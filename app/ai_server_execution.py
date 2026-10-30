"""Web jobs and token clients share registered, metered server workers."""
import io
import json
from pathlib import Path
import tempfile
import time
import zipfile


def enabled(native=False):
    # A diagnostic authentication bypass cannot select unowned local inference.
    # Only an explicitly native application may use the standalone local path.
    return not native


def identity():
    from .ai_global_execution import active_owner
    from .ai_metering_agent import require_dispatch_identity
    user_id = active_owner()
    require_dispatch_identity(user_id)
    return user_id


def infer(kind,source,options=None,*,cancel_check=None,raw=False):
    from .ai_metering_agent import execute_registered_worker,run_supervised_process
    from .ai_global_execution import active_owner,current_cancel
    from .model_license_policy import evaluate
    from .ai_execution_limits import inference_timeout
    from .ai_payload_limits import MAX_SOURCE_BYTES
    user_id=identity()
    plan={'kind':kind,**(options or {})}
    if plan['kind']!=kind:raise ValueError('AI plan cannot override the registered engine')
    evaluate(kind,plan)
    budget=inference_timeout(options or {})
    started=time.monotonic()
    def cancelled():
        active_owner(user_id)
        event=current_cancel.get()
        return bool(event and event.is_set()) or bool(cancel_check and cancel_check())
    with tempfile.TemporaryDirectory(prefix='mta-server-input-') as folder:
        wav=Path(folder)/'input.wav'
        prepared=run_supervised_process(['ffmpeg','-nostdin','-y','-v','error','-i',str(source),
            '-fs',str(MAX_SOURCE_BYTES+1),'-acodec','pcm_s16le',str(wav)],cwd=folder,
            timeout_seconds=budget,cancel_check=cancelled)
        if prepared.exit_code or time.monotonic()-started>=budget:
            raise RuntimeError('AI source preparation failed or timed out')
        if cancelled():raise RuntimeError('AI job cancelled after source preparation')
        if not 0<wav.stat().st_size<=MAX_SOURCE_BYTES:
            raise ValueError('Prepared AI source exceeds size limit or is empty')
        audio=wav.read_bytes()
        remaining=int(budget-(time.monotonic()-started))
        if remaining<1:raise RuntimeError('AI source preparation exhausted inference budget')
        payload,meta=execute_registered_worker(user_id,kind,plan,source_wav=audio,
            cancel_check=cancelled,timeout_seconds=remaining)
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
