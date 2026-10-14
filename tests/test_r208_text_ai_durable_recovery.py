"""Whisper/chord admission payload can survive a worker-process restart."""
from types import SimpleNamespace
import threading
import pytest
from app import main, ai_arranger_runtime as queue


def _payload(kind='lyrics'):
    return {'schema_version': 1, 'kind': kind, 'project_id': 'project-1',
            'track_id': 'track-1', 'model_or_engine': '', 'advanced_alignment': False,
            'chord_options': None, 'range_start_ms': None, 'range_end_ms': None}


@pytest.mark.parametrize('kind', ['lyrics', 'chords', 'markers'])
def test_restore_text_adapter_preserves_identity_and_cancel_event(monkeypatch, kind):
    monkeypatch.setattr(main, 'load_project', lambda pid: SimpleNamespace(tracks=[SimpleNamespace(id='track-1')]))
    called = []
    monkeypatch.setattr(main, '_text_music_worker', lambda *args: called.append(args))
    job_id = 'restored-text-' + kind
    main.MEDIA_JOBS.pop(job_id, None)
    callback = main._restore_text_music_job('project-1', _payload(kind), job_id)
    cancel_event = threading.Event()
    callback(None, cancel_event)
    assert main.MEDIA_JOBS[job_id]['cancel_event'] is cancel_event
    assert len(called) == 1 and called[0][0] == job_id and called[0][3] == kind
    main.MEDIA_JOBS.pop(job_id, None)


@pytest.mark.parametrize('change', [
    {'schema_version': 8}, {'kind': 'unknown'}, {'track_id': ''},
    {'range_start_ms': 0, 'range_end_ms': None},
    {'range_start_ms': -1, 'range_end_ms': 20},
    {'chord_options': []}, {'advanced_alignment': 'yes'},
])
def test_corrupt_text_payload_rejected_before_work(monkeypatch, change):
    monkeypatch.setattr(main, 'load_project', lambda pid: SimpleNamespace(tracks=[SimpleNamespace(id='track-1')]))
    data = _payload()
    data.update(change)
    with pytest.raises(ValueError):
        main._restore_text_music_job('project-1', data, 'bad-text-payload')


def test_text_admission_persists_reconstructible_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(queue, '_spawn', lambda *args, **kwargs: True)
    job = {'id': 'text-admission', 'kind': 'extract-lyrics', 'project_id': 'project-1',
           'status': 'queued', 'cancel_event': threading.Event()}
    main._enqueue_existing_ai_job(job, lambda: None, durable_payload=_payload())
    assert queue.read_payload(job['id']) == _payload()
    with queue._db() as con:
        row = con.execute('SELECT operation,state FROM jobs WHERE job_id=?', (job['id'],)).fetchone()
    assert row['operation'] == 'extract-lyrics' and row['state'] == 'queued'
