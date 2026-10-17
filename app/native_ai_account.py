"""One private AI credential per native installation and selected MTA server."""
from __future__ import annotations
import json
import os
import secrets
import threading
import time
from pathlib import Path
from .platform_file_lock import private_mode
from urllib.request import Request,build_opener,HTTPSHandler,HTTPRedirectHandler
from .ai_remote_client import _endpoint

_LOCK=threading.RLock()


def _file():
    from .native_ai_routing import _file as routing_file
    return Path(os.getenv('MTA_NATIVE_AI_ACCOUNT',str(routing_file().with_name('native-ai-account.json'))))


def _read():
    try:
        data=json.loads(_file().read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):return {}


def _write(data):
    import tempfile
    path=_file();path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.ai-account-')
    try:
        private_mode(fd)
        with os.fdopen(fd,'w') as stream:json.dump(data,stream)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def base_url(value):
    if not isinstance(value,str) or len(value)>2048:raise ValueError('Invalid MTA server URL')
    return _endpoint(value,'whisper').split('/api/ai-jobs/',1)[0]


def _request(server,path,data):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    request=Request(base_url(server)+path,data=json.dumps(data).encode(),  # noqa: S310 -- HTTPS validated
      headers={'Content-Type':'application/json','x-mta-request':'1'},method='POST')  # noqa: S310 -- validated HTTPS server
    with build_opener(HTTPSHandler(),NoRedirect()).open(request,timeout=15) as response:
        raw=response.read(16385)
    if len(raw)>16384:raise ValueError('Oversized authorization response')
    result=json.loads(raw)
    if not isinstance(result,dict):raise ValueError('Invalid authorization response')
    return result


def public_status():
    data=_read();pending=data.get('pending',{})
    return {'server':data.get('server',''),'connected':bool(data.get('token')),
      'token_id':data.get('token_id'),'user_id':data.get('user_id'),
      'state':data.get('state','disconnected'),'verification_uri':pending.get('verification_uri',''),
      'user_code':pending.get('user_code',''),'expires_at':pending.get('expires_at'),
      'client_id':data.get('client_id','')}


def begin(server,label='MTA native application'):
    server=base_url(server)
    with _LOCK:
        old=_read();client=old.get('client_id') or secrets.token_hex(16)
        if not isinstance(label,str):raise ValueError('Invalid instance label')
        label=label[:67]+' · '+client[-8:]
        response=_request(server,'/api/ai-device/start',{'client_id':client,'label':label})
        code=response.get('device_code');user_code=response.get('user_code')
        if not isinstance(code,str) or not 32<=len(code)<=100 or not isinstance(user_code,str):
            raise ValueError('Invalid device authorization response')
        # The server may return only its fixed relative approval path, no third-party URL.
        from urllib.parse import quote
        uri=server+'/ai-device?code='+quote(user_code,safe='')
        _write({'client_id':client,'server':server,'state':'pending','pending':{
          'device_code':code,'user_code':user_code,'verification_uri':uri,
          'expires_at':time.time()+min(900,max(1,int(response.get('expires_in',900))))}})
    return public_status()


def poll():
    with _LOCK:
        data=_read();pending=data.get('pending')
        if not pending:return public_status()
        if pending['expires_at']<=time.time():
            data.pop('pending',None);data['state']='expired';_write(data);return public_status()
        result=_request(data['server'],'/api/ai-device/poll',{'device_code':pending['device_code']})
        state=result.get('state')
        if state=='approved':
            token=result.get('token')
            if not isinstance(token,str) or not token.startswith('mta_ai_') or len(token)>180:
                raise ValueError('Invalid AI token response')
            data.update(token=token,token_id=result.get('token_id'),user_id=result.get('user_id'),state='connected')
            data.pop('pending',None);_write(data)
        elif state in ('expired','denied'):
            data.pop('pending',None);data['state']=state;_write(data)
    return public_status()


def credentials():
    data=_read()
    if not data.get('token'):raise ValueError('Connect this native instance to an MTA account first')
    return {'url':data['server'],'token':data['token']}


def execute_arranger(plan,project,resolve_audio,*,cancel_event=None):
    import tempfile
    from .ai_durable_remote_executor import render_source
    from .ai_remote_client import infer_audio,recover_after_lost_response
    from . import ai_native_remote_journal as journal
    from .ai_worker_protocol import verify_preview_wav
    from .ai_execution_limits import inference_timeout
    cfg=credentials()
    with tempfile.TemporaryDirectory(prefix='mta-native-remote-') as folder:
        source=Path(folder)/'source.wav';render_source(plan,project,resolve_audio,source)
        if plan.get('scope')=='range':
            from .ai_worker_protocol import _trim_wav_for_ai
            _trim_wav_for_ai(source,plan.get('start_ms'),plan.get('end_ms'))
        options={key:plan[key] for key in ('model_id','operation','prompt','strength','inference_timeout_seconds') if key in plan}
        options.setdefault('model_id','ace-step-1.5')
        key,existing,fingerprint=journal.begin(cfg['url'],cfg['token'],'ace-step',source.read_bytes(),options)
        if existing:
            payload,mime,remote_id=recover_after_lost_response(cfg['url'],cfg['token'],key,cancel_event=cancel_event)
        else:
            finished=threading.Event()
            def cancel_watch():
                from .ai_remote_client import cancel_remote_request
                while not finished.wait(.2):
                    if cancel_event is not None and cancel_event.is_set():
                        try:cancel_remote_request(cfg['url'],cfg['token'],key,timeout_seconds=2)
                        except (ValueError,RuntimeError,OSError):
                            if finished.wait(1):return
                            continue
                        return
            watcher=threading.Thread(target=cancel_watch,daemon=True,name='mta-remote-cancel')
            if cancel_event is not None:watcher.start()
            try:
                payload,mime,remote_id=infer_audio(cfg['url'],cfg['token'],'ace-step',source.read_bytes(),options,
                  request_id=key,timeout_seconds=inference_timeout(plan),cancel_event=cancel_event)
            finally:
                finished.set()
                if cancel_event is not None:watcher.join(3)

        if mime!='audio/wav':raise ValueError('ACE server returned a non-audio result')
        target=Path(folder)/'result.wav';target.write_bytes(payload);info=verify_preview_wav(target)
        if cancel_event is not None and cancel_event.is_set():raise RuntimeError('Remote generation cancelled')
        journal.finish(fingerprint,key)
        return payload,{**info,'remote_job_id':remote_id,'mode':'remote'}
