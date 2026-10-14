"""Behavioural regression for three project read-modify-write race closures."""
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from app import main
from app import ai_project_lock


def test_project_open_holds_shared_lock_before_loading(monkeypatch):
    events = []
    @contextmanager
    def lock(pid):
        events.append('lock')
        yield
        events.append('unlock')
    project = SimpleNamespace(id='p', base_bpm=120, bpm=120, tracks=[])
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    monkeypatch.setattr(main, '_project_for_actor', lambda *_: events.append('load') or project)
    monkeypatch.setattr(main, 'maintain_project_storage', lambda *_: events.append('maintain'))
    monkeypatch.setattr(main, '_ensure_project_clip_library', lambda *_: False)
    assert main.project_get('p', object()) is project
    assert events == ['lock', 'load', 'maintain', 'unlock']


def test_estimate_bpm_releases_lock_during_inference_then_reloads(monkeypatch):
    events = []
    @contextmanager
    def lock(pid):
        events.append('lock')
        yield
        events.append('unlock')
    track = SimpleNamespace(id='t', filename='track.wav', sample_rate=44100, duration_ms=1000)
    project = SimpleNamespace(id='p', tracks=[track], bpm=120, base_bpm=120, time_signature='4/4')
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    monkeypatch.setattr(main, '_project_for_actor', lambda *_: events.append('load') or project)
    monkeypatch.setattr(main, 'audio_path', lambda *_: '/tmp/not-used.wav')
    monkeypatch.setattr(main, 'estimate_bpm_and_signature', lambda *a, **k: (125, '4/4'))
    monkeypatch.setattr(main, 'save_project', lambda *_: events.append('save'))
    result = main.estimate_track_bpm('p', 't', object())
    assert result['bpm'] == 125
    assert events == ['lock', 'load', 'unlock', 'lock', 'load', 'save', 'unlock']


def test_admin_legacy_claim_rechecks_owner_under_lock(monkeypatch):
    events = []
    @contextmanager
    def lock(pid):
        events.append('lock')
        yield
        events.append('unlock')
    stale = SimpleNamespace(id='p', owner_user_id=None)
    already_claimed = SimpleNamespace(id='p', owner_user_id=22)
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    monkeypatch.setattr(main, '_actor', lambda *_: {'id': 1, 'role': 'admin'})
    monkeypatch.setattr(main, 'list_projects', lambda *a, **k: [stale])
    monkeypatch.setattr(main, 'load_project', lambda *_: events.append('reload') or already_claimed)
    monkeypatch.setattr(main, 'save_project', lambda *_: pytest.fail('must not steal ownership'))
    main.projects(object())
    assert events == ['lock', 'reload', 'unlock']
