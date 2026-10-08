from pathlib import Path
from app.audio_engine import zoned_metronome_beats
from app.models import Project, Marker


def test_zones_have_distinct_tempo_and_rephase_at_markers():
    project = Project(id='zone-test', title='Zone', artist='', bpm=120, markers=[Marker(time_ms=2000, label='B')])
    beats = zoned_metronome_beats(project, 4000, {'0': 120.0, '2000': 60.0})
    assert beats == [0, 500, 1000, 1500, 2000, 3000]


def test_zone_tempo_is_saved_in_project_schema():
    p=Project(id='zone-test', title='Zone', artist='', metronome_zone_bpms={'0':110.0,'2000':135.0})
    assert Project.model_validate_json(p.model_dump_json()).metronome_zone_bpms['2000']==135.0


def test_context_menu_checks_one_source_and_uses_transport_zone():
    s=Path('app/static/app.js').read_text()
    assert "selectedTrackIdSet.size!==1" in s
    assert 'updateMetronomeFromAudioTrack' in s
    assert "time_ms:String(Math.max(0,Math.round(timeMs||0)))" in s
    assert 'e.key===\'ArrowLeft\'||e.key===\'ArrowRight\'' in s


def test_zone_refresh_is_atomic_and_partial():
    s=Path('app/main.py').read_text()
    assert 'def _update_metronome_zone_locked' in s
    assert 'output.writeframesraw(pcm.tobytes())' in s
    assert 'os.replace(temp,original)' in s
    assert 'refresh_scope":"zone_atomic' in s
