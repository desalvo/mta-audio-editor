"""Server engine selection, real C++ rendering, admin/CSRF and package delivery."""
# ruff: noqa: F811 -- imported pytest fixture is intentionally injected by name
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi import Request
from fastapi.testclient import TestClient
from app import audio_backend as backend, audio_engine, auth, cpp_audio
from app.models import Project, Track
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401


@pytest.fixture
def server(tmp_path, monkeypatch, compiled_core):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'false')
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH', str(compiled_core))
    monkeypatch.setattr(auth, 'DATA_ROOT', None)
    cpp_audio._load.cache_clear()
    return tmp_path


def test_server_renders_use_selected_core_and_snapshot(server, monkeypatch):
    rate=48000
    source=server/'source.wav'
    sf.write(source, np.full((4800,2), .2), rate, subtype='PCM_24')
    track=Track(id='a',name='a',filename=source.name,channels=2,sample_rate=rate,duration_ms=100,gain_db=4,volume_db=-2,pan=.3)
    project=Project(id='112233aabbcc',title='server',sample_rate=rate,tracks=[track],master_volume_db=-3,master_fade_enabled=True,master_fade_in_ms=10,master_fade_out_ms=20)
    ref=server/'ref.wav';out=server/'cpp.wav'
    audio_engine.render_mix(project,lambda *_:source,ref,fmt='wav',wav_bit_depth=32)
    state=backend.select('cpp')
    assert state['scope']=='server' and state['transport']=='browser'
    assert not state['native_transport_available'] and not state['native_host_ready']
    calls=[];original=cpp_audio.Core.mix
    def mix(self,*args,**kwargs):
        calls.append(1)
        return original(self,*args,**kwargs)
    monkeypatch.setattr(cpp_audio.Core,'mix',mix)
    audio_engine.render_mix(project,lambda *_:source,out,fmt='wav',wav_bit_depth=32)
    assert calls
    np.testing.assert_allclose(sf.read(ref)[0],sf.read(out)[0],atol=3e-5,rtol=1e-4)
    assert (auth.data_root()/'server-audio-engine.json').is_file()
    assert not (auth.data_root()/'native-audio-engine.json').exists()
    with backend.snapshot_context():
        identity=backend.identity();backend.select('current')
        assert backend.selected()=='cpp' and backend.identity()==identity
    assert backend.selected()=='current'


def test_server_api_requires_admin_and_csrf(server,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','test-server-password')
    auth.init_auth_db();admin=auth.find_user('admin')['id']
    with auth.db() as con:
        user=con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES('dspuser','dsp@example.test','x',1,1,'user',1,1)").lastrowid
    client=TestClient(main.app);url='/api/admin/audio-engine'
    assert client.get(url).status_code==401
    request=Request({'type':'http','headers':[(b'user-agent',b'testclient')]})
    client.cookies.set('mta_session',auth.create_session(user,request))
    assert client.get(url).status_code==403
    assert client.put(url,json={'engine':'cpp'},headers={'x-mta-request':'1'}).status_code==403
    client.cookies.set('mta_session',auth.create_session(admin,request))
    assert client.get(url).json()['requested']=='current'
    assert client.put(url,json={'engine':'cpp'}).status_code==403
    headers={'x-mta-request':'1'}
    assert client.put(url,json={'engine':'bad'},headers=headers).status_code==422
    assert client.put(url,json={'engine':'cpp'},headers=headers).json()['requested']=='cpp'
    monkeypatch.setattr('app.native_dsp._candidate_paths',lambda:[])
    cpp_audio._load.cache_clear()
    assert client.put(url,json={'engine':'cpp'},headers=headers).status_code==409
    assert client.get(url).json()['requested']=='cpp'
    assert client.put(url,json={'engine':'current'},headers=headers).status_code==200


def test_server_staging_builds_and_ships_target_core(server,monkeypatch,compiled_core):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('server_prepare',root/'scripts/server_packages/prepare_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    commands=[];monkeypatch.setattr(module,'run',lambda cmd:commands.append(cmd))
    # The real build is deliberately exercised; only network wheel download is omitted.
    module.prepare(root,server/'stage',root/'requirements.txt')
    target=server/'stage/application/bin/libmta_audio_core.so'
    assert target.is_file()
    import ctypes
    lib=ctypes.CDLL(str(target));lib.mta_audio_core_abi.restype=ctypes.c_uint
    assert lib.mta_audio_core_abi()==1
    assert any('download' in cmd for cmd in commands)
    monkeypatch.delenv('MTA_AUDIO_CORE_PATH',raising=False)
    import app.native_dsp as dsp
    # Installed server / frozen lookup includes the shared application bin directory.
    monkeypatch.setattr(dsp,'__file__',str(server/'stage/application/app/native_dsp.py'))
    assert target in dsp._candidate_paths()
    for path in ('Dockerfile','.github/workflows/server-native-runtime-validation.yml'):
        assert 'cmake' in (root/path).read_text()


def test_server_offline_proof_binds_core_bytes(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('server_verify',root/'scripts/server_packages/verify_offline_runtime.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (tmp_path/'application/bin').mkdir(parents=True)
    (tmp_path/'wheelhouse.lock.json').write_text('{}')
    (tmp_path/'application/requirements.txt').write_text('')
    lib=tmp_path/'application/bin/libmta_audio_core.so';lib.write_bytes(b'one')
    proof=module.metadata(tmp_path)
    (tmp_path/'offline-runtime-proof.json').write_text(json.dumps(proof))
    module.check_proof(tmp_path);lib.write_bytes(b'two')
    with pytest.raises(ValueError,match='stale'):module.check_proof(tmp_path)
