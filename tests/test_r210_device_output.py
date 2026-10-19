"""Compiled native device lifecycle using the explicit clocked null test backend."""
import time
import numpy as np
import pytest
import soundfile as sf
from app import cpp_audio,native_transport as nt
from test_r210_cpp_audio_engine import compiled_core as device_core  # noqa: F401


@pytest.fixture
def device(request,tmp_path,monkeypatch):
    binary=request.getfixturevalue('device_core');monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(binary));cpp_audio._load.cache_clear()
    path=tmp_path/'àudio stereo.wav';sf.write(path,np.tile(np.array([[.25,-.5]],dtype=np.float32),(48000,1)),48000,subtype='FLOAT')
    with nt.Device(path,_test_null=True) as d:yield d


def test_null_backend_is_explicit_and_never_claims_physical_readiness(device):
    s=device.status();assert not s['physical'] and s['rate']==48000 and s['position']==0
    device.control('play');time.sleep(.07);s=device.control('pause')
    assert 0<s['position']<=s['total'] and s['peak_left']<=1
    position=s['position'];time.sleep(.03);assert device.status()['position']==position
    device.control('seek',250);assert device.status()['position']==12000
    device.control('play');time.sleep(.04);assert device.status()['position']>12000
    device.control('pause')
    device.control('gain',0);device.control('seek',0);device.control('play');time.sleep(.04)
    assert device.status()['peak_left']==0


def test_device_eof_seek_replay_and_validation(device):
    device.control('seek',980);device.control('play')
    deadline=time.monotonic()+2
    while not device.status()['ended'] and time.monotonic()<deadline:time.sleep(.01)
    assert device.status()['ended'] and device.status()['position']==48000
    device.control('seek',0);assert device.status()['position']<48000
    for bad in (-1,float('nan'),True):
        with pytest.raises(ValueError):device.control('seek',bad)
    with pytest.raises(ValueError):device.control('gain',float('inf'))
    device.close();device.close()
    with pytest.raises(RuntimeError):device.status()


def test_server_cannot_activate_native_device(monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    with pytest.raises(ValueError):nt.prepare_play('x')
