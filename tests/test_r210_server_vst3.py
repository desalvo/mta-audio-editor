"""Real headless plugin/audio streaming, isolation, ownership and browser transport."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name
import os
from pathlib import Path
import signal
import subprocess
import time

import numpy as np
import pytest
import soundfile as sf
from fastapi import Request
from fastapi.testclient import TestClient
from app import auth,storage,cpp_audio,audio_backend,server_vst3
from app.models import Track,InsertPlugin
from app.vst3_live import Session
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401
from test_r210_live_vst3 import real_plugin  # noqa: F401


@pytest.fixture
def server(tmp_path,monkeypatch,compiled_core,real_plugin):
    from app import main
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    monkeypatch.setattr(auth,'DATA_ROOT',None);monkeypatch.setattr(storage,'ROOT',tmp_path/'data')
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','test-vst3-server-password')
    auth.init_auth_db()
    with auth.db() as con:
        user=con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES('vstuser','vst@example.test','x',1,1,'user',1,1)").lastrowid
        other=con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES('vstother','other-vst@example.test','x',1,1,'user',1,1)").lastrowid
    project=storage.create_project('VST3 server',owner_user_id=user,sample_rate=48000)
    project.tracks=[Track(id='tone',name='Tone',filename='tone.wav',duration_ms=1000,channels=2,sample_rate=48000,
                          inserts=[InsertPlugin(id='tape',plugin='vst3',params={'path':str(real_plugin)})])]
    project.master_inserts=[InsertPlugin(id='master-tape',plugin='vst3',params={'path':str(real_plugin)})]
    source=storage.audio_path(project.id,'tone.wav')
    clock=np.arange(48000)/48000
    sf.write(source,np.column_stack([.15*np.sin(2*np.pi*211*clock),.13*np.sin(2*np.pi*331*clock)]),48000,subtype='FLOAT')
    storage.save_project(project,_skip_flac_conversion=True);audio_backend.select('cpp')
    manager=server_vst3.Sessions();monkeypatch.setattr(server_vst3,'sessions',manager)
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    def login(uid):
        req=Request({'type':'http','headers':[(b'user-agent',b'testclient')]})
        client.cookies.clear();client.cookies.set('mta_session',auth.create_session(uid,req))
    login(user)
    yield client,project,source,manager,login,user,other
    manager.shutdown()


def start(client,project,client_id='browser-client-0000000001'):
    result=client.post(f'/api/projects/{project.id}/vst3-live',json={'client_id':client_id,'cursor_ms':0})
    assert result.status_code in (200,202),result.text
    route=f'/api/projects/{project.id}/vst3-live/'+result.json()['session_id']
    state=result.json();deadline=time.monotonic()+20
    while state.get('state')=='preparing':
        assert time.monotonic()<deadline,'VST3 preparation timed out'
        result=client.get(route);assert result.status_code==200,result.text
        state=result.json();time.sleep(.01)
    assert not state.get('failed'),state
    return route,state


def test_server_catalog_inspection_pcm_update_seek_and_eof(server):
    client,p,_,manager,*_=server
    listing=client.get('/api/vst3/plugins').json()
    assert listing['scope']=='server' and listing['available'] and listing['live_available']
    from app.server_vst3_display import available as display_available
    assert listing['original_editor']==display_available()
    path=p.tracks[0].inserts[0].params['path']
    assert any(i['path']==path for i in listing['plugins'])
    info=client.get('/api/vst3/parameters',params={'path':path})
    assert info.status_code==200 and info.json()['parameters']
    route,status=start(client,p)
    assert status['plugin_count']==2 and not status['physical']
    first=client.post(route+'/pcm',json={'sequence':0,'frames':8192})
    assert first.status_code==200 and first.headers['cache-control']=='no-store'
    samples=np.frombuffer(first.content,dtype='<f4').reshape(-1,2)
    assert samples.shape==(8192,2) and np.isfinite(samples).all() and np.max(np.abs(samples))>.01
    assert first.headers['x-mta-start-frame']=='0'
    p.master_volume_db=-12;storage.save_project(p,_skip_flac_conversion=True)
    assert client.post(route+'/control',json={'action':'update'}).status_code==200
    token=route.split('/')[-1];entry=manager.entries[token]
    states=entry.session.request('states')['states'];assert len(states)==2
    parameter=next(k for k in states[0]['params'] if k not in ('path','__mta_state_b64'))
    p.tracks[0].inserts[0].params[parameter]=.31
    storage.save_project(p,_skip_flac_conversion=True)
    assert client.post(route+'/control',json={'action':'update'}).status_code==200
    updated=entry.session.request('states')['states']
    track_state=next(s for s in updated if s['route']=='tone')
    assert track_state['params'][parameter]==pytest.approx(.31,abs=.001)
    seek=client.post(route+'/control',json={'action':'seek','cursor_ms':700})
    assert seek.status_code==200 and seek.json()['status']['position']==33600
    data=client.post(route+'/pcm',json={'sequence':0,'frames':32768})
    assert data.status_code==200 and data.headers['x-mta-start-frame']=='33600'
    sequence=1
    while data.headers['x-mta-ended']!='1':
        data=client.post(route+'/pcm',json={'sequence':sequence,'frames':32768});sequence+=1
        assert data.status_code==200
    proc=entry.session.proc;root=entry.session.path
    assert client.delete(route).status_code==200
    assert proc.poll() is not None and not root.exists()
    assert client.get(route).status_code==404


def test_session_access_and_csrf_are_enforced(server):
    client,p,_,_,login,user,other=server
    route,_=start(client,p)
    # Admin project access must not grant access to another user's stream.
    login(auth.find_user('admin')['id']);assert client.get(route).status_code==404
    login(other);assert client.get(route).status_code==404
    assert client.post(route+'/pcm',json={'sequence':0}).status_code==404
    login(user)
    client.headers.pop('X-MTA-Request',None)
    assert client.post(route+'/pcm',json={'sequence':0}).status_code==403
    assert client.post(route+'/control',json={'action':'seek','cursor_ms':0}).status_code==403
    assert client.delete(route).status_code==403
    client.cookies.clear();assert client.get('/api/vst3/plugins').status_code==401


def test_capacity_replacement_expiry_and_cleanup(server,monkeypatch):
    client,p,_,manager,*_=server
    first,_=start(client,p)
    old=manager.entries[first.split('/')[-1]].session
    second,_=start(client,p)
    assert old.proc.poll() is not None and client.get(first).status_code==404
    monkeypatch.setenv('MTA_SERVER_VST3_MAX_SESSIONS','1')
    denied=client.post(f'/api/projects/{p.id}/vst3-live',json={'client_id':'another-browser-0001','cursor_ms':0})
    assert denied.status_code==429
    entry=manager.entries[second.split('/')[-1]];proc=entry.session.proc
    manager.reap(entry.touched+61)
    assert not manager.entries and proc.poll() is not None


def test_bad_sequence_is_not_replayed_or_silently_rendered_dry(server):
    client,p,_,manager,*_=server
    route,_=start(client,p)
    response=client.post(route+'/pcm',json={'sequence':100})
    assert response.status_code==409 and 'sequence' in response.text
    assert not manager.entries


def test_preparation_is_nonblocking_and_can_be_cancelled(server,monkeypatch):
    import threading
    client,p,_,manager,*_=server
    observed=threading.Event()
    class Preparing:
        def __init__(self,*args,cancelled,**kwargs):
            while not cancelled():time.sleep(.005)
            observed.set();raise RuntimeError('Preparation cancelled')
    monkeypatch.setattr(server_vst3,'Session',Preparing)
    now=time.monotonic()
    response=client.post(f'/api/projects/{p.id}/vst3-live',json={'client_id':'browser-client-0000000001'})
    assert response.status_code==202 and time.monotonic()-now<1
    route=f'/api/projects/{p.id}/vst3-live/'+response.json()['session_id']
    assert client.get(route).json()['state']=='preparing'
    assert client.post(route+'/pcm',json={'sequence':0}).status_code==409
    assert client.delete(route).status_code==200
    assert observed.wait(1) and not manager.entries


def test_preparation_failure_is_reported_and_released(server,tmp_path):
    client,p,_,manager,*_=server
    p.tracks[0].inserts[0].params={'path':str(tmp_path/'missing.vst3')}
    storage.save_project(p,_skip_flac_conversion=True)
    response=client.post(f'/api/projects/{p.id}/vst3-live',json={'client_id':'browser-client-0000000001'})
    assert response.status_code==202
    route=f'/api/projects/{p.id}/vst3-live/'+response.json()['session_id']
    deadline=time.monotonic()+15
    while True:
        status=client.get(route).json()
        if status.get('failed'):break
        assert time.monotonic()<deadline
        time.sleep(.02)
    assert status['state']=='failed' and 'not installed' in status['error']
    assert client.delete(route).status_code==200 and not manager.entries


def test_missing_current_engine_and_unsafe_plugin_are_explicit(server,tmp_path,monkeypatch):
    client,p,_,manager,*_=server
    audio_backend.select('current')
    response=client.post(f'/api/projects/{p.id}/vst3-live',json={'client_id':'browser-client-0000000001'})
    assert response.status_code==409 and not manager.entries
    # User-controlled project storage can never become a server executable root.
    plugin=storage.ROOT/'untrusted.vst3';plugin.mkdir()
    monkeypatch.setenv('MTA_VST3_PATHS',str(storage.ROOT))
    from app.vst3_host import validate_plugin_path
    with pytest.raises(ValueError,match='outside'):validate_plugin_path(str(plugin))
    response=client.get('/api/vst3/parameters',params={'path':str(plugin)})
    assert response.status_code==400


def test_headless_worker_stall_is_killed_as_a_group(server):
    if os.name!='posix':pytest.skip('POSIX process groups required')
    _,p,source,*_=server
    session=Session(p,[source],0,output='browser')
    try:
        assert session.status()['server_live_vst3'] and not session.status()['physical']
        os.kill(session.proc.pid,signal.SIGSTOP)
        now=time.monotonic()
        with pytest.raises(RuntimeError,match='timed out'):session.request('read',{'sequence':0,'frames':1024},timeout=.1)
        session.close();assert time.monotonic()-now<4
    finally:session.close()


def test_one_failed_user_worker_does_not_stop_another_user(server):
    import shutil
    client,p,source,manager,login,user,other=server
    first,_=start(client,p)
    q=storage.create_project('Another user',owner_user_id=other,sample_rate=48000)
    q.tracks=[p.tracks[0].model_copy(deep=True)]
    shutil.copyfile(source,storage.audio_path(q.id,q.tracks[0].filename))
    storage.save_project(q,_skip_flac_conversion=True)
    login(other);second,_=start(client,q)
    assert len(manager.entries)==2
    first_worker=manager.entries[first.split('/')[-1]].session.proc
    first_worker.kill();first_worker.wait(timeout=2)
    login(user)
    assert client.post(first+'/pcm',json={'sequence':0}).status_code==409
    login(other)
    response=client.post(second+'/pcm',json={'sequence':0,'frames':1024})
    assert response.status_code==200 and len(response.content)==1024*8
    assert len(manager.entries)==1


def test_server_plugin_render_export_reopens_saved_parameters(server,tmp_path):
    _,p,source,*_=server
    from app.audio_engine import render_mix
    from app.vst3_host import inspect_parameters
    values=inspect_parameters(Path(p.tracks[0].inserts[0].params['path']))
    p.tracks[0].inserts[0].params[values[0]['name']]=.4
    storage.save_project(p,_skip_flac_conversion=True)
    restored=storage.load_project(p.id)
    assert restored.tracks[0].inserts[0].params[values[0]['name']]==.4
    target=tmp_path/'vst3-export.wav'
    render_mix(restored,lambda *_:source,target,fmt='wav')
    data,rate=sf.read(target)
    assert rate==48000 and data.shape[1]==2 and np.isfinite(data).all() and np.max(np.abs(data))>.01


def test_browser_transport_full_script():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['node',str(root/'tests/server_vst3_browser.cjs')],cwd=root,text=True,capture_output=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
