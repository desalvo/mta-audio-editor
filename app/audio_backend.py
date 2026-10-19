"""Native and server engine preferences and immutable per-render backend selection.

Device transport and isolated live VST3 capabilities are reported separately. No compilation
is attempted at application startup. An unavailable selected C++ core fails
explicitly; an export never changes engine midway through its graph.
"""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import inspect
import json
import os
from pathlib import Path
import tempfile
import threading

_SCOPE=ContextVar('mta_audio_render_backend',default=None)
_LOCK=threading.RLock()
_RENDERING=ContextVar('mta_audio_render_transaction',default=False)


def _root(root=None):
    if root is not None:return Path(root)
    from .auth import data_root
    return data_root()


def _native():
    return os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true'


def _preference():
    return 'native-audio-engine.json' if _native() else 'server-audio-engine.json'


def requested(root=None):
    try:
        value=json.loads((_root(root)/_preference()).read_text(encoding='utf-8'))
        return 'cpp' if isinstance(value,dict) and value.get('engine')=='cpp' else 'current'
    except (OSError,ValueError):return 'current'


def status(root=None):
    from .cpp_audio import core_status
    core=core_status()
    from .native_transport import snapshot
    native=_native();snap=snapshot() if native else {};physical=snap.get('physical',False)
    from .vst3_live import available
    live=bool(core['available'] and available())
    return {'requested':requested(root),'cpp_available':core['available'],'cpp_abi':core['abi'],
            'scope':'native' if native else 'server','stage':'render-device' if native else 'server-render','transport':('native-device' if requested(root)=='cpp' else 'current') if native else 'browser','native_transport_available':bool(native and core['available']),'native_transport_ready':bool(requested(root)=='cpp' and physical),
            'native_host_ready':bool(requested(root)=='cpp' and snap.get('live_vst3') and not snap.get('failed')),'native_host_available':bool(native and live),'native_host_mode':'isolated-live-audio-effects','cpp_error':core['error']}


def select(engine,root=None):
    if engine not in ('current','cpp'):raise ValueError('Invalid audio engine')
    if engine=='cpp':
        from .cpp_audio import runtime
        runtime()
    root=_root(root);root.mkdir(parents=True,exist_ok=True)
    tmp=None
    with _LOCK:
        try:
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=root,prefix='.audio-engine-',delete=False) as f:
                tmp=Path(f.name);json.dump({'engine':engine,'schema':1},f);f.write('\n');f.flush();os.fsync(f.fileno())
            os.replace(tmp,root/_preference())
        finally:
            if tmp is not None:tmp.unlink(missing_ok=True)
    return status(root)


def selected():
    return _SCOPE.get() or requested()


def identity():
    return 'cpp-render-dsp-timeline-2' if selected()=='cpp' else 'current-render-dsp-1'


@contextmanager
def snapshot_context():
    if _SCOPE.get() is not None:
        yield _SCOPE.get()
        return
    engine=requested()
    if engine=='cpp':
        from .cpp_audio import runtime
        runtime()
    token=_SCOPE.set(engine)
    try:yield engine
    finally:_SCOPE.reset(token)


def render_scope(fn):
    @wraps(fn)
    def wrapped(*args,**kwargs):
        if _RENDERING.get():return fn(*args,**kwargs)
        with snapshot_context() as engine:
            transaction=_RENDERING.set(True);tmp=None
            try:
                if engine!='cpp':return fn(*args,**kwargs)
                bound=inspect.signature(fn).bind(*args,**kwargs)
                output=Path(bound.arguments['out']);output.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=output.parent,prefix='.'+output.stem+'-cpp-',suffix=output.suffix,delete=False) as f:tmp=Path(f.name)
                bound.arguments['out']=tmp
                result=fn(*bound.args,**bound.kwargs)
                os.replace(tmp,output)
                return output if isinstance(result,Path) and result==tmp else result
            finally:
                if tmp is not None:tmp.unlink(missing_ok=True)
                _RENDERING.reset(transaction)
    return wrapped
