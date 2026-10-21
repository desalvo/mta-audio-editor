"""Tempo-map, protocol precision, capture transaction and original editor regressions."""
# ruff: noqa: F811 -- imported pytest fixtures
import json
import subprocess
import time

import numpy as np
import pytest

from app.models import Project,Track,MidiNote,MidiSysEx,MidiUmp
from app.vst3_tempo_map import TempoMap
from app.midi import events,read_smf,write_smf,chase,Clock
from app.midi_ump import packet,vst_message
from test_r210_server_vst3 import server,start  # noqa: F401
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401
from test_r210_live_vst3 import real_plugin  # noqa: F401
from test_r210_midi import instrument_path  # noqa: F401


def track(**kwargs):return Track(id='keys',name='Keys',filename='anchor.wav',kind='midi',duration_ms=2000,**kwargs)


def test_zoned_ppq_continuity_bar_rephase_and_loop():
    data={'bpm':120,'base_bpm':120,'time_signature':'4/4','metronome_mode':'zones','markers':[{'id':'verse','time_ms':1000}],
          'metronome_manual_zone_bpms':{'START|verse':120,'verse|END':60},'metronome_manual_zone_signatures':{'verse|END':'3/4'}}
    tempo=TempoMap(data)
    assert tempo.position(999)[3]==pytest.approx(1.998)
    assert tempo.position(1000)==(60,3,4,2.,2.)
    assert tempo.position(2000)[3:]==(3.,2.)
    assert tempo.position(4000)[4]==5.
    assert tempo.boundaries(47000,2000,48000)==[47000,48000,49000]


def test_adaptive_map_and_browser_agree():
    data={'bpm':120,'base_bpm':120,'time_signature':'7/8','metronome_mode':'adaptive',
          'adaptive_tempo_map':[{'time_ms':0,'beat_index':0,'bpm':120},{'time_ms':500,'beat_index':1,'bpm':120},{'time_ms':1500,'beat_index':2,'bpm':60}]}
    tempo=TempoMap(data);assert tempo.position(1000)[3]==.75
    script='global.window=global;require("./app/static/midi_tempo.js");const m=new MtaTempoMap(JSON.parse(process.argv[1]));console.log(JSON.stringify([m.ppq(1000),m.time(.75)]))'
    values=json.loads(subprocess.check_output(['node','-e',script,json.dumps(data)],text=True))
    assert values==[.75,1000]


def test_compiled_clock_preserves_ppq_on_tempo_change(real_plugin):
    from pedalboard import load_plugin
    from app.vst3_transport import HostClock
    p=Project(id='tempo',title='Tempo',metronome_mode='zones',markers=[{'id':'m','time_ms':1000,'label':'M'}],metronome_manual_zone_bpms={'START|m':120,'m|END':60})
    host=HostClock(p,48000);plugin=load_plugin(str(real_plugin));host.apply(plugin,48000)
    assert plugin._mta_transport['bpm']==60 and plugin._mta_transport['ppq']==2
    plugin.process(np.zeros((2,480),np.float32),48000,reset=False)
    assert plugin._mta_transport['ppq']==pytest.approx(2.01)
    host.override(47000,True,0)
    assert list(host.segments(0,2000))==[(0,1000),(1000,2000)]


def test_sysex_smf_lossless_and_no_seek_replay():
    t=track(midi_sysex=[MidiSysEx(time_ms=100,data=[0xf0,0x7d,1,2,0xf7])])
    payload=write_smf(t);_,_,_,sysex=read_smf(payload,extended=True)
    assert sysex[0].data==t.midi_sysex[0].data
    assert not chase(events(t),500)
    assert Clock(t,48000,24000).read(10)==[]
    assert any(msg[0]==0xf0 for msg,_ in Clock(t,48000).read(10000))
    with pytest.raises(ValueError):MidiSysEx(data=[0xf0,128,0xf7])


def test_mpe_allocator_rpn_and_browser_equivalence():
    t=track(mpe_zone='lower',mpe_members=2,midi_notes=[MidiNote(start_ms=0,duration_ms=500,pitch=60),MidiNote(start_ms=50,duration_ms=500,pitch=64)])
    sequence=events(t)
    assert (0,[0xb0,100,6]) in sequence
    notes=[msg for _,msg in sequence if msg[0]&0xf0==0x90]
    assert [n[0]&15 for n in notes]==[1,2]
    script='const m=require("./app/static/midi_rules.js");console.log(JSON.stringify(m.events(JSON.parse(process.argv[1]))))'
    actual=json.loads(subprocess.check_output(['node','-e',script,t.model_dump_json()],text=True))
    assert [(v['at'],v['data']) for v in actual]==sequence
    t.mpe_members=1
    with pytest.raises(ValueError,match='polyphony'):events(t)


