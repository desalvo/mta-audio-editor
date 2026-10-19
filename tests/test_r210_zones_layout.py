"""Audio-level regressions for insertion/marker saves and identity-scoped layouts."""
import json

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.models import Track, Clip, Marker
from app.audio_engine import zoned_metronome_beats
from app import editor_layout


@pytest.fixture
def editor(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    from app import main, storage
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    p=storage.create_project('Zone regression')
    p.metronome_mode='zones'
    p.metronome_bpm=120
    p.markers=[Marker(id='bridge',time_ms=3000,label='Bridge')]
    p.tracks=[Track(id='music',name='Music',filename='music.wav',duration_ms=6000,clips=[Clip(id='music-c',source_end_ms=6000)])]
    sf.write(storage.audio_path(p.id,'music.wav'),np.zeros(6000*44100),44100)
    storage.save_project(p)
    return TestClient(main.app,headers={'X-MTA-Request':'1'}),storage,p


@pytest.mark.parametrize('position',[123,750,2250,3456])
def test_insert_first_audible_click_is_at_requested_position(editor,position):
    client,storage,p=editor
    result=client.post(f'/api/projects/{p.id}/metronome-insert',json={'start_ms':position,'pre_roll_bars':0})
    assert result.status_code==200,result.text
    data=result.json();samples,rate=sf.read(storage.audio_path(p.id,data['track']['filename']))
    first=np.flatnonzero(np.abs(samples)>0.0001)[0]
    assert abs(first/rate*1000-position)<0.2
    assert data['project']['metronome_grid_origin_ms']==position
    beats=zoned_metronome_beats(storage.load_project(p.id),6000,{'0':120,'3000':120})
    assert beats[0]==position
    if position<3000:assert 3000 in beats


def test_preroll_is_retained_when_zone_is_refreshed(editor):
    client,storage,p=editor
    result=client.post(f'/api/projects/{p.id}/metronome-insert',json={'start_ms':2500,'pre_roll_bars':1}).json()
    before,rate=sf.read(storage.audio_path(p.id,result['track']['filename']))
    refreshed=client.post(f'/api/projects/{p.id}/metronome-track/refresh?time_ms=1000')
    assert refreshed.status_code==200,refreshed.text
    after,_=sf.read(storage.audio_path(p.id,result['track']['filename']))
    assert np.flatnonzero(np.abs(before)>0.001)[0]==np.flatnonzero(np.abs(after)>0.001)[0]
    assert 499<np.flatnonzero(np.abs(after)>0.001)[0]/rate*1000<501


def test_marker_save_regenerates_actual_wav_and_keeps_override(editor):
    client,storage,p=editor
    result=client.post(f'/api/projects/{p.id}/metronome-insert',json={'start_ms':750,'pre_roll_bars':0}).json()
    project=result['project'];track=result['track'];path=storage.audio_path(p.id,track['filename'])
    before=path.read_bytes();revision=track['waveform_revision']
    project['markers'][0]['time_ms']=3350
    project['metronome_manual_zone_bpms']={'bridge|END':92.5}
    saved=client.put(f'/api/projects/{p.id}',json=project)
    assert saved.status_code==200,saved.text
    assert path.read_bytes()!=before
    click=next(t for t in saved.json()['tracks'] if t['type']=='click')
    assert click['waveform_revision']!=revision
    assert storage.load_project(p.id).metronome_manual_zone_bpms['bridge|END']==92.5
    pcm,rate=sf.read(path)
    assert np.max(np.abs(pcm[round(3350*rate/1000):round(3370*rate/1000)]))>.9
    persisted=client.get(f'/api/projects/{p.id}').json()
    assert next(t for t in persisted['tracks'] if t['type']=='click')['waveform_revision']==click['waveform_revision']


def test_marker_render_failure_rolls_back_metadata_and_wav(editor,monkeypatch):
    from app import main
    client,storage,p=editor
    result=client.post(f'/api/projects/{p.id}/metronome-insert',json={'start_ms':0,'pre_roll_bars':0}).json()
    path=storage.audio_path(p.id,result['track']['filename']);before=path.read_bytes()
    project=result['project'];project['markers'][0]['time_ms']=3350
    def fail(*args,**kwargs):raise RuntimeError('synthetic renderer failure')
    monkeypatch.setattr(main,'generate_adaptive_metronome_wav',fail)
    response=client.put(f'/api/projects/{p.id}',json=project)
    assert response.status_code==400
    assert storage.load_project(p.id).markers[0].time_ms==3000
    assert path.read_bytes()==before
    assert not list(path.parent.glob('.*.tmp.wav'))


@pytest.mark.parametrize('bad',[{'rows':[['same','same']]},{'rows':[['<script>']]},{'rows':[[]]*7},{'job_position':{'x':-1,'y':0}},{'job_position':{'x':True,'y':0}},{'job_position':{'x':float('inf'),'y':0}},{'other':1}])
def test_layout_validation(bad):
    with pytest.raises(ValueError):editor_layout.validate(bad)


def test_native_layout_is_atomic_and_persistent(tmp_path,monkeypatch):
    monkeypatch.setattr(editor_layout.auth,'data_root',lambda:tmp_path)
    value={'rows':[['header_playMaster'],['editor_toolSelect']],'job_position':{'x':.8,'y':.2}}
    editor_layout.save({'id':0},value,native=True)
    assert editor_layout.load({'id':0},native=True)==value
    assert json.loads((tmp_path/'native-editor-layout.json').read_text())==value
    assert not list(tmp_path.glob('.editor-layout-*'))


def test_user_layouts_are_isolated_and_cascade_on_delete(tmp_path,monkeypatch):
    import sqlite3
    from contextlib import contextmanager
    path=tmp_path/'auth.sqlite3'
    @contextmanager
    def db():
        con=sqlite3.connect(path);con.execute('PRAGMA foreign_keys=ON')
        try:yield con;con.commit()
        finally:con.close()
    monkeypatch.setattr(editor_layout.auth,'db',db)
    with db() as con:
        con.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)');con.executemany('INSERT INTO users(id) VALUES(?)',[(1,),(2,)])
    value={'rows':[['header_playMaster']]}
    editor_layout.save({'id':1},value)
    assert editor_layout.load({'id':1})==value
    assert editor_layout.load({'id':2})=={'rows':[]}
    with db() as con:con.execute('DELETE FROM users WHERE id=1')
    with db() as con:assert con.execute('SELECT COUNT(*) FROM editor_layout_preferences').fetchone()[0]==0


def test_marker_edit_tolerates_a_deleted_reference(editor):
    client,storage,p=editor
    result=client.post(f'/api/projects/{p.id}/metronome-insert',json={'start_ms':750,'pre_roll_bars':0}).json()
    project=result['project'];project['metronome_reference_track_id']='deleted-source';project['markers'][0]['time_ms']=3350
    saved=client.put(f'/api/projects/{p.id}',json=project)
    assert saved.status_code==200,saved.text
    assert saved.json()['metronome_reference_track_id']==''
