"""Real compiled DSP, renderer equivalence, persisted choice and pre-launch paths."""
import ctypes as ct
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pytest
import soundfile as sf
from app import audio_backend as backend,cpp_audio,audio_engine,auth
from app.models import Project,Track,Clip,InsertPlugin


@pytest.fixture(scope='module')
def compiled_core(tmp_path_factory, compiled_audio_core_build):
    # A unique library path retains per-module C++ globals and DLL isolation.
    target = tmp_path_factory.mktemp('cpp-build') / compiled_audio_core_build.name
    shutil.copy2(compiled_audio_core_build, target)
    return target


@pytest.fixture
def engine(tmp_path,monkeypatch,compiled_core):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true');monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));monkeypatch.setattr(auth,'DATA_ROOT',None)
    cpp_audio._load.cache_clear()
    return tmp_path


def test_engine_selection_persists_and_never_enables_transport(engine):
    assert backend.requested()=='current'
    s=backend.select('cpp');assert s['requested']=='cpp' and s['cpp_available']
    assert s['transport']=='native-device' and not s['native_transport_ready'] and not s['native_host_ready']
    assert backend.requested()=='cpp'
    backend.select('current');assert backend.requested()=='current'
    with pytest.raises(ValueError):backend.select('unknown')


def test_missing_core_does_not_change_preference_or_overwrite_export(engine,monkeypatch):
    monkeypatch.setattr('app.native_dsp._candidate_paths',lambda:[])
    with pytest.raises(RuntimeError,match='unavailable'):backend.select('cpp')
    assert backend.requested()=='current'
    path=Path(os.environ['MTA_DATA_DIR'])/'native-audio-engine.json';path.parent.mkdir(exist_ok=True)
    path.write_text('{"engine":"cpp"}')
    assert backend.status()['requested']=='cpp' and not backend.status()['cpp_available']
    target=engine/'saved.wav';target.write_bytes(b'keep this file')
    with pytest.raises(RuntimeError,match='unavailable'):audio_engine.render_track(Track(id='t',name='t',filename='t.wav',duration_ms=1000),engine/'missing.wav',target)
    assert target.read_bytes()==b'keep this file'
    backend.select('current')


def test_server_never_uses_native_preference(engine,monkeypatch):
    backend.select('cpp');monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    assert backend.requested()=='current'
    state=backend.select('cpp')
    assert state['scope']=='server' and state['transport']=='browser'
    assert not state['native_transport_available'] and not state['native_transport_ready']
    assert backend.requested()=='cpp'
    backend.select('current');monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    assert backend.requested()=='cpp'


def test_core_mix_balance_solo_and_overflow_atomic(engine):
    core=cpp_audio.runtime();a=np.array([[1,2],[3,4]],dtype=np.float32);b=a*.5
    np.testing.assert_allclose(core.mix([a,b],[1,2],[-1,1],[1,1]),[[1,2],[3,4]])
    assert np.count_nonzero(core.mix([a,b],[1,2],[0,0],[0,0]))==0
    original=(ct.c_float*4)(8,9,10,11);src=(ct.c_float*4)(1,float('nan'),2,3)
    ptr=(cpp_audio.FP*1)(ct.cast(src,cpp_audio.FP));g=(ct.c_float*1)(1);pan=(ct.c_float*1)(0);enabled=(ct.c_ubyte*1)(1)
    assert core.lib.mta_render_mix(ptr,g,pan,enabled,1,original,2)==-2
    assert list(original)==[8,9,10,11]
    data=np.array([[1,np.inf]],dtype=np.float32);old=data.copy()
    with pytest.raises(RuntimeError):core.gain(data,2)
    np.testing.assert_array_equal(data,old)
    alias=(cpp_audio.FP*1)(ct.cast(original,cpp_audio.FP))
    assert core.lib.mta_render_mix(alias,g,pan,enabled,1,original,2)==-1


