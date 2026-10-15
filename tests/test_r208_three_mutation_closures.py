"""End-to-end route registration and lock exclusion for three project-write areas."""




import pytest

from app import main


@pytest.mark.parametrize('path,method', [
    ('/api/projects/{pid}/tracks/{track_id}/sample-editor/edit', 'POST'),
    ('/api/projects/{pid}/tracks/{track_id}/sample-editor/effect-apply', 'POST'),
    ('/api/projects/{pid}/shares', 'POST'),
    ('/api/projects/{pid}/shares/{user_id}', 'DELETE'),
    ('/api/projects/{pid}', 'DELETE'),
])
def test_endpoint_uses_project_mutation_guard(path, method):
    routes = [r for r in main.app.routes if getattr(r, 'path', None)==path and method in getattr(r, 'methods', ())]
    assert len(routes)==1
    assert hasattr(routes[0].endpoint, '__wrapped__'), path


def test_sample_editor_lock_is_acquired_before_project_read(monkeypatch):
    state=[]
    class Guard:
        def __init__(self,pid): assert pid=='p123'
        def __enter__(self): state.append('lock')
        def __exit__(self,*args): state.append('unlock')
    import app.ai_project_lock as locks
    monkeypatch.setattr(locks,'project_publication_lock', Guard)
    monkeypatch.setattr(main,'_project_for_actor', lambda *args,**kwargs: (state.append('read'), (_ for _ in ()).throw(RuntimeError('halt')))[1])
    with pytest.raises(RuntimeError, match='halt'):
        main.sample_editor_edit('p123','t1',object(),object())
    assert state==['lock','read','unlock']


def test_share_lock_is_acquired_before_project_read(monkeypatch):
    state=[]
    class Guard:
        def __init__(self,pid): assert pid=='p123'
        def __enter__(self): state.append('lock')
        def __exit__(self,*args): state.append('unlock')
    import app.ai_project_lock as locks
    monkeypatch.setattr(locks,'project_publication_lock', Guard)
    monkeypatch.setattr(main,'_project_for_actor', lambda *args,**kwargs: (state.append('read'), (_ for _ in ()).throw(RuntimeError('halt')))[1])
    with pytest.raises(RuntimeError, match='halt'):
        main.project_share_add('p123',object(),{})
    assert state==['lock','read','unlock']


def test_delete_lock_is_acquired_before_project_read(monkeypatch):
    state=[]
    class Guard:
        def __init__(self,pid): assert pid=='p123'
        def __enter__(self): state.append('lock')
        def __exit__(self,*args): state.append('unlock')
    import app.ai_project_lock as locks
    monkeypatch.setattr(locks,'project_publication_lock', Guard)
    monkeypatch.setattr(main,'_project_for_actor', lambda *args,**kwargs: (state.append('read'), (_ for _ in ()).throw(RuntimeError('halt')))[1])
    with pytest.raises(RuntimeError, match='halt'):
        main.project_delete('p123',object())
    assert state==['lock','read','unlock']