@pytest.mark.parametrize('value',[[0x40903c00],[0x40903c00,-1],[True],[0xffffffff],[0x40903c00,0x100000000]])
def test_ump_packet_limits(value):
    with pytest.raises(ValueError):packet(value)


def test_ump_envelope_keeps_every_word_bit_and_chase():
    words=[0x40903c00,0xfedc0000];message=vst_message(words)
    assert len(message)==17 and message[0]==0xf0 and message[-1]==0xf7
    recovered=[sum(message[6+w*5+i]<<(7*i) for i in range(5)) for w in range(2)]
    assert recovered==words
    t=track(midi_ump=[MidiUmp(time_ms=0,words=words),MidiUmp(time_ms=1000,words=[0x40803c00,0])])
    assert any(msg==message for msg,_ in Clock(t,48000,24000).read(1))
    from app.midi_ump import chase as ump_chase
    assert ump_chase([(0,words),(1000,[0x40803c00,0])],1500)==[]
    assert not any(msg==message for msg,_ in Clock(t,48000,72000).read(1))
    with pytest.raises(ValueError,match='lossless'):write_smf(t)


def test_real_ump_vsti_velocity_precision(instrument_path):
    from pedalboard import load_plugin
    plugin=load_plugin(str(instrument_path));sample=vst_message([0x40903c00,0xffff0000])
    audio=plugin.process([(sample,0.)],duration=.1,sample_rate=48000,num_channels=2,buffer_size=512,reset=False)
    assert np.isfinite(audio).all() and abs(audio).max()>1e-4


def test_native_capture_null_ring_and_cleanup(compiled_core,monkeypatch):
    from app import cpp_audio,native_capture
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    try:
        native_capture.start('',48000,_test_null=True)
        time.sleep(.03);value=native_capture.read()
        assert value['frames']>0
        import base64
        samples=np.frombuffer(base64.b64decode(value['pcm']),dtype='<f4')
        assert samples.size==value['frames']*2 and np.isfinite(samples).all()
    finally:native_capture.stop()
    with pytest.raises(ValueError):native_capture.read()


def test_capture_upload_durable_publish_permissions_and_sequence(server):
    from app import storage
    client,p,_,_,login,user,other=server
    base=f'/api/projects/{p.id}/audio-capture'
    opened=client.post(base,json={'rate':48000,'offset_ms':123});assert opened.status_code==200,opened.text
    url=base+'/'+opened.json()['capture_id']
    assert client.post(base,json={'rate':48000}).status_code==429
    pcm=np.zeros((4800,2),dtype='<f4');pcm[:,0]=np.sin(np.arange(4800)*.1)*.1
    assert client.post(url+'/pcm?sequence=1',content=pcm.tobytes()).status_code==409
    login(other);assert client.post(url+'/pcm?sequence=0',content=pcm.tobytes()).status_code==404
    login(user);assert client.post(url+'/pcm?sequence=0',content=pcm.tobytes()).status_code==200
    result=client.post(url+'/finish',json={'sequence':1,'name':'Recorded input'});assert result.status_code==200,result.text
    job=result.json();deadline=time.monotonic()+20
    while job.get('status') not in ('completed','failed'):
        assert time.monotonic()<deadline
        job=client.get('/api/media-jobs/'+result.json()['id']).json();time.sleep(.05)
    assert job['status']=='completed',job
    saved=storage.load_project(p.id);t=saved.tracks[-1]
    assert t.name=='Recorded input' and t.clips[0].timeline_start_ms==123
    assert storage.audio_path(p.id,t.filename).is_file()
    assert client.delete(url).status_code==404


def test_original_server_editor_live_pcm_authorization_and_persistence(server):
    from app.server_vst3_display import available
    if not available():pytest.skip('Install Xvfb/libXtst for original server editor integration')
    from app import storage
    client,p,_,manager,login,user,other=server
    route,_=start(client,p)
    previous=manager.entries[route.split('/')[-1]].session.request('states')['states'][0]['params']
    opened=client.post(route+'/editor',json={'route':'tone','insert':'tape'});assert opened.status_code==200,opened.text
    url=route+'/editor/'+opened.json()['editor_id'];time.sleep(.3)
    assert client.post(route+'/editor',json={'route':'tone','insert':'tape'}).status_code==409
    login(other);assert client.get(url+'/frame').status_code==404
    login(user)
    frame=client.get(url+'/frame');assert frame.status_code==200 and frame.content.startswith(b'\xff\xd8')
    assert client.post(url+'/input',json={'events':[{'type':'move','x':-1,'y':0}]}).status_code==422
    result=client.post(route+'/pcm',json={'sequence':0,'frames':4096});assert result.status_code==200
    # Actual original rotary control, not a synthetic parameter API.
    inputs=[{'type':'move','x':68,'y':210},{'type':'button','button':1,'down':True},{'type':'move','x':68,'y':150},{'type':'button','button':1,'down':False}]
    assert client.post(url+'/input',json={'events':inputs}).status_code==200
    time.sleep(.15)
    closed=client.post(url+'/state',json={'close':True});assert closed.status_code==200,closed.text
    assert closed.json()['state']=='completed'
    saved=storage.load_project(p.id).tracks[0].inserts[0].params
    assert saved['__mta_state_b64'] and any(k not in ('path','__mta_state_b64') for k in saved)
    assert saved['input_gain']!=previous['input_gain'],'The actual original rotary control must change the running plugin'
    second=client.post(route+'/editor',json={'route':'tone','insert':'tape'});assert second.status_code==200,second.text
    again=client.post(route+'/editor/'+second.json()['editor_id']+'/state',json={'close':True});assert again.status_code==200,again.text
    assert again.json()['state']=='completed'
    client.delete(route)
    assert not manager.entries


