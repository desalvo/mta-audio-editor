"""Native bridge for local device discovery, capture and isolated monitoring."""
import atexit
import os
import threading
import heapq
import math
import logging
import time

from .midi_devices import Input,ports,SharedOutput,validate_messages

_LOCK=threading.RLock();_MONITOR=None;_CAPTURE=None;_MONITOR_INPUT='';_PROJECT=None
_OUTPUTS={};_PENDING=[];_OUTPUT_CONDITION=threading.Condition();_OUTPUT_THREAD=None;_SERIAL=0


def _guard():
    if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()!='true':raise ValueError('Local MIDI device access requires a native application')


def list_ports():
    _guard()
    try:return ports()
    except (ImportError,RuntimeError,OSError) as exc:return {'available':False,'inputs':[],'outputs':[],'error':str(exc)}


def start(pid,tid,options=None):
    global _MONITOR,_MONITOR_INPUT,_PROJECT
    _guard()
    from .audio_backend import requested
    from .storage import load_project,audio_path,validate_project_files
    from .midi_monitor import monitor_project
    from .vst3_live import Session
    from .vst3_transport import runtime_available
    if requested()!='cpp' or not runtime_available():raise ValueError('Select C++ and install the updated VST host runtime')
    with _LOCK:
        stop();project=load_project(pid);validate_project_files(project);project=monitor_project(project,tid)
        options=options or {};_MONITOR_INPUT=options.get('input','')
        _MONITOR=Session(project,[audio_path(pid,t.filename) for t in project.tracks],0,monitor=True,midi_options=options)
        _PROJECT=pid
        return {'ok':True,'buffer_frames':1536,'rate':project.sample_rate}


def control(action,value=None):
    _guard()
    with _LOCK:
        if not _MONITOR:raise ValueError('MIDI monitoring is not running')
        if action not in ('midi','ump','panic','transport','midi-parameters'):raise ValueError('Unsupported MIDI control')
        _MONITOR.request(action,value)
        return {'ok':True}


def capture_start(name,sysex=False):
    global _CAPTURE
    _guard()
    with _LOCK:
        capture_stop()
        if not (_MONITOR and _MONITOR_INPUT==name):_CAPTURE=Input(name,sysex=sysex)
        return {'ok':True}


def capture_poll():
    _guard()
    with _LOCK:
        if _CAPTURE:return _CAPTURE.capture()
        if _MONITOR:
            result=_MONITOR.request('midi-input');result['monitoring']=True;return result
        return {'events':[],'connected':False}


def capture_stop():
    global _CAPTURE
    with _LOCK:
        if _CAPTURE:_CAPTURE.close();_CAPTURE=None
    return {'ok':True}


def stop():
    global _MONITOR,_MONITOR_INPUT,_PROJECT
    with _LOCK:
        capture_stop()
        if _MONITOR:_MONITOR.close();_MONITOR=None
        _MONITOR_INPUT='';_PROJECT=None
    return {'ok':True}


def send(name,data,delay_ms=0):
    global _OUTPUT_THREAD,_SERIAL
    _guard()
    if not (isinstance(data,list) and (data in ([0xF8],[0xFA],[0xFB],[0xFC]) or (len(data)==3 and data[0]==0xF2 and all(type(v) is int and 0<=v<=127 for v in data[1:])))):validate_messages([data],sysex=True)
    if type(delay_ms) not in (int,float) or not math.isfinite(delay_ms) or not 0<=delay_ms<=1000:raise ValueError('Invalid MIDI output timestamp')
    with _OUTPUT_CONDITION:
        if len(_PENDING)>=4096:raise ValueError('MIDI output queue full: use Panic')
        if name not in _OUTPUTS:
            if len(_OUTPUTS)>=16:raise ValueError('At most 16 MIDI outputs may be open')
            _OUTPUTS[name]=SharedOutput(name)
        _SERIAL+=1;heapq.heappush(_PENDING,(time.monotonic()+delay_ms/1000,_SERIAL,name,list(data)))
        if _OUTPUT_THREAD is None:
            def run():
                while True:
                    with _OUTPUT_CONDITION:
                        if not _PENDING:_OUTPUT_CONDITION.wait();continue
                        due,_,port,message=_PENDING[0];remaining=due-time.monotonic()
                        if remaining>0:_OUTPUT_CONDITION.wait(timeout=min(.01,remaining));continue
                        heapq.heappop(_PENDING)
                        try:_OUTPUTS[port].send(message)
                        except Exception:
                            try:_OUTPUTS[port].panic()
                            except Exception:logging.getLogger(__name__).debug('MIDI cleanup failed',exc_info=True)
            _OUTPUT_THREAD=threading.Thread(target=run,name='mta-midi-port-output',daemon=True);_OUTPUT_THREAD.start()
        _OUTPUT_CONDITION.notify()
    return {'ok':True}


def panic(name=None):
    _guard()
    with _OUTPUT_CONDITION:
        _PENDING[:]=[item for item in _PENDING if name and item[2]!=name];heapq.heapify(_PENDING)
        for key,output in _OUTPUTS.items():
            if name is None or key==name:output.panic()
        # Include ports currently owned only by a native transport sequencer.
        with SharedOutput.lock:
            for key,(output,_) in SharedOutput.pool.items():
                if key not in _OUTPUTS and (name is None or key==name):output.panic()
    return {'ok':True}


def shutdown():
    stop()
    with _OUTPUT_CONDITION:
        _PENDING.clear()
        for output in _OUTPUTS.values():
            try:output.close()
            except Exception:logging.getLogger(__name__).debug('MIDI cleanup failed',exc_info=True)
        _OUTPUTS.clear()


atexit.register(shutdown)


atexit.register(stop)
