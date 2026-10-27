"""Actual TLS/independent worker processes drain only original admitted work."""
import os
import subprocess
import time

import pytest
from app import auth,service_admission as gate,storage
from test_r210_pull_coordinator import authority as authority,enqueue,economic  # noqa: F401
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401
from test_r210_pull_lifecycle import api as api  # noqa: F401
from test_r210_pull_transport import https as https,cli  # noqa: F401


@pytest.fixture
def drain(authority,api,https,tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_SERVICE_ADMISSION',gate.MODE)
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    with gate.operation('provision'):pass
    return api[2]


@pytest.mark.parametrize('lost',[None,'claim','complete'])
def test_queued_original_work_finishes_over_tls_after_full_service_barrier(authority,api,https,drain,lost):
    job=enqueue(authority)
    before=gate.change(actor=drain,expected_generation=0,draining=True,identifier='drain-tls',confirm=True)
    assert not before['drained'] and before['pending']['by_kind']['pull_execution']==1
    # This is the actual protected application,not a mocked rights/admission API.
    response=api[0].post('/api/ai-jobs/execute',json={'kind':'whisper','plan':{}},headers={'X-MTA-Request':'1'})
    assert response.status_code==503
    args,env,folder=cli(authority,https,'service-drain-node')
    env={**env,'MTA_SERVICE_ADMISSION':'off'}
    if lost:https['drops'][lost]=1
    first=subprocess.run(args,env=env,capture_output=True,timeout=20)
    assert first.returncode==(1 if lost else 0),first.stderr
    if lost:
        if lost=='claim':
            assert economic_in_control(job)==('running','running','open')
            assert not gate.inspect(actor=drain)['drained']
        second=subprocess.run(args,env=env,capture_output=True,timeout=20)
        assert second.returncode==0,second.stderr
    assert economic_in_control(job)==('done','finished','closed')
    assert (authority[2]/'execution-count').read_bytes()==b'1'
    assert gate.inspect(actor=drain)['drained']
    assert not list(folder.rglob('*.sqlite*'))
    assert api[0].post('/api/ai-jobs/execute',json={'kind':'whisper','plan':{}}).status_code==503


def economic_in_control(job):
    with gate.control():return economic(job)


def test_independent_authority_process_is_fenced_before_db_or_queue_mutation(authority,api,https,drain):
    gate.change(actor=drain,expected_generation=0,draining=True,identifier='drain-process',confirm=True)
    code='''from app import auth
from app.regime_operation_fence import FenceBlocked
try:
 with auth.db() as c:c.execute("UPDATE users SET display_name='unauthorized-new-work'")
except FenceBlocked:print('refused')
else:raise SystemExit('New authority process bypassed admission')
'''
    from pathlib import Path
    import sys
    env={**os.environ,'MTA_DATA_DIR':str(auth.data_root()),'PYTHONPATH':str(Path(__file__).resolve().parents[1]),
         'MTA_SERVICE_ADMISSION':'off'}
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=8)
    assert result.returncode==0 and result.stdout.strip()=='refused',result.stderr
    with gate.control(),auth.db() as c:
        assert not c.execute("SELECT 1 FROM users WHERE display_name='unauthorized-new-work'").fetchone()


def test_no_timeout_converts_a_dispatched_remote_worker_into_drained(authority,api,https,drain):
    from app import ai_pull_coordinator as central
    job=enqueue(authority)
    task=central.assignment(authority[1]['credential'],'a'*32)
    gate.change(actor=drain,expected_generation=0,draining=True,identifier='drain-held',confirm=True)
    with gate.control(),auth.db() as c:
        c.execute('UPDATE ai_pull_tasks SET created_at=0 WHERE job_id=?',(job,))
    # Age is not external worker quiescence. Existing worker ownership,nonce,
    # output and financial fences cannot be replaced by this service protocol.
    for _ in range(3):
        value=gate.inspect(actor=drain)
        assert not value['drained'] and value['pending']['by_kind']['pull_execution']==1
        time.sleep(.01)
    with gate.control():
        assert central.assignment(authority[1]['credential'],'a'*32)['nonce']==task['nonce']
