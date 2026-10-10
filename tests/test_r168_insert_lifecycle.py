"""r168: link project VST3 insert snapshots to the control-thread supervisor."""
from pathlib import Path
import pytest
from app import storage
from app.models import InsertPlugin
from app.vst3_project_state import capture_insert_checkpoint, stage_insert_checkpoint
from native.vst3_probe.native_chain import NativeChainError


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    storage.ROOT.mkdir()
    p = storage.create_project('Lifecycle')
    p.master_inserts = [InsertPlugin(id='vst', plugin='vst3', params={'path': '/p/A.vst3'})]
    storage.save_project(p)
    return p


class WorkerStub:
    def __init__(self):
        self.snapshot = (b'processor', b'controller')
        self.imported = None
        self.calls = 0
    def checkpoint_full_state(self):
        self.calls += 1
        return self.snapshot
    def import_checkpoint(self, path, identity):
        from native.vst3_probe.state_store import load_checkpoint
        self.imported = load_checkpoint(path, identity)


def test_project_snapshot_capture_and_stage(project):
    active = WorkerStub()
    path = capture_insert_checkpoint(project.id, 'master', 'vst', active)
    assert path.is_file() and active.calls == 1
    fresh = WorkerStub()
    assert stage_insert_checkpoint(project.id, 'master', 'vst', fresh) is True
    assert fresh.imported == (b'processor', b'controller')


def test_missing_checkpoint_leaves_supervisor_untouched(project):
    worker = WorkerStub()
    assert stage_insert_checkpoint(project.id, 'master', 'vst', worker) is False
    assert worker.imported is None


def test_reject_switch_after_capture_before_persist(project):
    class Mutating(WorkerStub):
        def checkpoint_full_state(self):
            project.master_inserts[0].params['path'] = '/p/Other.vst3'
            storage.save_project(project)
            return super().checkpoint_full_state()
    with pytest.raises(ValueError, match='changed'):
        capture_insert_checkpoint(project.id, 'master', 'vst', Mutating())


def test_switch_rejects_stale_snapshot(project):
    capture_insert_checkpoint(project.id, 'master', 'vst', WorkerStub())
    project.master_inserts[0].params['path'] = '/p/Other.vst3'
    storage.save_project(project)
    with pytest.raises(NativeChainError):
        stage_insert_checkpoint(project.id, 'master', 'vst', WorkerStub())


def test_nonexistent_insert_never_contacts_worker(project):
    worker = WorkerStub()
    with pytest.raises(ValueError):
        capture_insert_checkpoint(project.id, 'master', 'does-not-exist', worker)
    assert worker.calls == 0
