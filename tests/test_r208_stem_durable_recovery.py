"""Durable stem recovery covers Demucs, DrumSep, SAM Audio and backing vocals."""
import threading
from pathlib import Path

import pytest

from app import main


def _request(source):
    job = {
        'id':'stem-job-1', 'project_id':'project-1', 'model':'htdemucs_6s',
        'stem_count':6, 'stem_targets':['all'], 'singers':[],
        'split_backing_vocals':False, 'split_percussions':False,
        'cancel_event':threading.Event(),
    }
    return job


def test_restorer_rebuilds_project_scoped_stem_worker(tmp_path, monkeypatch):
    source = tmp_path / 'original.mp3'
    source.write_bytes(b'fake-mp3')
    monkeypatch.setattr(main, 'file_path', lambda pid, category, name: source)
    monkeypatch.setattr(main, 'load_project', lambda pid: object())
    job = _request(source)
    payload = main._stem_durable_payload(job, source, True)
    assert payload['schema_version'] == 1
    assert payload['options']['model'] == 'htdemucs_6s'
    assert payload['keep_original_track'] is True
    called = []
    monkeypatch.setattr(main, '_stem_split_worker', lambda jid, src, keep: called.append((jid, src, keep)))
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.pop('stem-job-1', None)
    try:
        execute = main._restore_stem_split_job('project-1', payload, 'stem-job-1')
        execute(None, threading.Event())
        assert called == [('stem-job-1', source, True)]
    finally:
        with main.STEM_JOB_LOCK:
            main.STEM_JOBS.pop('stem-job-1', None)


def test_restorer_rejects_wrong_project_missing_source_and_invalid_options(tmp_path, monkeypatch):
    source = tmp_path / 'original.mp3'
    source.write_bytes(b'fake-mp3')
    monkeypatch.setattr(main, 'file_path', lambda pid, category, name: source)
    monkeypatch.setattr(main, 'load_project', lambda pid: object())
    payload = main._stem_durable_payload(_request(source), source, True)
    with pytest.raises(ValueError):
        main._restore_stem_split_job('different-project', payload, 'job')
    bad = {**payload, 'options':{**payload['options'], 'stem_targets':['../../outside']}}
    with pytest.raises(ValueError):
        main._restore_stem_split_job('project-1', bad, 'job')
    source.unlink()
    with pytest.raises(ValueError):
        main._restore_stem_split_job('project-1', payload, 'job')


def test_restorer_queued_cancellation_skips_inference(tmp_path, monkeypatch):
    source = tmp_path / 'original.mp3'
    source.write_bytes(b'fake-mp3')
    monkeypatch.setattr(main, 'file_path', lambda pid, category, name: source)
    monkeypatch.setattr(main, 'load_project', lambda pid: object())
    payload = main._stem_durable_payload(_request(source), source, True)
    called = []
    monkeypatch.setattr(main, '_stem_split_worker', lambda *args: called.append(args))
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.pop('stem-job-cancelled', None)
    try:
        fn = main._restore_stem_split_job('project-1', payload, 'stem-job-cancelled')
        cancelled = threading.Event()
        cancelled.set()
        fn(None, cancelled)
        assert called == []
        assert main.STEM_JOBS['stem-job-cancelled']['status'] == 'cancelled'
    finally:
        with main.STEM_JOB_LOCK:
            main.STEM_JOBS.pop('stem-job-cancelled', None)
