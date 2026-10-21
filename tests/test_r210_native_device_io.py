"""Real compiled callback routing plus fail-closed native device settings."""
import ctypes as C
import shutil
import time

import numpy as np
import pytest
from app import native_device_io as io


@pytest.fixture(scope='module')
def compiled_core(tmp_path_factory, compiled_audio_core_build):
    target = tmp_path_factory.mktemp('device-io-core') / compiled_audio_core_build.name
    shutil.copy2(compiled_audio_core_build, target)
    return target


@pytest.fixture
def core(compiled_core,monkeypatch):
    from app.cpp_audio import runtime,_load
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));_load.cache_clear()
    return runtime().lib


def test_native_external_callback_maps_stereo_to_many_outputs(core):
    from app.native_transport import bind_stream,State
    bind_stream(core)
    core.mta_transport_open_external.argtypes=[C.c_uint32,C.c_uint64,C.c_uint32,C.POINTER(C.c_float)];core.mta_transport_open_external.restype=C.c_void_p
    core.mta_transport_external_callback.restype=C.c_void_p
    gains=(C.c_float*8)(1,0,0,1,.5,.5,-1,0)
    handle=core.mta_transport_open_external(48000,8,4,gains);assert handle
    callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_ulong,C.c_void_p,C.c_ulong,C.c_void_p)(core.mta_transport_external_callback())
    try:
        pcm=np.array([[.2,.6]]*8,dtype=np.float32)
        assert core.mta_transport_push(handle,pcm.ctypes.data_as(C.POINTER(C.c_float)),8)==0
        assert core.mta_transport_play(handle)==0
        out=np.full((8,4),99,dtype=np.float32)
        assert callback(None,out.ctypes.data,8,None,0,handle)==0
        assert np.allclose(out,np.tile([.2,.6,.4,-.2],(8,1)))
        assert core.mta_transport_pause(handle)==0
        out[:]=99;callback(None,out.ctypes.data,8,None,0,handle);assert not out.any()
        state=State();assert core.mta_transport_status(handle,C.byref(state))==0
        assert state.position==8 and state.underruns==0
        assert callback(None,None,8,None,0,handle)==2
    finally:core.mta_transport_close(handle)
    gains[0]=float('nan');assert not core.mta_transport_open_external(48000,8,4,gains)


def test_settings_reject_invalid_matrix_and_wrong_backend():
    for value in ({'output_channels':3},{'output_matrix':[[float('nan'),0],[0,1]]},
                  {'backend':'miniaudio','output_name':'Specific'}, {'blocksize':255},
                  {'input_channels':8,'input_matrix':[[1,0],[0,1]]}):
        with pytest.raises(ValueError):io.Settings.model_validate(value)
    cfg=io.Settings(backend='portaudio',output_channels=4,output_matrix=[[1.,0.],[0.,1.],[.5,.5],[0.,0.]])
    assert len(cfg.output_matrix)==4


def test_explicit_device_is_not_replaced_when_missing(monkeypatch):
    class Backend:
        default=type('Defaults',(),{'device':(0,0)})()
        def query_hostapis(self):return [{'name':'ASIO','type':3}]
        def query_devices(self,index=None):
            values=[{'name':'Other interface','hostapi':0,'max_output_channels':8,'max_input_channels':8}]
            return values if index is None else values[index]
    monkeypatch.setattr(io,'sounddevice',lambda:Backend())
    cfg=io.Settings(backend='portaudio',host_api='ASIO',output_name='Missing interface')
    with pytest.raises(ValueError,match='missing or ambiguous'):io.resolve(cfg)


def test_device_settings_are_native_db_preferences(tmp_path,monkeypatch):
    from app import auth
    monkeypatch.setattr(auth,'data_root',lambda:tmp_path)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    cfg=io.save(io.Settings(blocksize=256).model_dump())
    assert cfg['blocksize']==256 and io.load().blocksize==256
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    with pytest.raises(ValueError,match='native'):io.load()


