import tempfile
from pathlib import Path
from unittest.mock import patch
from app import ai_arranger_runtime as q


def test_deferred_admission_does_not_execute_before_activation():
    with tempfile.TemporaryDirectory() as root, patch.object(q, '_ROOT', Path(root)):
        called = []
        accepted, job = q.start('project', 'arranger', lambda *args: called.append(True),
                                payload={'schema_version': 1}, defer_spawn=True)
        assert accepted and job['state'] == 'queued'
        assert not called
        assert q.cancel(job['job_id'])['state'] == 'cancelled'
        assert not q.activate(job['job_id'], lambda *args: called.append(True))
        assert not called


def test_admission_block_is_not_bypassed_by_recovery():
    with tempfile.TemporaryDirectory() as root, patch.object(q, '_ROOT', Path(root)):
        accepted, job = q.start('project', 'arranger', lambda *args: None,
                                payload={'schema_version': 1}, defer_spawn=True)
        with q._db() as con:
            con.execute("UPDATE jobs SET state='blocked',message='Ledger admission needs reconciliation' WHERE job_id=?", (job['job_id'],))
        assert q.recover_queued() == 0
        assert q.get(job['job_id'])['state'] == 'blocked'
