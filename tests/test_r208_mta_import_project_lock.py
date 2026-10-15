"""MTA container import must share project locking with native AI publishers."""
import inspect
from types import SimpleNamespace

from app import main


def test_async_mta_import_uses_shared_project_lock_before_load(monkeypatch, tmp_path):
    events = []
    class Lock:
        def __enter__(self): events.append('lock-enter')
        def __exit__(self, *exc): events.append('lock-exit')
    def fake_lock(pid):
        assert pid == 'p1'
        return Lock()
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', fake_lock)
    monkeypatch.setattr(main, 'pdir', lambda pid: tmp_path / pid)
    monkeypatch.setattr(main, 'ffprobe', lambda path: events.append('probe'))
    monkeypatch.setattr(main, 'load_project', lambda pid: events.append('load') or object())
    monkeypatch.setattr(main, 'import_mta', lambda src, project: events.append('import') or SimpleNamespace(id='p1', title='Import', tracks=[]))
    monkeypatch.setattr(main, 'save_project', lambda project: events.append('save'))
    monkeypatch.setattr(main, '_media_job_update', lambda *a, **kw: events.append('job-update'))
    main._mta_import_worker('j1', 'p1', 'source.mta')
    assert events.index('probe') < events.index('lock-enter')
    assert events.index('lock-enter') < events.index('load') < events.index('import') < events.index('save') < events.index('lock-exit')


def test_mta_import_releases_lock_on_error_and_marks_failed(monkeypatch, tmp_path):
    events = []
    class Lock:
        def __enter__(self): events.append('enter')
        def __exit__(self, *exc): events.append('exit')
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', lambda pid: Lock())
    monkeypatch.setattr(main, 'pdir', lambda pid: tmp_path / pid)
    monkeypatch.setattr(main, 'ffprobe', lambda path: None)
    monkeypatch.setattr(main, 'load_project', lambda pid: object())
    monkeypatch.setattr(main, 'import_mta', lambda src, proj: (_ for _ in ()).throw(RuntimeError('broken import')))
    monkeypatch.setattr(main, 'delete_project', lambda pid: events.append('delete'))
    monkeypatch.setattr(main, '_media_job_update', lambda *a, **kw: events.append(kw.get('status')))
    main._mta_import_worker('j1', 'p1', 'source.mta')
    assert events.index('enter') < events.index('exit') < events.index('delete')
    assert 'failed' in events


def test_direct_mta_import_uses_same_lock():
    source = inspect.getsource(main.import_file)
    assert 'with project_publication_lock(project.id):' in source
    assert 'import_mta(src, load_project(project.id))' in source
