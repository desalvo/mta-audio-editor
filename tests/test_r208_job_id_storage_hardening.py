"""Security regression: durable AI job identifiers cannot escape runtime state."""
import os
from pathlib import Path
import pytest

from app import ai_arranger_runtime as queue


def test_job_id_rejects_path_components_before_db_write(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    for value in ('../outside', 'a/b', 'a\\b', '', ' space', '.hidden'):
        with pytest.raises(ValueError, match='Invalid AI job identifier'):
            queue.start('project', 'arranger', lambda _: None, job_id=value)
    assert not (tmp_path / 'jobs.sqlite3').exists()


def test_job_store_is_private(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    with queue._db() as con:
        con.execute('SELECT 1')
    assert os.stat(tmp_path).st_mode & 0o777 == 0o700
    assert os.stat(tmp_path / 'jobs.sqlite3').st_mode & 0o777 == 0o600
