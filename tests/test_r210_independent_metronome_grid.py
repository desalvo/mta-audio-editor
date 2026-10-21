import subprocess

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.models import Project, Track, Clip, Marker
from app.audio_engine import render_mix, generate_metronome_wav
from app.timeline_editing import prepare_metronome_insert
from app.metronome_grid import grid_settings, zone_signature


@pytest.fixture
def setup(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    monkeypatch.setattr(storage, 'ROOT', tmp_path)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    p = storage.create_project('Independent grid')
    p.bpm, p.base_bpm, p.original_bpm = 180, 120, 120
    p.tracks = [Track(id='music', name='Music', filename='music.wav', duration_ms=8000,
                      clips=[Clip(id='c', source_end_ms=8000)])]
    storage.save_project(p)
    samples = .2*np.sin(2*np.pi*440*np.arange(44100*8)/44100)
    sf.write(storage.audio_path(p.id, 'music.wav'), samples, 44100)
    return TestClient(main.app, headers={'X-MTA-Request': '1'}), storage, p, tmp_path


def music_state(p):
    return (p.bpm, p.base_bpm, p.original_bpm, p.time_signature, p.pitch_semitones,
            p.tracks[0].model_dump())


def test_fixed_grid_configuration_does_not_change_audio_or_source(setup):
    client, storage, p, root = setup
    before = music_state(p)
    original = storage.audio_path(p.id, 'music.wav').read_bytes()
    render_mix(p, storage.audio_path, root/'before.wav', fmt='wav')
    response = client.post(f'/api/projects/{p.id}/metronome-grid', json={'bpm': 90, 'time_signature': '3/4'})
    assert response.status_code == 200, response.text
    assert response.json()['track'] is None
    assert client.post(f'/api/projects/{p.id}/metronome-track', params={'mode': 'fixed'}).status_code == 200
    saved = storage.load_project(p.id)
    assert music_state(saved) == before
    assert storage.audio_path(p.id, 'music.wav').read_bytes() == original
    saved.tracks = [saved.tracks[0]]
    render_mix(saved, storage.audio_path, root/'after.wav', fmt='wav')
    assert (root/'before.wav').read_bytes() == (root/'after.wav').read_bytes()
    generate_metronome_wav(saved, root/'click.wav')
    pcm, rate = sf.read(root/'click.wav')
    assert np.max(abs(pcm[int(.99*rate):int(1.04*rate)])) > .5
    assert np.max(abs(pcm[int(.49*rate):int(.53*rate)])) == 0


def test_grid_change_with_existing_click_preserves_mixer_tempo_and_music(setup):
    client, storage, p, _ = setup
    assert client.post(f'/api/projects/{p.id}/metronome-track').status_code == 200
    before = storage.load_project(p.id)
    next(t for t in before.tracks if t.type == 'click').volume_db = -12
    storage.save_project(before)
    response = client.post(f'/api/projects/{p.id}/metronome-grid', json={'bpm': 100, 'time_signature': '6/8'})
    assert response.status_code == 200
    after = storage.load_project(p.id)
    assert music_state(after) == music_state(before)
    assert grid_settings(after) == (100, '6/8')
    assert next(t for t in after.tracks if t.type == 'click').volume_db == -12
    assert len([t for t in after.tracks if t.type == 'click']) == 1


def test_zone_signature_changes_only_that_zone_and_survives_full_regeneration(setup):
    client, storage, p, _ = setup
    p.metronome_mode, p.metronome_bpm, p.metronome_time_signature = 'zones', 120, '4/4'
    marker = Marker(id='boundary', time_ms=4000, label='B')
    p.markers = [marker]
    storage.save_project(p)
    assert client.post(f'/api/projects/{p.id}/metronome-track', params={'mode': 'zones'}).status_code == 200
    before = storage.load_project(p.id)
    click = next(t for t in before.tracks if t.type == 'click')
    initial, rate = sf.read(storage.audio_path(p.id, click.filename), dtype='int16')
    response = client.post(f'/api/projects/{p.id}/metronome-zone-bpm', params={'time_ms': 4500, 'bpm': 60, 'time_signature': '3/4'})
    assert response.status_code == 200, response.text
    after = storage.load_project(p.id)
    edited, _ = sf.read(storage.audio_path(p.id, click.filename), dtype='int16')
    assert np.array_equal(initial[:rate*4], edited[:rate*4])
    assert not np.array_equal(initial[rate*4:], edited[rate*4:])
    assert zone_signature(after, marker.id, 'END') == '3/4'
    assert music_state(after) == music_state(before)
    manual_zone = edited[rate*4:].copy()
    response = client.post(f'/api/projects/{p.id}/metronome-grid', json={'bpm': 100, 'time_signature': '5/4'})
    assert response.status_code == 200, response.text
    regenerated, _ = sf.read(storage.audio_path(p.id, click.filename), dtype='int16')
    assert np.array_equal(manual_zone, regenerated[rate*4:])
    after = storage.load_project(p.id)
    after.markers[0].time_ms = 4200
    assert zone_signature(after, 'boundary', 'END') == '3/4'
    assert after.metronome_zone_bpms['0'] == 100
    assert after.metronome_zone_bpms['4000'] == 60
    assert after.metronome_zone_signatures['0'] == '5/4'
    assert after.metronome_zone_signatures['4000'] == '3/4'


def test_adaptive_grid_is_not_manually_overridden(setup):
    client, storage, p, _ = setup
    p.metronome_mode = 'adaptive'
    p.metronome_bpm, p.metronome_time_signature = 90, '3/4'
    storage.save_project(p)
    assert grid_settings(p) == (180, '4/4')
    assert client.post(f'/api/projects/{p.id}/metronome-grid', json={'bpm': 100, 'time_signature': '5/4'}).status_code == 400
    assert client.post(f'/api/projects/{p.id}/metronome-zone-bpm', params={'bpm': 100}).status_code == 400
    assert music_state(storage.load_project(p.id)) == music_state(p)


@pytest.mark.parametrize('payload', [{'bpm': 0, 'time_signature': '4/4'}, {'bpm': True, 'time_signature': '4/4'}, {'bpm': 100, 'time_signature': 'abc'}])
def test_invalid_grid_settings_are_rejected_without_changes(setup, payload):
    client, storage, p, _ = setup
    original = storage.load_project(p.id).model_dump_json()
    assert client.post(f'/api/projects/{p.id}/metronome-grid', json=payload).status_code == 400
    assert storage.load_project(p.id).model_dump_json() == original


def test_preroll_uses_metronome_grid_instead_of_audio_tempo():
    p = Project(id='p', title='P', bpm=180, base_bpm=120, metronome_bpm=60, metronome_time_signature='3/4', tracks=[Track(id='t', name='T', filename='t.wav', duration_ms=1000)])
    q, extension = prepare_metronome_insert(p, 0, 2)
    assert extension == 9000 and q.metronome_insertion_ms == 9000
    assert (q.bpm, q.base_bpm) == (180, 120)


def test_compound_delay_units_and_zone_grid_math_in_browser_code():
    code = r'''const fs=require('fs'),vm=require('vm'),assert=require('assert'),R=require('./app/static/timeline_rules.js');
const s=fs.readFileSync('app/static/app.js','utf8');const p={bpm:180,base_bpm:120,time_signature:'4/4',metronome_bpm:60,metronome_time_signature:'3/4',metronome_mode:'fixed',tracks:[{id:'t',delay_ms:0,clips:[{id:'c',timeline_start_ms:0,source_start_ms:0,source_end_ms:10000}]}]};
const c={current:p,MtaTimelineRules:R,playCursorMs:0};vm.createContext(c);vm.runInContext(s.slice(s.indexOf('function trackDelayUnit('),s.indexOf('function delayUnitOptions(')),c);
assert.equal(c.delayMsFromUnit('1:2','bars_beats'),7500);assert.equal(c.delayMsFromUnit('-1:2.5','bars_beats'),-8250);assert.equal(c.delayMsFromUnit('-0:2','bars_beats'),-3000);assert(Number.isNaN(c.delayMsFromUnit('1:3','bars_beats')));assert.equal(c.delayValueFromMs(-8250,'bars_beats'),'-1:2.5');assert.equal(c.delayMsFromUnit(.5,'bars'),2250);assert.equal(c.delayMsFromUnit(2,'beats'),3000);
p.metronome_mode='zones';p.markers=[{id:'m',time_ms:4000}];p.metronome_manual_zone_bpms={'m|END':120};p.metronome_manual_zone_signatures={'m|END':'5/4'};const t={clips:[{timeline_start_ms:5000}]};assert.equal(c.delayMsFromUnit('1:2','bars_beats',t),5250);assert.equal(R.gridAt(p,5000).signature,'5/4');p.timeline_snap='bars';assert.equal(R.step(p,5000),3750);
assert.equal(p.bpm/p.base_bpm,1.5);
'''
    subprocess.run(['node', '-e', code], check=True, capture_output=True, text=True)


def test_old_delay_units_migrate_without_changing_offset():
    t = Track(id='t', name='T', filename='a.wav', delay_ms=-125)
    t.delay_unit = 'bars_beats'
    q = Track.model_validate_json(t.model_dump_json())
    assert q.delay_ms == -125 and q.delay_unit == 'bars_beats'


def test_grid_configuration_rolls_back_on_render_failure(setup, monkeypatch):
    import app.main as main
    from fastapi import HTTPException
    client, storage, p, _ = setup
    assert client.post(f'/api/projects/{p.id}/metronome-track').status_code == 200
    before = storage.load_project(p.id)
    click = next(t for t in before.tracks if t.type == 'click')
    pcm = storage.audio_path(p.id, click.filename).read_bytes()
    def fail(*args, **kwargs):
        raise HTTPException(400, 'render failed')
    monkeypatch.setattr(main, '_create_metronome_track_locked', fail)
    assert client.post(f'/api/projects/{p.id}/metronome-grid', json={'bpm': 99, 'time_signature': '5/4'}).status_code == 400
    assert storage.load_project(p.id).model_dump() == before.model_dump()
    assert storage.audio_path(p.id, click.filename).read_bytes() == pcm


def test_grid_configuration_requires_project_access(setup, monkeypatch):
    import app.main as main
    from fastapi import HTTPException
    client, storage, p, _ = setup
    def denied(*args, **kwargs):
        raise HTTPException(403, 'Forbidden')
    monkeypatch.setattr(main, '_project_for_actor', denied)
    assert client.post(f'/api/projects/{p.id}/metronome-grid', json={'bpm': 99, 'time_signature': '5/4'}).status_code == 403
    assert storage.load_project(p.id).metronome_bpm is None