def test_sidechain_live_offline_same_graph(compiled_core,tmp_path,monkeypatch):
    import os
    from pathlib import Path
    plugin=os.getenv('MTA_TEST_SIDECHAIN_PLUGIN')
    if not plugin:pytest.skip('Build tests/vst3_probe and set MTA_TEST_SIDECHAIN_PLUGIN')
    from app import cpp_audio,audio_backend,auth
    import soundfile as sf
    from app.models import InsertPlugin
    from app.vst3_live_graph import Graph
    from app.vst3_sidechain import render
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'data'));monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true');monkeypatch.setattr(auth,'DATA_ROOT',None)
    monkeypatch.setenv('MTA_VST3_PATHS',str(Path(plugin).parent));audio_backend.select('cpp')
    first=tmp_path/'a.wav';second=tmp_path/'b.wav'
    sf.write(first,np.full((48000,2),.2,np.float32),48000,subtype='FLOAT');sf.write(second,np.full((48000,2),.5,np.float32),48000,subtype='FLOAT')
    target=Track(id='a',name='A',filename='a.wav',duration_ms=1000,channels=2,inserts=[InsertPlugin(id='fx',plugin='vst3',params={'path':plugin},sidechain_track_id='b')])
    key=Track(id='b',name='B',filename='b.wav',duration_ms=1000,channels=2,mute=True)
    project=Project(id='sc',title='SC',sample_rate=48000,tracks=[target,key])
    g=Graph(project,[first,second],tail_seconds=0)
    try:np.testing.assert_allclose(g.read(4096),.1,atol=1e-6)
    finally:g.close()
    out=tmp_path/'out.wav';render(project,lambda _,name:tmp_path/name,out)
    pcm,rate=sf.read(out,dtype='float32');assert rate==48000
    np.testing.assert_allclose(pcm[:48000],.1,atol=1e-6)
    assert np.count_nonzero(pcm[48000:])==0
    # Prefader audio is not stretched yet, but tempo-synchronised plugins must
    # still see the source BPM, so the outer project stretch is applied once.
    from app import vst3_live
    real_session=vst3_live.Session;observed=[]
    class CheckedSession(real_session):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);observed.append(self.status()['host_bpm'])
    monkeypatch.setattr(vst3_live,'Session',CheckedSession)
    project.bpm=180;project.base_bpm=120
    render(project,lambda _,name:tmp_path/name,tmp_path/'prefader.wav',track_id='a',prefader=True)
    assert observed==[120]
    rendered,rate=sf.read(tmp_path/'prefader.wav');assert len(rendered)>=48000



def test_original_editor_requires_confinement_and_private_env(monkeypatch,tmp_path):
    from app import vst3_sandbox
    monkeypatch.setenv('MTA_SMTP_PASSWORD','do-not-inherit');monkeypatch.setenv('MTA_ADMIN_PASSWORD','do-not-inherit')
    monkeypatch.setenv('MTA_DATA_DIR','/private/projects')
    safe=vst3_sandbox.worker_environment()
    assert 'MTA_SMTP_PASSWORD' not in safe and 'MTA_ADMIN_PASSWORD' not in safe
    # monkeypatch restores the complete environment after the scoped scrub.
    with monkeypatch.context() as patch:
        import os
        patch.setattr(os,'environ',dict(os.environ))
        vst3_sandbox.private_environment(tmp_path)
        assert 'MTA_SMTP_PASSWORD' not in os.environ and 'MTA_ADMIN_PASSWORD' not in os.environ
        assert os.environ['MTA_DATA_DIR']=='/private/projects'
    monkeypatch.setattr(vst3_sandbox,'available',lambda:False)
    with pytest.raises(RuntimeError,match='Landlock'):vst3_sandbox.confine(tmp_path,[],[])
