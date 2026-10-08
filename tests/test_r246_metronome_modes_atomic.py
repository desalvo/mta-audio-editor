from pathlib import Path

from app.audio_engine import stabilize_adaptive_beats, zoned_metronome_beats
from app.models import Marker, Project

ROOT = Path(__file__).resolve().parents[1]


def test_zones_restart_at_active_markers_and_skip_disabled():
    p = Project(id='z', title='Zones', bpm=120, markers=[
        Marker(time_ms=750, label='Verse'),
        Marker(time_ms=1200, label='Hidden', disabled=True),
        Marker(time_ms=2300, label='Chorus')])
    assert zoned_metronome_beats(p, 3000) == [0, 500, 750, 1250, 1750, 2250, 2300, 2800]


def test_sensitivity_changes_jitter_and_preserves_monotonicity():
    beats=[0, 500, 1050, 1450, 2050, 2500]
    a=stabilize_adaptive_beats(beats, 0.0)
    b=stabilize_adaptive_beats(beats, 1.0)
    assert a!=b
    assert all(x<y for x,y in zip(a,a[1:]))
    assert all(x<y for x,y in zip(b,b[1:]))


def test_project_persists_metronome_settings():
    p=Project(id='z', title='Zones', metronome_mode='zones', metronome_sensitivity=0.7, show_markers_playback=True)
    q=Project.model_validate_json(p.model_dump_json())
    assert (q.metronome_mode,q.metronome_sensitivity,q.show_markers_playback)==('zones',0.7,True)


def test_atomic_metronome_and_chords_stage_before_replace():
    source=(ROOT/'app/main.py').read_text()
    assert 'os.replace(out, target_out)' in source
    assert 'shutil.copyfile(target, staged)' in source
    assert 'os.replace(staged, target)' in source
    assert 'finally:\n            staged.unlink(missing_ok=True)' in source