def test_envelope_is_block_independent_and_keeps_headroom(engine):
    core=cpp_audio.runtime();n=13003
    def run(block):
        data=np.full((n,2),2,dtype=np.float32)
        for start in range(0,n,block):core.envelope(data[start:start+block],start,n,2,7000,18000)
        return data
    a=run(512);np.testing.assert_array_equal(a,run(4096))
    assert a[0,0]==0 and a.max()>1
    assert a[-1,0]==pytest.approx(4/18000,abs=1e-9)


def test_render_snapshot_and_atomic_failure(engine):
    backend.select('cpp');target=engine/'out.wav';target.write_bytes(b'old')
    @backend.render_scope
    def nested(out):out.write_text(backend.selected())
    @backend.render_scope
    def render(out):
        assert backend.selected()=='cpp';backend.select('current');nested(out)
    render(target);assert target.read_text()=='cpp' and backend.requested()=='current'
    backend.select('cpp')
    @backend.render_scope
    def broken(out):out.write_bytes(b'partial');raise RuntimeError('late failure')
    with pytest.raises(RuntimeError):broken(target)
    assert target.read_text()=='cpp'


@pytest.mark.parametrize('rate',[44100,48000,96000])
@pytest.mark.parametrize('pan',[-1,-.35,0,.5,1])
def test_real_render_matches_current_gain_mix_master_fades(engine,rate,pan):
    n=round(rate*.19);clock=np.arange(n)/rate
    source=engine/'source.wav';sf.write(source,np.column_stack([.15*np.sin(2*np.pi*313*clock),.13*np.cos(2*np.pi*457*clock)]),rate,subtype='PCM_24')
    track=Track(id='a',name='a',filename=source.name,channels=2,sample_rate=rate,duration_ms=190,gain_db=4,volume_db=-2,pan=pan,
                clips=[Clip(id='c',source_start_ms=10,source_end_ms=180,timeline_start_ms=15)])
    other=track.model_copy(deep=True);other.id='b';other.volume_db=-8;other.pan=-pan;other.delay_ms=-8
    project=Project(id='112233aabbcc',title='test',sample_rate=rate,tracks=[track,other],master_volume_db=-3,master_fade_enabled=True,master_fade_in_ms=33,master_fade_out_ms=100)
    reference=engine/'current.wav';candidate=engine/'cpp.wav'
    backend.select('current');audio_engine.render_mix(project,lambda *_:source,reference,fmt='wav',wav_bit_depth=32)
    backend.select('cpp');audio_engine.render_mix(project,lambda *_:source,candidate,fmt='wav',wav_bit_depth=32)
    a,ar=sf.read(reference,dtype='float32',always_2d=True);b,br=sf.read(candidate,dtype='float32',always_2d=True)
    assert ar==br==rate and a.shape==b.shape
    np.testing.assert_allclose(a,b,atol=3e-5,rtol=1e-4)


def test_input_gain_precedes_nonlinear_inserts_and_master_is_processed_once(engine):
    rate=48000;source=engine/'clip.wav';signal=np.full((4800,2),.23,dtype=np.float32);sf.write(source,signal,rate,subtype='PCM_24')
    # Built-in clipper is nonlinear; gain after inserts would produce a different result.
    track=Track(id='a',name='a',filename=source.name,channels=2,sample_rate=rate,duration_ms=100,gain_db=6,inserts=[InsertPlugin(id='compress',plugin='compressor',preset='default')])
    project=Project(id='112233aabbcc',title='test',sample_rate=rate,tracks=[track],master_volume_db=-6)
    expected=engine/'master-current.wav';out=engine/'master.wav'
    backend.select('current');audio_engine.render_mix(project,lambda *_:source,expected,fmt='wav',wav_bit_depth=32)
    backend.select('cpp');audio_engine.render_mix(project,lambda *_:source,out,fmt='wav',wav_bit_depth=32)
    data,_=sf.read(out,dtype='float32');reference,_=sf.read(expected,dtype='float32')
    np.testing.assert_allclose(data,reference,atol=3e-5,rtol=1e-4)


