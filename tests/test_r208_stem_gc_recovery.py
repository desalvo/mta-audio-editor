"""Batch stem GC must respect published references and interrupted staging."""
import inspect
from app import main
from app import storage


def test_batch_stems_are_registered_before_copy_and_conversion():
    source = inspect.getsource(main._stem_split_worker)
    assert source.index('shutil.copyfile(stem, dst)') < source.index('_normalize_audio_to_project_rate(project.id, filename')
    assert 'if dst not in added_files:' in source


def test_batch_gc_runs_only_after_atomic_project_publication():
    source = inspect.getsource(main._stem_split_worker)
    assert source.index('stems_published = True') < source.index('schedule_project_gc(project_id, {path.name for path in obsolete_files})')
    assert 'old_path.unlink(' not in source


def test_batch_gc_rechecks_live_references_and_is_restart_durable():
    worker = inspect.getsource(storage.run_project_gc)
    resume = inspect.getsource(storage.resume_pending_gc)
    assert 'referenced_audio_files(project)' in worker
    assert 'if name in referenced:' in worker
    assert 'remaining.add(name)' in worker
    assert 'reconcile_orphans=True' in resume


def test_failed_batch_staging_uses_durable_gc():
    source = inspect.getsource(main._stem_split_worker)
    assert 'if not stems_published:' in source
    assert 'schedule_project_gc(project_id, abandoned)' in source
