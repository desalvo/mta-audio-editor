import ctypes
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from app.main import app


def test_ai_catalog_endpoint():
    client = TestClient(app)
    response = client.get('/api/ai-arranger/catalog')
    # Authentication depends on configured mode: never allow anonymous bypass in production.
    assert response.status_code in (200, 401)
    if response.status_code == 200:
        assert response.json()['generation_available'] is False


def test_native_pdc_abi(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'native/audio_core/audio_core.cpp'
    lib = tmp_path / 'libplanner.so'
    subprocess.run(['c++', '-std=c++20', '-shared', '-fPIC', '-O2', str(source), '-o', str(lib)], check=True)
    class Route(ctypes.Structure):
        _fields_ = [('plugin_frames',ctypes.c_uint32),('ipc_frames',ctypes.c_uint32),('enabled',ctypes.c_uint32)]
    class Result(ctypes.Structure):
        _fields_ = [('target_frames',ctypes.c_uint32),('route_count',ctypes.c_uint32)]
    fn = ctypes.CDLL(str(lib)).mta_vst3_plan_latency
    fn.argtypes = [ctypes.POINTER(Route),ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(Result)]
    fn.restype=ctypes.c_int
    routes = (Route*3)(Route(256,32,1),Route(32,32,1),Route(100,0,0))
    delay = (ctypes.c_uint32*3)()
    result=Result()
    assert fn(routes,3,delay,ctypes.byref(result)) == 0
    assert list(delay)==[0,224,0]
    assert (result.target_frames,result.route_count)==(288,3)
    bad=(Route*1)(Route(1048576,1,1))
    result.target_frames=99
    assert fn(bad,1,delay,ctypes.byref(result))==-2
    assert result.target_frames==99
    bad[0].enabled=2
    assert fn(bad,1,delay,ctypes.byref(result))==-1