@pytest.mark.skipif(__import__('os').getenv('MTA_TEST_PORTAUDIO_NULL')!='1',reason='Opt-in real PortAudio stream on configured virtual ALSA device')
def test_real_portaudio_cpp_callback_stream(core,monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    cfg=io.Settings(backend='portaudio',host_api='ALSA',output_name='default',latency=.01)
    device=io.PortAudioDevice(48000,4096,cfg)
    try:
        assert device.push(np.full((4096,2),.1,dtype=np.float32))
        device.finish();device.control('play')
        deadline=time.monotonic()+3
        while device.status()['position']<4096 and time.monotonic()<deadline:time.sleep(.01)
        assert device.status()['position']==4096
        assert device.status()['host_api']=='ALSA'
        device.control('pause');device.control('seek',0)
        assert device.status()['position']==0
    finally:device.close()


def test_compiled_capture_matrix_and_overflow_fail_closed(core):
    core.mta_capture_open_external.argtypes=[C.c_uint32,C.POINTER(C.c_float)];core.mta_capture_open_external.restype=C.c_void_p
    core.mta_capture_external_callback.restype=C.c_void_p
    core.mta_capture_read.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32];core.mta_capture_read.restype=C.c_int
    core.mta_capture_close.argtypes=[C.c_void_p]
    matrix=(C.c_float*12)(0,0,1,0,0,0,0,0,0,0,0,.5)
    handle=core.mta_capture_open_external(6,matrix);assert handle
    callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_ulong,C.c_void_p,C.c_ulong,C.c_void_p)(core.mta_capture_external_callback())
    try:
        source=np.tile([.1,.2,.3,.4,.5,.6],(8,1)).astype(np.float32)
        assert callback(source.ctypes.data,None,8,None,0,handle)==0
        result=np.zeros((8,2),dtype=np.float32)
        assert core.mta_capture_read(handle,result.ctypes.data,8)==8
        assert np.allclose(result,.3)
        assert callback(source.ctypes.data,None,8,None,2,handle)==2
        assert core.mta_capture_read(handle,result.ctypes.data,8)==-1
    finally:core.mta_capture_close(handle)


def test_compiled_duplex_shares_callback_and_detaches_before_free(core):
    from app.native_transport import bind_stream
    bind_stream(core)
    core.mta_transport_open_external.argtypes=[C.c_uint32,C.c_uint64,C.c_uint32,C.POINTER(C.c_float)];core.mta_transport_open_external.restype=C.c_void_p
    core.mta_transport_external_callback.restype=C.c_void_p
    core.mta_capture_open_external.argtypes=[C.c_uint32,C.POINTER(C.c_float)];core.mta_capture_open_external.restype=C.c_void_p
    core.mta_transport_capture_attach.argtypes=[C.c_void_p,C.c_void_p];core.mta_transport_capture_attach.restype=C.c_int
    core.mta_capture_read.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32];core.mta_capture_read.restype=C.c_int
    core.mta_capture_close.argtypes=[C.c_void_p]
    matrix=(C.c_float*4)(1,0,0,1)
    output=core.mta_transport_open_external(48000,32,2,matrix);capture=core.mta_capture_open_external(2,matrix)
    callback=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_void_p,C.c_ulong,C.c_void_p,C.c_ulong,C.c_void_p)(core.mta_transport_external_callback())
    try:
        assert core.mta_transport_capture_attach(output,capture)==0
        assert core.mta_transport_play(output)==0
        assert core.mta_transport_capture_attach(output,None)!=0
        source=np.full((8,2),.25,dtype=np.float32);audio=np.zeros_like(source)
        assert callback(source.ctypes.data,audio.ctypes.data,8,None,0,output)==0
        result=np.zeros_like(source)
        assert core.mta_capture_read(capture,result.ctypes.data,8)==8
        assert np.allclose(result,source)
        assert core.mta_transport_pause(output)==0
        assert core.mta_transport_capture_attach(output,None)==0
        core.mta_capture_close(capture);capture=None
        assert callback(None,audio.ctypes.data,8,None,0,output)==0
    finally:
        core.mta_transport_pause(output);core.mta_transport_capture_attach(output,None)
        if capture:core.mta_capture_close(capture)
        core.mta_transport_close(output)


def test_capture_cleanup_resets_owner_after_driver_failure(monkeypatch):
    from app import native_capture
    class Broken:
        def close(self):raise RuntimeError('Device disconnected')
    monkeypatch.setattr(native_capture,'_EXTERNAL',Broken())
    with pytest.raises(RuntimeError,match='disconnected'):native_capture.stop()
    assert native_capture._EXTERNAL is None
