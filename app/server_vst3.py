"""Authenticated, bounded per-user VST3 browser sessions.

Only administrator-installed plugins from trusted roots can execute. Plugin code
and dry preparation run in a disposable worker process group, never ASGI.
"""
import atexit
from dataclasses import dataclass,field
import math
import os
import re
import threading
import time
import uuid

from fastapi import HTTPException,Request,Response
from .vst3_live import Session


@dataclass
class Entry:
    owner: int
    project: str
    client: str
    touched: float=field(default_factory=time.monotonic)
    cancelled: threading.Event=field(default_factory=threading.Event)
    session: object=None
    error: str=''
    initializer: object=None
    editor: object=None


class Sessions:
    def __init__(self):
        self.lock=threading.RLock();self.entries={};self.reaper=None

    def close(self,token):
        with self.lock:entry=self.entries.pop(token,None)
        if entry:
            entry.cancelled.set()
            if entry.session:
                if entry.editor:
                    try:
                        from .server_vst3_editor import finish
                        finish(entry,wait=True)
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception('Could not persist original VST3 editor before session close')
                entry.session.close()
            if entry.initializer and entry.initializer is not threading.current_thread():entry.initializer.join(timeout=3)

    def reap(self,now=None):
        now=time.monotonic() if now is None else now
        with self.lock:stale=[key for key,e in self.entries.items() if now-e.touched>60]
        for key in stale:self.close(key)

    def shutdown(self):
        with self.lock:keys=list(self.entries)
        for key in keys:self.close(key)

    def start(self,owner,project,paths,client,cursor,*,asynchronous=False,monitor=False):
        self.reap()
        with self.lock:previous=[key for key,e in self.entries.items() if e.owner==owner and e.client==client]
        for key in previous:self.close(key)
        with self.lock:
            limit=max(1,min(64,int(os.getenv('MTA_SERVER_VST3_MAX_SESSIONS','8'))))
            if len(self.entries)>=limit:raise HTTPException(429,'Live VST3 capacity reached. Stop another session or contact the administrator.')
            if sum(e.owner==owner for e in self.entries.values())>=2:raise HTTPException(429,'At most two live VST3 sessions per user are allowed.')
            token=uuid.uuid4().hex;entry=Entry(owner,project.id,client);self.entries[token]=entry
            if self.reaper is None:
                def clean():
                    while True:
                        time.sleep(5);self.reap()
                self.reaper=threading.Thread(target=clean,name='mta-server-vst3-cleanup',daemon=True);self.reaper.start()
        def initialize():
            try:
                timeout=max(10,min(900,int(os.getenv('MTA_SERVER_VST3_START_TIMEOUT','120'))))
                def cancelled():
                    entry.touched=time.monotonic()
                    return entry.cancelled.is_set()
                session=Session(project,paths,cursor,cancelled=cancelled,output='browser',startup_timeout=timeout,**({'monitor':True} if monitor else {}))
                with self.lock:
                    if entry.cancelled.is_set():session.close();raise RuntimeError('Live VST3 session cancelled')
                    entry.session=session;entry.touched=time.monotonic()
                return {'session_id':token,'state':'ready',**session.status()}
            except BaseException as exc:
                if not asynchronous:self.close(token);raise
                with self.lock:entry.error=str(exc);entry.touched=time.monotonic()
        if asynchronous:
            entry.initializer=threading.Thread(target=initialize,name='mta-server-vst3-prepare',daemon=True)
            entry.initializer.start()
            return {'session_id':token,'state':'preparing','failed':False}
        return initialize()

    def get(self,token,owner,pid,*,allow_preparing=False):
        self.reap()
        with self.lock:
            entry=self.entries.get(token)
            if not entry or entry.owner!=owner or entry.project!=pid:raise HTTPException(404,'Live VST3 session not found or expired')
            entry.touched=time.monotonic()
            if entry.session is None and not allow_preparing:raise HTTPException(409,entry.error or 'Live VST3 session is preparing')
            return entry


sessions=Sessions()
atexit.register(sessions.shutdown)


def read_pcm(session,sequence,frames=32768):
    result=session.request('read',{'sequence':sequence,'frames':frames},timeout=15)
    name=result['chunk']
    if not re.fullmatch(r'pcm-[0-9a-f]{32}\.bin',name):raise RuntimeError('Invalid live PCM result')
    path=session.path/name
    try:
        count=result['frames']
        if type(count) is not int or not 0<=count<=frames or path.stat().st_size!=count*8:raise RuntimeError('Invalid live PCM size')
        return result,path.read_bytes()
    finally:path.unlink(missing_ok=True)


