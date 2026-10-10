"""r167: project-scoped VST3 checkpoint archive and stale identity defenses."""
import zipfile

import pytest

from app import storage
from app.models import InsertPlugin
from app.vst3_project_state import (checkpoint_path, load_insert_checkpoint,
                                    remove_stale_checkpoints, save_insert_checkpoint)
from native.vst3_probe.native_chain import NativeChainError


@pytest.fixture
def sample_project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    storage.ROOT.mkdir()
    project = storage.create_project('State archive')
    project.master_inserts = [InsertPlugin(id='my-vst', plugin='vst3', params={'path': '/plugin/A.vst3'})]
    storage.save_project(project)
    return project


def test_state_roundtrip_project_export_import(sample_project, tmp_path):
    pid = sample_project.id
    state_path = save_insert_checkpoint(pid, 'master', 'my-vst', b'component', b'controller')
    assert state_path.is_file()
    assert load_insert_checkpoint(pid, 'master', 'my-vst') == (b'component', b'controller')
    archive = tmp_path / 'portable.maeprojz'
    storage.write_project_archive(pid, archive)
    with zipfile.ZipFile(archive) as z:
        assert 'project/vst3-checkpoints/master--my-vst.json' in z.namelist()
    imported = storage.import_project_archive(archive, None)
    assert load_insert_checkpoint(imported.id, 'master', 'my-vst') == (b'component', b'controller')


def test_identity_change_rejects_old_checkpoint(sample_project):
    pid = sample_project.id
    save_insert_checkpoint(pid, 'master', 'my-vst', b'component', None)
    sample_project.master_inserts[0].params['path'] = '/plugin/B.vst3'
    storage.save_project(sample_project)
    with pytest.raises(NativeChainError):
        load_insert_checkpoint(pid, 'master', 'my-vst')


def test_deleted_insert_cleanup_and_invalid_identifier(sample_project):
    pid = sample_project.id
    save_insert_checkpoint(pid, 'master', 'my-vst', b'a', None)
    with pytest.raises(ValueError):
        checkpoint_path(pid, '../master', 'my-vst')
    sample_project.master_inserts.clear()
    storage.save_project(sample_project)
    assert remove_stale_checkpoints(pid) == 1
    assert remove_stale_checkpoints(pid) == 0


def test_reject_oversize_import_checkpoint(sample_project, tmp_path):
    archive = tmp_path / 'malicious.maeprojz'
    storage.write_project_archive(sample_project.id, archive)
    with zipfile.ZipFile(archive, 'a') as z:
        z.writestr('project/vst3-checkpoints/master--my-vst.json', b'x' * (3 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match='checkpoint'):
        storage.import_project_archive(archive, None)