def test_prelaunch_native_paths_and_mac_import_without_data(tmp_path,monkeypatch):
    from app import runtime_paths
    monkeypatch.delenv('MTA_DATA_DIR',raising=False);monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.setenv('MTA_NATIVE_DATA_DIR',str(tmp_path/'native'))
    assert runtime_paths.application_data_root()==tmp_path/'native'
    monkeypatch.delenv('MTA_NATIVE_DATA_DIR');monkeypatch.setattr(runtime_paths.sys,'platform','darwin')
    assert str(runtime_paths.application_data_root()).endswith('/Library/Application Support/MTA Audio Editor')
    env={**os.environ,'MTA_NATIVE_DATA_DIR':str(tmp_path/'subprocess'),'MTA_NATIVE_SINGLE_USER':'true'};env.pop('MTA_DATA_DIR',None)
    script="""from pathlib import Path
original=Path.mkdir
def guard(self,*a,**kw):
 if str(self).startswith('/data'):raise RuntimeError('forbidden server path')
 return original(self,*a,**kw)
Path.mkdir=guard
from app import storage,auth
assert storage.ROOT==auth.data_root()
assert '/data/projects'!=str(storage.ROOT)
print(storage.ROOT)
"""
    subprocess.run([sys.executable,'-c',script],check=True,env=env,capture_output=True,text=True)


def test_preference_probe_does_not_import_ml_or_audio_stack(engine):
    env={**os.environ}
    script="""import sys
from app.audio_backend import status
value=status()
assert value['cpp_available']
assert not {'numpy','soundfile','torch','librosa'} & set(sys.modules)
"""
    subprocess.run([sys.executable,'-c',script],check=True,env=env,capture_output=True,text=True)


def test_native_bridge_engine_setting_and_existing_settings_are_separate(engine,monkeypatch):
    from native import mta_audio_editor_native as launcher
    monkeypatch.setattr(launcher,'_data_root',lambda:Path(os.environ['MTA_DATA_DIR']))
    api=launcher.NativeApi();api.set_native_settings(777,False,'early','en')
    api.set_audio_engine('cpp');cfg=api.get_native_settings()
    assert cfg['max_upload_mb']==777 and cfg['audio_engine']['requested']=='cpp'
    assert cfg['language']=='en' and not cfg['autosave_enabled']
    assert json.loads((Path(os.environ['MTA_DATA_DIR'])/'native-settings.json').read_text())['update_channel']=='early'


@pytest.mark.parametrize('channels,solo,fade',[(1,False,0),(1,True,300),(2,True,300)])
def test_real_mono_solo_long_fade_and_master_inserts(engine,channels,solo,fade):
    rate=48000;clock=np.arange(7200)/rate;samples=.12*np.sin(2*np.pi*200*clock)
    source=engine/'mono.wav';sf.write(source,samples if channels==1 else np.column_stack([samples,samples]),rate,subtype='PCM_24')
    a=Track(id='a',name='a',filename=source.name,channels=channels,sample_rate=rate,duration_ms=150,gain_db=3,solo=solo)
    b=a.model_copy(deep=True);b.id='b';b.solo=False;b.volume_db=-12
    p=Project(id='112233aabbcc',title='mono',sample_rate=rate,tracks=[a,b],master_fade_enabled=bool(fade),master_fade_in_ms=fade,master_fade_out_ms=fade,
              master_inserts=[InsertPlugin(id='m',plugin='amplify',preset='minus-6db')])
    p.bpm=100;p.base_bpm=120
    paths=[]
    for mode in ('current','cpp'):
        backend.select(mode);out=engine/(mode+'-mono.wav');audio_engine.render_mix(p,lambda *_:source,out,fmt='wav',wav_bit_depth=32);paths.append(out)
    x,_=sf.read(paths[0]);y,_=sf.read(paths[1]);assert x.shape==y.shape
    # The shared FFmpeg WSOLA stage can choose a neighboring overlap for tiny
    # pre-stretch rounding differences. Bound both RMS error and transient peak.
    assert float(np.sqrt(np.mean((x-y)**2)))<3e-5
    assert float(np.max(np.abs(x-y)))<.002