def register_routes(app,project_for_actor,actor):
    def guard(request,pid):
        if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true':raise HTTPException(404,'Server VST3 playback is unavailable in native mode')
        project=project_for_actor(request,pid)
        return actor(request)['id'],project

    def entry_for(request,pid,token,*,allow_preparing=False):
        owner,project=guard(request,pid)
        return sessions.get(token,owner,pid,allow_preparing=allow_preparing),project

    from .server_vst3_editor import register_routes as editor_routes
    editor_routes(app,entry_for)

    @app.post('/api/projects/{pid}/vst3-live',status_code=202)
    def start(pid:str,body:dict,request:Request):
        owner,project=guard(request,pid)
        from .audio_backend import selected
        from .vst3_live import available
        from .storage import validate_project_files,audio_path
        if selected()!='cpp' or not available():raise HTTPException(409,'Ask the administrator to select the C++ engine and install the VST3 runtime.')
        cursor=body.get('cursor_ms',0);client=body.get('client_id')
        if type(cursor) not in (int,float) or not math.isfinite(cursor) or cursor<0:raise HTTPException(422,'Invalid playback position')
        if not isinstance(client,str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,64}',client):raise HTTPException(422,'Invalid browser client identity')
        if not 1<=len(project.tracks)<=64:raise HTTPException(422,'Live VST3 supports 1–64 tracks')
        validate_project_files(project)
        paths=[audio_path(pid,t.filename) for t in project.tracks]
        try:return sessions.start(owner,project,paths,client,cursor,asynchronous=True)
        except (ValueError,RuntimeError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.get('/api/projects/{pid}/vst3-live/{token}')
    def status(pid:str,token:str,request:Request,response:Response):
        entry,_=entry_for(request,pid,token,allow_preparing=True)
        response.headers['Cache-Control']='no-store'
        if entry.error:return {'session_id':token,'state':'failed','failed':True,'error':entry.error}
        if entry.session is None:return {'session_id':token,'state':'preparing','failed':False}
        return {'session_id':token,'state':'ready',**entry.session.status()}

    @app.post('/api/projects/{pid}/vst3-live/{token}/pcm')
    def pcm(pid:str,token:str,body:dict,request:Request):
        entry,_=entry_for(request,pid,token)
        seq=body.get('sequence');frames=body.get('frames',32768)
        if type(seq) is not int or seq<0 or type(frames) is not int or not 1024<=frames<=32768:raise HTTPException(422,'Invalid PCM request')
        try:
            result,data=read_pcm(entry.session,seq,frames)
            return Response(data,media_type='application/octet-stream',headers={
                'Cache-Control':'no-store','X-MTA-Frames':str(result['frames']),'X-MTA-Rate':str(result['rate']),
                'X-MTA-Start-Frame':str(result['start_frame']),'X-MTA-Sequence':str(result['sequence']),
                'X-MTA-Ended':'1' if result['ended'] else '0'})
        except (ValueError,RuntimeError,OSError) as exc:
            # A lost/invalid chunk cannot be retried as if it had never advanced DSP.
            sessions.close(token);raise HTTPException(409,str(exc)) from exc

    @app.post('/api/projects/{pid}/vst3-live/{token}/control')
    def control(pid:str,token:str,body:dict,request:Request):
        entry,project=entry_for(request,pid,token)
        try:
            if body.get('action')=='update':return entry.session.update(project)
            if body.get('action') in ('play','pause'):return entry.session.request(body['action'])
            if body.get('action')=='seek':
                value=body.get('cursor_ms')
                if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise HTTPException(422,'Invalid seek')
                if 'playing' in body and type(body['playing']) is not bool:raise HTTPException(422,'Invalid host playing state')
                result=entry.session.request('seek',value)
                if 'playing' in body:result=entry.session.request('play' if body['playing'] else 'pause')
                return result
            raise HTTPException(422,'Unsupported server VST3 control')
        except (ValueError,RuntimeError,OSError) as exc:
            sessions.close(token);raise HTTPException(409,str(exc)) from exc

    @app.delete('/api/projects/{pid}/vst3-live/{token}')
    def stop(pid:str,token:str,request:Request):
        entry_for(request,pid,token,allow_preparing=True);sessions.close(token)
        return {'ok':True}

