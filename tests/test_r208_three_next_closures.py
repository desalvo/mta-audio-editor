"""Behavioral coverage for FLAC, BPM optimism, synchronous stem compatibility."""
from contextlib import contextmanager
from types import SimpleNamespace

import inspect
import pytest
from fastapi import HTTPException
from app import main, ai_project_lock


def test_flac_migration_takes_project_lock_before_load(monkeypatch):
    events = []
    @contextmanager
    def lock(pid):
        events.append('lock')
        try:
            yield
        finally:
            events.append('unlock')
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    monkeypatch.setattr(main, '_project_for_actor', lambda *_: events.append('load') or SimpleNamespace(audio_storage_mode='flac'))
    main.project_migrate_flac('p', object())
    assert events == ['lock', 'load', 'unlock']


def test_bpm_inference_is_outside_lock_and_conflict_fails_closed(monkeypatch):
    events=[]
    @contextmanager
    def lock(pid):
        events.append('lock')
        try:
            yield
        finally:
            events.append('unlock')
    track = SimpleNamespace(id='t', filename='a.wav', sample_rate=44100, duration_ms=400)
    original = SimpleNamespace(tracks=[track], bpm=120, base_bpm=120, time_signature='4/4')
    changed = SimpleNamespace(tracks=[track], bpm=132, base_bpm=132, time_signature='4/4')
    reads = iter([original, changed])
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    monkeypatch.setattr(main, '_project_for_actor', lambda *_: events.append('load') or next(reads))
    monkeypatch.setattr(main, 'audio_path', lambda *_: 'a.wav')
    monkeypatch.setattr(main, 'estimate_bpm_and_signature', lambda *a, **k: events.append('infer') or (128, '4/4'))
    monkeypatch.setattr(main, 'save_project', lambda *_: pytest.fail('stale BPM must not persist'))
    with pytest.raises(HTTPException) as exc:
        main.estimate_track_bpm('p', 't', object())
    assert exc.value.status_code == 409
    assert events == ['lock','load','unlock','infer','lock','load','unlock']


def test_bpm_track_replaced_during_inference_is_rejected(monkeypatch):
    @contextmanager
    def lock(pid): yield
    t1=SimpleNamespace(id='t',filename='a.wav',sample_rate=44100,duration_ms=100)
    t2=SimpleNamespace(id='t',filename='b.wav',sample_rate=44100,duration_ms=100)
    p1=SimpleNamespace(tracks=[t1],bpm=120,base_bpm=120,time_signature='4/4')
    p2=SimpleNamespace(tracks=[t2],bpm=120,base_bpm=120,time_signature='4/4')
    monkeypatch.setattr(ai_project_lock,'project_publication_lock',lock)
    monkeypatch.setattr(main,'_project_for_actor', lambda *_: next(reads))
    reads=iter([p1,p2])
    monkeypatch.setattr(main,'audio_path', lambda *_: 'a.wav')
    monkeypatch.setattr(main,'estimate_bpm_and_signature', lambda *a, **k: (120,'4/4'))
    monkeypatch.setattr(main,'save_project', lambda *_: pytest.fail('must not save'))
    with pytest.raises(HTTPException) as err: main.estimate_track_bpm('p','t',object())
    assert err.value.status_code == 409


def test_sync_stems_existing_project_locked_before_snapshot():
    source = inspect.getsource(main.split_stems_compat)
    assert 'with project_publication_lock(project_id)' in source
    assert source.index('with project_publication_lock(project_id)') < source.index('existing_project=_project_for_actor')
    assert source.index('existing_project=_project_for_actor') < source.index('save_project(project)')