def test_cpp_respects_post_master_bounce_route(engine):
    source=engine/'s.wav';sf.write(source,np.full((4800,2),.1,dtype=np.float32),48000,subtype='PCM_24')
    t=Track(id='a',name='a',filename=source.name,channels=2,sample_rate=48000,duration_ms=100)
    post=t.model_copy(deep=True);post.id='post';post.master_bypass=True
    p=Project(id='112233aabbcc',title='post',sample_rate=48000,tracks=[t,post],master_volume_db=-6,
              master_inserts=[InsertPlugin(id='m',plugin='amplify',preset='minus-6db')])
    paths=[]
    for mode in ('current','cpp'):
        backend.select(mode);out=engine/(mode+'-post.wav');audio_engine.render_mix(p,lambda *_:source,out,fmt='wav',wav_bit_depth=32);paths.append(out)
    x,_=sf.read(paths[0]);y,_=sf.read(paths[1]);assert x.shape==y.shape
    np.testing.assert_allclose(x,y,atol=3e-5,rtol=1e-4)


def test_routes_and_native_settings_source_keep_real_capabilities(engine,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    client=TestClient(main.app);assert client.get('/api/native/audio-engine').status_code==404
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True);monkeypatch.setattr(main,'require_user',lambda req:{'id':1})
    result=client.get('/api/native/audio-engine');assert result.status_code==200
    assert result.json()['transport']=='current' and not result.json()['native_host_ready']


def test_noncontiguous_pcm_is_rejected_before_native_write(engine):
    samples=np.ones((10,4),dtype=np.float32);view=samples[:,::2]
    with pytest.raises(ValueError,match='PCM block'):cpp_audio.runtime().gain(view,2)
    np.testing.assert_array_equal(samples,1)


def test_mac_ci_has_explicit_writable_paths_and_both_native_builds_compile_cpp():
    workflow=(Path(__file__).parents[1]/'.github/workflows/ci-cd.yml').read_text()
    mac=workflow.split('- name: macOS native project save regressions',1)[1].split('- name: Generate native build id',1)[0]
    assert 'MTA_DATA_DIR: ${{ runner.temp }}/mta-native-project-tests' in mac
    assert 'MTA_NATIVE_DATA_DIR:' in mac
    assert 'Build and verify Windows C++ audio DSP' in workflow and 'Build and verify macOS C++ audio DSP' in workflow
    assert workflow.count('python scripts/build_audio_core.py')==2


def test_preview_cache_keeps_backend_snapshot_during_engine_change(engine,monkeypatch):
    from app import main
    source=engine/'preview-source.wav';sf.write(source,np.full((4800,2),.1,dtype=np.float32),48000,subtype='PCM_24')
    t=Track(id='a',name='a',filename=source.name,channels=2,sample_rate=48000,duration_ms=100,gain_db=3,
            inserts=[InsertPlugin(id='fx',plugin='amplify',preset='minus-3db')])
    p=Project(id='112233aabbcc',title='snapshot',sample_rate=48000,tracks=[t])
    monkeypatch.setattr(main,'_project_for_actor',lambda *a:p)
    monkeypatch.setattr(main,'audio_path',lambda *a:source)
    monkeypatch.setattr(main,'session_preview_dir',lambda *a:engine/'previews')
    original=main.render_track_export;seen=[]
    def changed(*a,**kw):
        before=backend.selected();backend.select('current');seen.append((before,backend.selected()))
        return original(*a,**kw)
    monkeypatch.setattr(main,'render_track_export',changed)
    backend.select('cpp')
    cpp_response=main.preview_track(p.id,t.id,None,render=True)
    assert seen==[('cpp','cpp')]
    current_response=main.preview_track(p.id,t.id,None,render=True)
    assert cpp_response.path!=current_response.path
    assert Path(cpp_response.path).is_file() and Path(current_response.path).is_file()
