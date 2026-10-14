import sqlite3
import pytest
from app import ai_publish_outbox as outbox
from app import ai_arranger_runtime as runtime

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path / 'jobs')
    return tmp_path

def test_sqlite_symlink_refused_before_open(sandbox):
    root = outbox._root()
    target = sandbox / 'outside.sqlite'
    sqlite3.connect(target).close()
    (root / 'outbox.sqlite3').symlink_to(target)
    with pytest.raises(ValueError, match='regular file'):
        outbox.stage('j1', 'p1', b'wav', {})

def test_sqlite_directory_refused_before_open(sandbox):
    (outbox._root() / 'outbox.sqlite3').mkdir()
    with pytest.raises(ValueError, match='regular file'):
        outbox.status('j1')

def test_sqlite_sidecar_symlink_refused(sandbox):
    outbox.stage('j1', 'p1', b'wav', {})
    target = sandbox / 'other'
    target.write_bytes(b'untouched')
    sidecar = outbox._root() / 'outbox.sqlite3-journal'
    sidecar.symlink_to(target)
    with pytest.raises(ValueError, match='regular file'):
        outbox.status('j1')
    assert target.read_bytes() == b'untouched'

def test_normal_publish_unaffected(sandbox):
    outbox.stage('j1', 'p1', b'wav', {})
    assert outbox.recover(lambda *args: None) == 1
    assert outbox.status('j1')['state'] == 'published'
