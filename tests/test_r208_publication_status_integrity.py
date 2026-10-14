import json
import sqlite3
import pytest
from app import ai_publish_outbox as outbox
from app import ai_arranger_runtime as runtime


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path)
    return tmp_path


def _staged():
    outbox.stage('job_integrity_1', 'project-A', b'RIFFtest', {'source': 'test'})


def _tamper(root, statement, args=()):
    with sqlite3.connect(root / 'publication' / 'outbox.sqlite3') as con:
        con.execute(statement, args)


def test_invalid_published_completion_cannot_be_reported(configured):
    _staged()
    _tamper(configured, "UPDATE publications SET state='published' WHERE job_id='job_integrity_1'")
    with pytest.raises(ValueError, match='completion timestamp'):
        outbox.status('job_integrity_1')
    with pytest.raises(ValueError, match='completion timestamp'):
        outbox.published_jobs()


def test_corrupted_metadata_cannot_claim_published(configured):
    _staged()
    _tamper(configured, "UPDATE publications SET metadata='[]', state='published', published_at=staged_at WHERE job_id='job_integrity_1'")
    with pytest.raises(ValueError, match='metadata'):
        outbox.status('job_integrity_1')
    with pytest.raises(ValueError, match='metadata'):
        outbox.published_jobs()


def test_valid_publish_still_visible(configured):
    _staged()
    assert outbox.recover(lambda *args: None) == 1
    assert outbox.status('job_integrity_1')['state'] == 'published'
    assert outbox.published_jobs() == ['job_integrity_1']


def test_corrupt_pending_record_blocks_global_published_listing(configured):
    _staged()
    _tamper(configured, "UPDATE publications SET audio_sha256='wrong' WHERE job_id='job_integrity_1'")
    with pytest.raises(ValueError, match='digest'):
        outbox.published_jobs()
