"""Regressions for serialization shared by ordinary and AI project mutations."""
import inspect
from contextlib import contextmanager


import pytest

from app import main
from app import ai_project_lock


@pytest.mark.parametrize('name', [
    'replace_track', 'delete_tracks', 'set_track_delay',
    'sync_metronome_to_track', 'move_track', 'autosync_track',
    'project_auto_mix', 'edit_delete_range', 'update_project_clip',
    'instantiate_project_clip',
])
def test_mutation_endpoint_preserves_signature(name):
    endpoint = getattr(main, name)
    assert 'pid' in inspect.signature(endpoint).parameters
    assert getattr(endpoint, '__wrapped__', None) is not None


def test_sync_serialization_holds_lock_through_handler(monkeypatch):
    acquired = []
    @contextmanager
    def lock(pid):
        acquired.append(('enter', pid))
        try:
            yield
        finally:
            acquired.append(('exit', pid))
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    @main._serialized_project_mutation
    def mutation(pid, extra=0):
        acquired.append(('execute', pid, extra))
        return extra + 1
    assert mutation('demo', extra=3) == 4
    assert acquired == [('enter', 'demo'), ('execute', 'demo', 3), ('exit', 'demo')]


@pytest.mark.asyncio
async def test_async_serialization_releases_on_failure(monkeypatch):
    acquired = []
    @contextmanager
    def lock(pid):
        acquired.append('enter')
        try:
            yield
        finally:
            acquired.append('exit')
    monkeypatch.setattr(ai_project_lock, 'project_publication_lock', lock)
    @main._serialized_project_mutation
    async def mutation(pid):
        acquired.append('execute')
        raise ValueError('failure')
    with pytest.raises(ValueError, match='failure'):
        await mutation('demo')
    assert acquired == ['enter', 'execute', 'exit']
