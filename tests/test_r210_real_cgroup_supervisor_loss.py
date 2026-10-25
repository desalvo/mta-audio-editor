"""Opt-in delegated-kernel test. Never substitutes synthetic cgroup files."""
import os
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

import pytest

from app import ai_cgroup_metering as groups
from test_r210_subscriptions import account as account  # noqa: F401


def test_kernel_kills_nested_workers_after_actual_supervisor_loss(tmp_path, account):
    configured = os.environ.get('MTA_TEST_CGROUP_PARENT')
    if not configured:
        pytest.skip('Requires an explicitly supplied isolated writable cgroup v2 delegation')
    parent = Path(configured).resolve(strict=True)
    assert parent != Path('/sys/fs/cgroup') and parent.is_relative_to('/sys/fs/cgroup')
    root = parent / ('mta-test-' + uuid.uuid4().hex)
    root.mkdir(mode=0o700)
    proc = None
    try:
        from app import ai_billing, auth, worker_cgroup_recovery as recovery
        from app.regime_worker_claims import claim
        jid=ai_billing.create_job(account,'whisper')
        credentials={'worker_id':'kernel-test-supervisor','claim_token':'isolated-kernel-test-token'}
        with auth.db() as c:
            c.execute('BEGIN IMMEDIATE');claim(c,jid,worker_id=credentials['worker_id'],token=credentials['claim_token'])
        (root / 'cgroup.subtree_control').write_text('+cpu +io')
        ready = tmp_path / 'worker-ready'
        child_ready = tmp_path / 'nested-ready'
        worker = tmp_path / 'worker.py'
        worker.write_text('''import os,sys,time,subprocess
from pathlib import Path
root,ready,nested_ready=map(Path,sys.argv[1:])
group=next(root.glob('mta-*'))
# A nested cgroup and a new session defeat direct cgroup.procs/killpg cleanup.
nested=group/'descendant';nested.mkdir()
code="import os,sys,time;from pathlib import Path;(Path(sys.argv[1])/'cgroup.procs').write_text(str(os.getpid()));Path(sys.argv[2]).touch();time.sleep(60)"
subprocess.Popen([sys.executable,'-c',code,str(nested),str(nested_ready)],start_new_session=True)
deadline=time.monotonic()+10
while not nested_ready.exists() and time.monotonic()<deadline:time.sleep(.01)
assert nested_ready.exists()
ready.touch()
time.sleep(60)
''')
        supervisor = '''import sys,json,os
from app.ai_cgroup_metering import run_cgroup_process
run_cgroup_process([sys.executable,*sys.argv[2:]],cwd=sys.argv[1],parent=sys.argv[3],owner_receipt=json.loads(os.environ['MTA_TEST_RECOVERY_RECEIPT']))
'''
        proc = subprocess.Popen([sys.executable, '-c', supervisor, str(tmp_path),
                                 str(worker), str(root), str(ready), str(child_ready)],
                                env={**os.environ,'MTA_TEST_RECOVERY_RECEIPT':json.dumps({'job_id':jid,**credentials})})
        deadline = time.monotonic() + 15
        while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
            threading.Event().wait(.02)
        assert ready.exists(), 'Worker did not reach its nested cgroup; inspect supervisor stderr'
        job_groups = list(root.glob('mta-*'))
        assert len(job_groups) == 1
        job_group = job_groups[0]
        proc.kill()
        proc.wait(timeout=5)
        with pytest.raises(RuntimeError, match='contains processes'):
            groups._assert_empty(job_group)
        with auth.db() as c:
            scope=c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?',(jid,)).fetchone()[0]
        proof=recovery.recover(scope,1,'kernel-supervisor-loss-test')
        assert proof['financial_settlement'] is False
        groups._assert_empty(job_group)
        with auth.db() as c:
            assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()[0]=='running'
            assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+jid,)).fetchone()[0]=='running'
        from app.worker_loss_resolution import preview,resolve
        with auth.db() as c:plan=preview(c,jid,1)
        approved=resolve(jid,1,{'request_id':'kernel-loss-approval-0001','expected_sha256':plan['expected_sha256'],
          'reason':'Isolated kernel crash test: the operator absorbs all unknown service costs.',
          'evidence_sha256':'a'*64,'confirm_operator_loss':True,'confirm_no_customer_charge':True,'confirm_no_reallocation':True})
        assert approved['unknown_consumption'] and approved['customer_charge_micro']==0
        with auth.db() as c:
            assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?',(jid,)).fetchone()[0]=='failed'
            assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+jid,)).fetchone()[0]=='finished'
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        # Only this test's new private subtree is ever terminated/removed.
        for job_group in root.glob('mta-*'):
            groups._stop_cgroup(job_group)
        for child in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if child.is_dir():
                child.rmdir()
        root.rmdir()
