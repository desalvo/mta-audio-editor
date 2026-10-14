"""Regression guards for background audio import concurrency."""
import inspect
import textwrap

from app import main


def _source(fn):
    return textwrap.dedent(inspect.getsource(fn))


def test_track_import_publishes_current_project_under_shared_lock():
    src = _source(main._track_import_worker)
    assert 'with project_publication_lock(pid):\n            latest = load_project(pid)' in src
    locked = src.split('with project_publication_lock(pid):', 1)[1]
    assert locked.index('latest = load_project(pid)') < locked.index('latest.tracks.append(track)') < locked.index('save_project(latest)')
    assert 'save_project(project)' not in src


def test_track_import_does_expensive_processing_without_lock():
    src = _source(main._track_import_worker)
    lock = src.index('with project_publication_lock(pid):')
    assert src.index('estimate_bpm_and_signature(') < lock
    assert src.index('waveform_peaks(') < lock
    assert src.index('_normalize_audio_to_project_rate(') < lock
    assert 'int(latest.sample_rate) != int(project.sample_rate)' in src
    assert 'estimated_tempo is not None and not latest.tracks' in src
    assert 'if not committed:' in src


def test_waveform_publication_rejects_changed_track():
    src = _source(main._waveform_worker)
    lock = src.index('with project_publication_lock(pid):')
    assert src.index('waveform_peaks(') < lock
    assert src.index('latest = load_project(pid)', lock) < src.index('save_project(latest)', lock)
    assert '!= source_revision' in src
