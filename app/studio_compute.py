"""Registered studio execution shared by authenticated server and local native."""
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import zipfile


def terminate(process):
    if process.poll() is not None:return
    if os.name=='posix':
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    else:
        subprocess.run([str(Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/taskkill.exe'),
                        '/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
    process.wait()


def compute(user_id,kind,plan,**kwargs):
    if user_id==0:
        from .native_ai_routing import is_remote
        if is_remote('audio-to-midi' if kind.startswith('audio-to-midi-') else kind):
            from .model_license_policy import authorize_remote_execution
            authorize_remote_execution(kind,plan)
            return remote_compute(kind,plan,**kwargs)
    # Runtime removal/upgrade cannot race an active model process.
    from contextlib import nullcontext
    from .ai_project_lock import project_publication_lock
    guard=project_publication_lock('studio-model:basic-pitch') if kind.startswith('audio-to-midi') else project_publication_lock('studio-model:oddvoices') if kind=='vocal-synthesis' else nullcontext()
    from contextlib import ExitStack
    with ExitStack() as stack:
        stack.enter_context(guard)
        if kind=='vocal-synthesis' or kind.endswith('transkun'):
            stack.enter_context(project_publication_lock('studio-model:managed'))
        return _compute(user_id,kind,plan,**kwargs)


def _compute(user_id,kind,plan,*,audio=None,score=None,cancelled=lambda:False,timeout=3600,progress=None,artifact_mode='music'):
    if user_id>0:
        from .ai_metering_agent import execute_registered_worker
        payload,meta=execute_registered_worker(user_id,kind,plan,source_wav=audio,source_json=score,
                                               cancel_check=cancelled,timeout_seconds=timeout)
    else:
        # Local single-user jobs have no server ledger or billing identity.
        from .model_license_policy import evaluate
        evaluate(kind,plan)
        if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()!='true':
            raise ValueError('Studio inference requires an authenticated server user or a native application')
        from .ai_worker_registry import worker_python,resolve_worker
        from .ai_worker_artifacts import package_artifacts
        from .storage import _atomic_json_write
        worker=resolve_worker(kind)
        if worker is None:raise RuntimeError('Studio model is not installed or enabled')
        with tempfile.TemporaryDirectory(prefix='mta-local-studio-') as folder:
            root=Path(folder);request={**plan,'kind':kind}
            if audio is not None:
                (root/'source.wav').write_bytes(audio);request['source_audio']=str(root/'source.wav')
            if score is not None:
                from .studio_score import validate
                validate(score);(root/'score.json').write_bytes(score);request['source_score']=str(root/'score.json')
            (root/'request.json').write_text(json.dumps(request,allow_nan=False))
            args=[worker_python(kind),str(worker),'--request',str(root/'request.json'),'--output',str(root/'preview.wav')]
            env={**os.environ,'MTA_AI_PROGRESS_FILE':str(progress or root/'progress.json')}
            usage={}
            if hasattr(os,'wait4'):
                from .ai_metering_agent import run_metered_process
                result=run_metered_process(args,cwd=folder,timeout_seconds=timeout,cancel_check=cancelled,env=env)
                if result.isolated:usage={k:v for k,v in result.usage.items() if k=='cpu_seconds'}
                if progress:_atomic_json_write(Path(progress),{'phase':'worker-exited',**usage})
                if result.exit_code:raise RuntimeError('Local studio worker failed, was cancelled or timed out')
            else:
                process=subprocess.Popen(args,cwd=folder,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                deadline=time.monotonic()+timeout
                try:
                    while process.poll() is None:
                        if cancelled():raise RuntimeError('Job cancelled; local worker stopped')
                        if time.monotonic()>deadline:raise RuntimeError('Local worker timed out')
                        time.sleep(.05)
                    if process.returncode:raise RuntimeError('Local studio worker failed')
                finally:terminate(process)
            if cancelled():raise RuntimeError('Job cancelled; local result discarded')
            payload,_=package_artifacts(root)
            meta={'usage':usage,'metering_source':'local-worker','billable':False}
            if progress:_atomic_json_write(Path(progress),{'phase':'validating-results',**usage})
    if artifact_mode=='stems':return stem_artifacts(payload),meta
    from .music_interchange import MusicResult,parse_result
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entry=archive.getinfo('music.json')
        if entry.file_size>16*1024*1024:raise ValueError('Musical result exceeds 16 MiB')
        result=parse_result(archive.read(entry)) if kind.startswith('audio-to-midi') else MusicResult.model_validate_json(archive.read(entry))
        if kind=='vocal-synthesis':
            meta['audio_artifacts']=singing_artifacts(archive,result);meta['singing_metadata']=singing_metadata(archive)
    return result,meta


def remote_compute(kind,plan,*,audio=None,score=None,cancelled=lambda:False,timeout=3600,progress=None,artifact_mode='music'):
    """One server token, durable request identity, no local fallback or rebilling."""
    from .model_license_policy import authorize_remote_execution
    authorize_remote_execution(kind,plan)
    import threading
    from .native_ai_routing import _read
    from . import ai_native_remote_journal as journal
    from .ai_remote_client import infer_audio,recover_after_lost_response,cancel_remote_request,remote_resources
    cfg=_read().get('workers',{}).get('audio-to-midi' if kind.startswith('audio-to-midi-') else kind,{})
    if cfg.get('mode')!='remote':raise ValueError('Remote Studio mode not configured')
    source=score if score is not None else audio
    if source is None:raise ValueError('Missing remote Studio source')
    options={k:v for k,v in plan.items() if k!='kind'}
    key,pending,fingerprint=journal.begin(cfg['url'],cfg['token'],kind,source,options)
    stop=threading.Event();done=threading.Event()
    def watch():
        while not done.wait(.1):
            if cancelled():
                stop.set()
                try:cancel_remote_request(cfg['url'],cfg['token'],key,timeout_seconds=5)
                except RuntimeError:pass
                return
    thread=threading.Thread(target=watch,daemon=True,name='mta-studio-remote-cancel');thread.start()
    try:
        if progress:
            from .storage import _atomic_json_write
            _atomic_json_write(Path(progress),{'phase':'remote-inference','message':'Processing on the configured AI server','progress_percent':None})
        if pending:
            payload,mime,jid=recover_after_lost_response(cfg['url'],cfg['token'],key,max_wait_seconds=min(3600,timeout),
                require_attestation=True,cancel_event=stop)
        else:
            payload,mime,jid=infer_audio(cfg['url'],cfg['token'],kind,source,options,timeout_seconds=timeout,request_id=key,
                require_attestation=True,cancel_event=stop,source_format='score' if score is not None else 'wav')
        if cancelled():raise RuntimeError('Remote Studio result discarded after cancellation')
        if mime!='application/zip':raise ValueError('Remote Studio returned an unexpected result format')
        from .music_interchange import MusicResult,parse_result
        audio_artifacts={};metadata={}
        if artifact_mode=='stems':result=stem_artifacts(payload)
        else:
            result=None
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if artifact_mode!='stems':
                entry=archive.getinfo('music.json')
                if entry.file_size>16*1024*1024:raise ValueError('Remote music result exceeds 16 MiB')
                result=parse_result(archive.read(entry)) if kind.startswith('audio-to-midi') else MusicResult.model_validate_json(archive.read(entry))
                audio_artifacts=singing_artifacts(archive,result) if kind=='vocal-synthesis' else {}
                metadata=singing_metadata(archive) if kind=='vocal-synthesis' else {}
        # HTTPS/token ownership binds these counters to the server ledger.
        # They are displayed locally, never used to create a second local bill.
        resources=remote_resources(cfg['url'],cfg['token'],jid)
        return result,{'audio_artifacts':audio_artifacts,'singing_metadata':metadata,'usage':resources['usage'],'remote_job_id':jid,'billable':False,
            'metering_source':'remote-server-ledger','acknowledge':lambda:journal.finish(fingerprint,key)}
    finally:done.set();thread.join(timeout=.2)


def singing_artifacts(archive,result):
    from .ai_payload_limits import worker_artifact_bytes,MAX_ARTIFACT_BYTES
    limit=worker_artifact_bytes(MAX_ARTIFACT_BYTES);total=0;audio={}
    for index,part in enumerate(result.parts):
        entry=archive.getinfo(f'voice-{index}.wav');total+=entry.file_size
        if entry.file_size<=44 or total>limit:raise ValueError('Singing audio artifact exceeds configured limit')
        audio[part.id]=archive.read(entry)
    return audio


def singing_metadata(archive):
    entry=archive.getinfo('singing.json')
    if entry.file_size>4*1024*1024:raise ValueError('Singing metadata exceeds limit')
    value=json.loads(archive.read(entry))
    if not isinstance(value,dict) or len(value)>32:raise ValueError('Invalid singing metadata')
    return value



def stem_artifacts(payload):
    """Only admit Demucs' four expected, bounded PCM stems; ignore no extras."""
    from .ai_payload_limits import worker_artifact_bytes, MAX_ARTIFACT_BYTES
    from .ai_worker_artifacts import _verify_wav_bytes
    limit=worker_artifact_bytes(MAX_ARTIFACT_BYTES)
    expected={'stem_bass.wav','stem_drums.wav','stem_other.wav','stem_vocals.wav'}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries=archive.infolist()
        names=[entry.filename for entry in entries]
        if len(names)!=len(set(names)) or set(names)-expected-{'manifest.json'} or not expected<=set(names):
            raise ValueError('Demucs must return exactly the four htdemucs stems')
        if sum(entry.file_size for entry in entries)>limit:
            raise ValueError('Separated sources exceed artifact budget')
        result={}
        for name in sorted(expected):
            data=archive.read(name);_verify_wav_bytes(data);result[name]=data
    return result
