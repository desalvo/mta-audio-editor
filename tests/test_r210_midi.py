"""SMF and sample-clock regressions, instrument graph and authorized project I/O."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name
import io
import os
from pathlib import Path

import mido
import numpy as np
import pytest
import soundfile as sf

from app.models import Track,Clip,MidiNote,MidiControl,InsertPlugin,Project
from app.midi import read_smf,write_smf,Clock,chase,events
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401
from test_r210_server_vst3 import server  # noqa: F401
from test_r210_live_vst3 import real_plugin  # noqa: F401


def track(**kwargs):
    return Track(id='midi',name='MIDI',filename='anchor.wav',kind='midi',channels=2,duration_ms=3000,**kwargs)


def test_smf_tempo_map_running_notes_and_controls_roundtrip():
    midi=mido.MidiFile();part=mido.MidiTrack();midi.tracks.append(part)
    part.extend([mido.MetaMessage('set_tempo',tempo=500000),mido.Message('program_change',program=7),mido.Message('note_on',note=60,velocity=90),mido.MetaMessage('set_tempo',tempo=1000000,time=480),mido.Message('note_off',note=60,time=480),mido.Message('pitchwheel',pitch=123)])
    file=io.BytesIO();midi.save(file=file)
    notes,controls,duration=read_smf(file.getvalue())
    assert duration==1500 and len(notes)==1 and notes[0].duration_ms==1500
    t=track(midi_notes=notes,midi_controls=controls)
    again,ctl,_=read_smf(write_smf(t,123.45))
    assert again[0].duration_ms==pytest.approx(1500,abs=1)
    assert [x.data for x in ctl][:2]==[x.data for x in controls]


def test_clock_boundaries_chase_delay_and_clip_trim():
    t=track(midi_notes=[MidiNote(start_ms=0,duration_ms=1000,pitch=60)],delay_ms=100,
        clips=[Clip(id='clip',source_start_ms=300,source_end_ms=800,timeline_start_ms=0)])
    clock=Clock(t,48000,start_frame=round(.3*48000))
    msg=clock.read(512)
    assert (bytes([0x90,60,100]),0) in msg
    end=Clock(t,48000,start_frame=28800).read(1)
    assert any(m[1]==64 and m[2]==0 for m,_ in end if len(m)==3)
    t=track(midi_notes=[MidiNote(start_ms=0,duration_ms=10)])
    c=Clock(t,48000);assert c.read(480)==[(bytes([0x90,60,100]),0)]
    assert c.read(1)==[(bytes([0x80,60,0]),0)]


def test_sustain_seek_restores_released_but_pedalled_voice():
    data=[(0,[0xB0,64,127]),(0,[0x90,60,91]),(100,[0x80,60,0]),(1000,[0xB0,64,0])]
    assert chase(data,500)==[[0xB0,64,127],[0x90,60,91],[0x80,60,0]]
    assert chase(data,1500)==[[0xB0,64,0]]


@pytest.mark.parametrize('payload',[b'',b'not midi',b'MThd'+b'\0'*20])
def test_reject_invalid_smf(payload):
    with pytest.raises((ValueError,EOFError,OSError)):read_smf(payload)


def test_reject_smpte_type2_sysex_and_nonfinite():
    midi=mido.MidiFile(type=2);midi.tracks.append(mido.MidiTrack());out=io.BytesIO();midi.save(file=out)
    with pytest.raises(ValueError):read_smf(out.getvalue())
    for data in ([0xF0,1,2],[0x90,60,1],[0xB0,128,0]):
        with pytest.raises(ValueError):MidiControl(data=data)
    with pytest.raises(ValueError):MidiNote(start_ms=float('nan'))


def test_midi_api_persistence_ownership_csrf_and_export(server):
    from app import storage
    client,p,_,_,login,user,other=server
    created=client.post(f'/api/projects/{p.id}/midi',json={'name':'Piano','notes':[{'start_ms':0,'duration_ms':500,'pitch':64}]})
    assert created.status_code==200,created.text
    item=created.json()['tracks'][-1];assert item['kind']=='midi'
    saved=storage.load_project(p.id);assert saved.tracks[-1].midi_notes[0].pitch==64
    assert storage.audio_path(p.id,item['filename']).is_file()
    export=client.get(f'/api/projects/{p.id}/midi/{item["id"]}/export');assert export.status_code==200
    assert read_smf(export.content)[0][0].pitch==64
    imported=client.post(f'/api/projects/{p.id}/midi/import?name=again.mid',content=export.content,headers={'Content-Type':'audio/midi'})
    assert imported.status_code==200,imported.text
    assert imported.json()['tracks'][-1]['midi_notes'][0]['pitch']==64
    changed=client.put(f'/api/projects/{p.id}/midi/{item["id"]}',json={'name':'Changed','notes':[{'pitch':67,'duration_ms':750}]})
    assert changed.status_code==200 and storage.load_project(p.id).tracks[-2].midi_notes[0].pitch==67
    rejected=client.put(f'/api/projects/{p.id}/midi/{item["id"]}',json={'name':'Unsafe','instrument':{'id':'i','plugin':'vst3','params':{'path':'/not-configured/missing.vst3'}}})
    assert rejected.status_code==422
    assert storage.load_project(p.id).tracks[-2].name=='Changed'
    client.headers.pop('X-MTA-Request')
    assert client.post(f'/api/projects/{p.id}/midi',json={}).status_code==403
    client.headers['X-MTA-Request']='1'
    login(other);assert client.get(f'/api/projects/{p.id}/midi/{item["id"]}/export').status_code==404


@pytest.fixture
def instrument_path(monkeypatch):
    path=os.getenv('MTA_TEST_VSTI')
    if not path:pytest.skip('Set MTA_TEST_VSTI to an independently installed Linux VSTi')
    path=Path(path);assert path.exists();monkeypatch.setenv('MTA_VST3_PATHS',str(path.parent));return path


def test_real_instrument_live_seek_parameters_and_offline(compiled_core,instrument_path,tmp_path,monkeypatch):
    from app import cpp_audio
    from app.vst3_live_graph import Graph
    from app.audio_engine import render_track
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    t=track(midi_notes=[MidiNote(start_ms=0,duration_ms=1000,pitch=60)],instrument=InsertPlugin(id='instrument',plugin='vst3',params={'path':str(instrument_path)}))
    p=Project(id='midi-test',title='Instrument',sample_rate=48000,tracks=[t]);g=Graph(p,[tmp_path/'unused.wav'],tail_seconds=0)
    first=g.read(8192);assert first.shape==(8192,2) and np.isfinite(first).all() and abs(first).max()>.00001
    reuse=g.plugins;node=reuse[('midi','instrument')];g.close();g=Graph(p,[tmp_path/'unused.wav'],start_frame=24000,reuse=reuse,tail_seconds=0)
    assert g.plugins[('midi','instrument')].plugin is node.plugin
    assert abs(g.read(8192)).max()>.00001
    newer=p.model_copy(deep=True);newer.tracks[0].volume_db=-6;assert g.update(newer)
    g.close();target=tmp_path/'midi.wav';render_track(t,tmp_path/'unused.wav',target,sample_rate=48000)
    samples,rate=sf.read(target);assert rate==48000 and abs(samples).max()>.00001
    assert len(samples)>=48000*3
    from app.audio_engine import render_mix
    mixed=tmp_path/'master.wav';render_mix(p,lambda *_:tmp_path/'unused.wav',mixed,fmt='wav',sample_rate=48000)
    assert abs(sf.read(mixed)[0]).max()>.00001


def test_midi_note_clip_mapping_has_explicit_note_releases():
    t=track(midi_notes=[MidiNote(start_ms=10,duration_ms=900)],clips=[Clip(id='a',source_start_ms=0,source_end_ms=100,timeline_start_ms=500)])
    assert (600,[0xB0,64,0]) in events(t) and (600,[0xB0,123,0]) in events(t)


def test_real_vsti_server_session_pcm_seek_update_and_cancel(server,instrument_path,monkeypatch):
    from app import storage
    from test_r210_server_vst3 import start
    client,p,source,manager,*_=server
    monkeypatch.setenv('MTA_VST3_PATHS',str(instrument_path.parent)+os.pathsep+str(Path(os.environ['MTA_TEST_LIVE_VST3']).parent))
    t=track(midi_notes=[MidiNote(start_ms=0,duration_ms=1600,pitch=60)],instrument=InsertPlugin(id='instrument',plugin='vst3',params={'path':str(instrument_path)}))
    t.filename=source.name;p.tracks=[t];p.master_inserts=[];storage.save_project(p)
    route,status=start(client,p);assert status['plugin_count']==1
    result=client.post(route+'/pcm',json={'sequence':0,'frames':8192});assert result.status_code==200,result.text
    assert np.abs(np.frombuffer(result.content,dtype='<f4')).max()>.00001
    assert client.post(route+'/control',json={'action':'seek','cursor_ms':500}).status_code==200
    result=client.post(route+'/pcm',json={'sequence':0,'frames':8192});assert result.status_code==200
    assert np.abs(np.frombuffer(result.content,dtype='<f4')).max()>.00001
    p.tracks[0].volume_db=-6;storage.save_project(p)
    assert client.post(route+'/control',json={'action':'update'}).status_code==200
    assert client.delete(route).status_code==200 and not manager.entries


def test_real_vsti_native_null_transport_pause_seek_and_stop(compiled_core,instrument_path,tmp_path,monkeypatch):
    from app.vst3_live import Session
    from app import cpp_audio
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    t=track(midi_notes=[MidiNote(duration_ms=2000)],instrument=InsertPlugin(id='instrument',plugin='vst3',params={'path':str(instrument_path)}))
    p=Project(id='native-midi',title='MIDI',sample_rate=48000,tracks=[t])
    with_session=Session(p,[tmp_path/'unused.wav'],0,_test_null=True,paused=True)
    try:
        assert with_session.status()['plugin_count']==1
        with_session.control('play');with_session.control('pause');with_session.control('seek',500)
        assert with_session.status()['position']>=24000
    finally:with_session.close()
    assert with_session.proc.poll() is not None
