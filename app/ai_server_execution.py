"""Web jobs and token clients share registered, metered server workers."""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile


def enabled(native=False):
    return not native and os.getenv('MTA_ALLOW_INSECURE_NO_AUTH','').lower() not in ('1','true','yes','on')


def identity():
    from .ai_global_execution import current_job
    from . import ai_arranger_runtime as queue
    jid=current_job.get()
    if jid:
        with queue._db() as con:row=con.execute('SELECT actor_user_id FROM jobs WHERE job_id=?',(jid,)).fetchone()
        if row and type(row[0]) is int and row[0]>0:return row[0]
    raise ValueError('Authenticated global AI job required')


def infer(kind,source,options=None,*,cancel_check=None,raw=False):
    from .ai_metering_agent import execute_registered_worker
    user_id=identity()
    with tempfile.TemporaryDirectory(prefix='mta-server-input-') as folder:
        wav=Path(folder)/'input.wav'
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-acodec','pcm_s16le',str(wav)],check=True,capture_output=True)
        audio=wav.read_bytes()
        payload,meta=execute_registered_worker(user_id,kind,{'kind':kind,**(options or {})},source_wav=audio,
            cancel_check=cancel_check,timeout_seconds=__import__('app.ai_execution_limits',fromlist=['inference_timeout']).inference_timeout(options or {}))
    if raw:
        from .ai_worker_protocol import verify_preview_wav
        with tempfile.TemporaryDirectory(prefix='mta-server-result-') as folder:
            output=Path(folder)/'preview.wav';output.write_bytes(payload)
            info=verify_preview_wav(output)
        return payload,{**meta,**info}
    result={'audio':{},'json':{}}
    from .ai_worker_artifacts import SAFE_NAME,MAX_FILES
    from .ai_payload_limits import MAX_ARTIFACT_CEILING_BYTES, MAX_MANIFEST_BYTES
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist())>MAX_FILES+1:raise ValueError('Too many AI results')
        total=0
        for entry in archive.infolist():
            if not SAFE_NAME.fullmatch(entry.filename):raise ValueError('Unsafe AI artifact')
            if entry.filename == 'manifest.json':
                if entry.file_size > MAX_MANIFEST_BYTES:raise ValueError('Oversized AI manifest')
                continue
            total+=entry.file_size
            if total>MAX_ARTIFACT_CEILING_BYTES:raise ValueError('Oversized AI result')
            data=archive.read(entry)
            if entry.filename.endswith('.wav'):result['audio'][entry.filename]=data
            elif entry.filename.endswith('.json') and entry.filename!='manifest.json':result['json'][entry.filename]=json.loads(data)
    return result,meta['job_id']
