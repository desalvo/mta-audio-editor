"""DB identity isolation/concurrent preference patches and linked MIDI grid."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from app import auth, user_preferences
from app.models import Project, Track, Clip, Marker, MidiMetronome
from app.midi_metronome import refresh


@pytest.fixture
def preferences(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'data_root', lambda: tmp_path)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'false')
    with auth.db() as con:
        con.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)')
        con.executemany('INSERT INTO users VALUES(?)', [(1,), (2,)])
    return user_preferences


def test_concurrent_preferences_merge_and_cascade(preferences):
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda i: preferences.patch({'id': 1}, {f'mta.pref.{i}': str(i)}), range(30)))
    assert len(preferences.load({'id': 1})['values']) == 30
    assert preferences.load({'id': 2})['values'] == {}
    preferences.patch({'id': 1}, {'mta.pref.0': None})
    assert len(preferences.load({'id': 1})['values']) == 29
    with auth.db() as con:
        con.execute('DELETE FROM users WHERE id=1')
        assert con.execute('SELECT COUNT(*) FROM application_preferences').fetchone()[0] == 0


def test_native_preferences_need_no_server_user_or_auth_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'data_root', lambda: tmp_path)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    user_preferences.patch({'id': 0}, {'mta.sidebar.collapsed.v1': '{"midi":false}'})
    assert user_preferences.load({'id': 0}) == {'owner': 'native', 'values': {'mta.sidebar.collapsed.v1': '{"midi":false}'}}


@pytest.mark.parametrize('value', [{'_bad key': 'x'}, {'mta.key': float('nan')}, {'mta.key': 'x'*32769}, {'mta.key': []}])
def test_invalid_preference_payload_is_atomic(preferences, value):
    preferences.patch({'id': 1}, {'mta.key': 'good'})
    with pytest.raises(ValueError):
        preferences.patch({'id': 1}, value)
    assert preferences.load({'id': 1})['values'] == {'mta.key': 'good'}


def test_bootstrap_script_data_is_escaped(preferences, monkeypatch):
    preferences.patch({'id': 1}, {'mta.caption': '</script><script>alert(1)</script>'})
    monkeypatch.setattr(auth, 'session_user', lambda request: {'id': 1})
    value = preferences.bootstrap(None)
    assert '<' not in value and json.loads(value)['values']['mta.caption'].startswith('</script>')


def project():
    audio = Track(id='audio', name='Audio', filename='audio.wav', duration_ms=6000,
                  clips=[Clip(id='a', source_end_ms=6000)])
    click = Track(id='click', name='MIDI click', filename='click.wav', kind='midi', midi_metronome=MidiMetronome(), duration_ms=6000)
    return Project(id='p', title='MIDI grid', bpm=120, tracks=[audio, click])


def test_midi_grid_uses_decimal_bpm_without_changing_audio_tempo():
    p = project()
    p.metronome_bpm = 112.5
    refresh(p)
    assert [n.start_ms for n in p.tracks[1].midi_notes[:4]] == [0, 533, 1067, 1600]
    assert [n.velocity for n in p.tracks[1].midi_notes[:4]] == [120, 85, 85, 85]
    assert p.bpm == 120 and p.tracks[0].delay_ms == 0
    before = p.tracks[1].midi_notes
    refresh(p)
    assert p.tracks[1].midi_notes is before
    p.metronome_bpm = 100
    refresh(p)
    assert p.tracks[1].midi_notes[1].start_ms == 600


def test_zone_marker_move_refreshes_linked_midi_clicks():
    p = project()
    p.metronome_mode = 'zones'
    p.metronome_insertion_ms = 750
    p.markers = [Marker(id='bridge', time_ms=3000, label='Bridge')]
    p.metronome_manual_zone_bpms = {'START|bridge': 120, 'bridge|END': 60}
    refresh(p)
    assert [n.start_ms for n in p.tracks[1].midi_notes] == [750, 1250, 1750, 2250, 2750, 3000, 4000, 5000]
    p.markers[0].time_ms = 3200
    refresh(p)
    assert [n.start_ms for n in p.tracks[1].midi_notes][-3:] == [3200, 4200, 5200]
    assert p.tracks[1].midi_notes[-3].velocity == 120


def test_unlinked_metronome_preserves_manually_edited_notes():
    p = project()
    refresh(p)
    p.tracks[1].midi_metronome = None
    p.tracks[1].midi_notes[0].pitch = 60
    p.metronome_bpm = 90
    refresh(p)
    assert p.tracks[1].midi_notes[0].pitch == 60
