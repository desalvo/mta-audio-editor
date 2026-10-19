"""Original plugin windows isolated from the application and audio-device process."""
import atexit
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import uuid
from .vst3_host import validate_plugin_path,worker_command

_LOCK=threading.RLock();_JOBS={}


def start(params):
    from .main import NATIVE_SINGLE_USER
    if not NATIVE_SINGLE_USER:raise ValueError('Desktop plugin editor required')
    if not isinstance(params,dict):raise ValueError('Invalid plugin parameters')
    path=validate_plugin_path(str(params.get('path','')))
    with _LOCK:
        if _JOBS:raise ValueError('Close the current plugin editor first')
        scratch=tempfile.TemporaryDirectory(prefix='mta-vst3-editor-');root=Path(scratch.name)
        values={k:v for k,v in params.items() if k!='path'}
        encoded=json.dumps(values,allow_nan=False)
        if len(encoded)>13*1024*1024:scratch.cleanup();raise ValueError('VST3 state too large')
        config=root/'parameters.json';config.write_text(encoded,encoding='utf-8');log=(root/'editor.log').open('wb')
        try:proc=subprocess.Popen(worker_command('--editor-plugin',path,'--editor-result',root/'result.json','--parameters-file',config),stdout=subprocess.DEVNULL,stderr=log)
        except BaseException:log.close();scratch.cleanup();raise
        token=uuid.uuid4().hex;_JOBS[token]=(proc,scratch,log)
        return {'editor_id':token,'state':'running'}


def poll(token):
    with _LOCK:
        if token not in _JOBS:raise ValueError('Plugin editor not found')
        proc,scratch,log=_JOBS[token]
        if proc.poll() is None:return {'state':'running'}
        root=Path(scratch.name)
        try:
            if proc.returncode:raise RuntimeError('Plugin editor failed (exit '+str(proc.returncode)+')')
            path=root/'result.json'
            if not path.is_file() or path.stat().st_size>13*1024*1024:raise RuntimeError('Invalid plugin editor state')
            result=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(result,dict):raise RuntimeError('Invalid plugin state')
            return {'state':'completed','params':result}
        finally:log.close();scratch.cleanup();del _JOBS[token]


def close():
    with _LOCK:
        for proc,scratch,log in _JOBS.values():
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
            log.close();scratch.cleanup()
        _JOBS.clear()


atexit.register(close)
