"""Bounded PCM capture upload, followed by the existing durable media transaction.

Web capture always records the client input, never the server's sound device.
"""
import atexit
from dataclasses import dataclass,field
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid

from fastapi import HTTPException,Request,UploadFile


@dataclass
class Capture:
    owner:int
    pid:str
    rate:int
    offset:int
    folder:object
    storage_owner:int|None=None
    size:int=0
    sequence:int=0
    touched:float=field(default_factory=time.monotonic)
    lock:object=field(default_factory=threading.RLock)


_LOCK=threading.RLock();_CAPTURES={};_REAPER=None


def close(token):
    with _LOCK:entry=_CAPTURES.pop(token,None)
    if entry:
        with entry.lock:entry.folder.cleanup()


def shutdown():
    with _LOCK:tokens=list(_CAPTURES)
    for token in tokens:close(token)


atexit.register(shutdown)


def register_routes(app,project_for_actor,actor):
    def get(request,pid,token):
        project_for_actor(request,pid);owner=actor(request)['id']
        with _LOCK:entry=_CAPTURES.get(token)
        if not entry or entry.owner!=owner or entry.pid!=pid:raise HTTPException(404,'Audio recording not found or expired')
        entry.touched=time.monotonic();return entry

    @app.post('/api/projects/{pid}/audio-capture')
    def start(pid:str,body:dict,request:Request):
        global _REAPER
        project=project_for_actor(request,pid);owner=actor(request)['id']
        rate=body.get('rate');offset=body.get('offset_ms',0)
        if type(rate) is not int or not 8000<=rate<=192000 or type(offset) is not int or not 0<=offset<=86400000:raise HTTPException(422,'Invalid audio capture format or position')
        from .main import _ensure_workspace_capacity
        _ensure_workspace_capacity(project.owner_user_id,4096)
        with _LOCK:
            if len(_CAPTURES)>=16 or any(c.owner==owner for c in _CAPTURES.values()):raise HTTPException(429,'An audio recording is already active or server capture capacity is full')
            token=uuid.uuid4().hex;folder=tempfile.TemporaryDirectory(prefix='mta-capture-')
            _CAPTURES[token]=Capture(owner,pid,rate,offset,folder,storage_owner=project.owner_user_id)
            (Path(folder.name)/'capture.f32').touch(mode=0o600)
            if _REAPER is None:
                def reap():
                    while True:
                        time.sleep(10)
                        with _LOCK:stale=[key for key,value in _CAPTURES.items() if time.monotonic()-value.touched>45]
                        for key in stale:close(key)
                _REAPER=threading.Thread(target=reap,name='mta-audio-capture-cleanup',daemon=True);_REAPER.start()
        return {'capture_id':token,'rate':rate,'channels':2,'limit_bytes':max(1024**2,min(4*1024**3,int(os.getenv('MTA_AUDIO_CAPTURE_LIMIT_BYTES',str(512*1024**2)))))}

    @app.get('/api/projects/{pid}/audio-capture/{token}')
    def status(pid:str,token:str,request:Request):
        entry=get(request,pid,token)
        with entry.lock:return {'sequence':entry.sequence,'frames':entry.size//8,'rate':entry.rate}

    @app.post('/api/projects/{pid}/audio-capture/{token}/pcm')
    async def pcm(pid:str,token:str,request:Request,sequence:int):
        entry=get(request,pid,token);raw=bytearray()
        async for part in request.stream():
            raw.extend(part)
            if len(raw)>262144:raise HTTPException(413,'Audio capture packet exceeds 32768 stereo frames')
        if not raw or len(raw)%8:raise HTTPException(422,'Invalid stereo float PCM packet')
        import numpy as np
        if not np.isfinite(np.frombuffer(raw,dtype='<f4')).all():raise HTTPException(422,'Non-finite audio capture')
        with entry.lock:
            if sequence!=entry.sequence:raise HTTPException(409,'Audio capture sequence mismatch')
            limit=max(1024**2,min(4*1024**3,int(os.getenv('MTA_AUDIO_CAPTURE_LIMIT_BYTES',str(512*1024**2)))))
            if entry.size+len(raw)>limit or (entry.size+len(raw))/8/entry.rate>3600:raise HTTPException(413,'Recording size or one-hour duration limit reached; save the recording before continuing')
            from .main import _ensure_workspace_capacity
            _ensure_workspace_capacity(entry.storage_owner,entry.size+len(raw)+4096)
            with (Path(entry.folder.name)/'capture.f32').open('ab') as output:output.write(raw)
            entry.size+=len(raw);entry.sequence+=1
            return {'sequence':entry.sequence,'frames':entry.size//8}

    @app.post('/api/projects/{pid}/audio-capture/{token}/finish')
    async def finish(pid:str,token:str,body:dict,request:Request):
        entry=get(request,pid,token)
        # Existing import waits only for staging; decoding/publication is async.
        try:
            with entry.lock:
                if body.get('sequence')!=entry.sequence or not entry.size:raise HTTPException(409,'Recording is empty or has unacknowledged audio packets')
                import numpy as np
                import soundfile as sf
                root=Path(entry.folder.name);target=root/'recording.wav'
                with (root/'capture.f32').open('rb') as source,sf.SoundFile(target,'w',samplerate=entry.rate,channels=2,subtype='FLOAT',format='WAV') as writer:
                    while raw:=source.read(32768*8):writer.write(np.frombuffer(raw,dtype='<f4').reshape(-1,2))
                with target.open('rb') as source:
                    from .main import start_track_import_job
                    return await start_track_import_job(pid,request,UploadFile(file=source,filename='recording.wav'),name=str(body.get('name') or 'Audio recording')[:200],offset_ms=entry.offset)
        finally:close(token)

    @app.delete('/api/projects/{pid}/audio-capture/{token}')
    def cancel(pid:str,token:str,request:Request):
        get(request,pid,token);close(token);return {'ok':True}
