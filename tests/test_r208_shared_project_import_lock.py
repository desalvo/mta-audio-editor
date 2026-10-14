"""Cross-process track imports use the same publication lock as recovered jobs."""
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from app import main
from app import ai_project_lock


def test_regular_upload_acquires_shared_lock(monkeypatch):
    observed = []
    @contextmanager
    def lock(pid):
        observed.append(('enter', pid))
        try:
            yield
        finally:
            observed.append(('exit', pid))
    async def imported(pid, request, file, **kwargs):
        observed.append(('import', pid))
        return {'id': pid}
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    monkeypatch.setattr(main, '_add_track_under_project_lock', imported)
    result = asyncio.run(main.add_track('p1', SimpleNamespace(), SimpleNamespace(), name='a'))
    assert result == {'id': 'p1'}
    assert observed == [('enter', 'p1'), ('import', 'p1'), ('exit', 'p1')]


def test_regular_upload_releases_lock_on_failure(monkeypatch):
    events = []
    @contextmanager
    def lock(pid):
        events.append('enter')
        try:
            yield
        finally:
            events.append('exit')
    async def fail(*args, **kwargs):
        raise RuntimeError('audio conversion failure')
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    monkeypatch.setattr(main, '_add_track_under_project_lock', fail)
    try:
        asyncio.run(main.add_track('p1', None, None))
    except RuntimeError:
        pass
    else:
        raise AssertionError('exception swallowed')
    assert events == ['enter', 'exit']
