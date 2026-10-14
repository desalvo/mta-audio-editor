import sqlite3
import pytest
from app import ai_publish_outbox as outbox
from app import ai_arranger_runtime as runtime

@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path)
    return tmp_path

def alter(root, sql):
    with sqlite3.connect(root / 'publication' / 'outbox.sqlite3') as con:
        con.execute(sql)

def test_pending_corrupt_metadata_never_reaches_callback(root):
    outbox.stage('safe1', 'proj', b'wav', {'mode':'test'})
    alter(root, "UPDATE publications SET metadata='[]'")
    seen=[]
    with pytest.raises(ValueError, match='metadata'):
        outbox.recover(lambda *args: seen.append(args))
    assert not seen

def test_pending_invalid_timestamp_never_reaches_callback(root):
    outbox.stage('safe2', 'proj', b'wav', {'mode':'test'})
    alter(root, "UPDATE publications SET published_at=staged_at WHERE job_id='safe2'")
    with pytest.raises(ValueError, match='Pending publication'):
        outbox.recover(lambda *args: None)

def test_callback_tampering_record_prevents_false_publication(root):
    outbox.stage('safe3', 'proj', b'wav', {'mode':'test'})
    def callback(*args):
        alter(root, "UPDATE publications SET project_id='other' WHERE job_id='safe3'")
    with pytest.raises(ValueError, match='changed during callback'):
        outbox.recover(callback)
    with sqlite3.connect(root / 'publication' / 'outbox.sqlite3') as con:
        assert con.execute("SELECT state FROM publications WHERE job_id='safe3'").fetchone()[0]=='pending'

def test_corrupt_record_rejected_during_stage_replay(root):
    outbox.stage('safe4', 'proj', b'wav', {'mode':'test'})
    alter(root, "UPDATE publications SET staged_at=0 WHERE job_id='safe4'")
    with pytest.raises(ValueError, match='staging timestamp'):
        outbox.stage('safe4', 'proj', b'wav', {'mode':'test'})
