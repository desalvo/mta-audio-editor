"""Real Linux kernel adoption/pidfds and original financial recovery after SIGKILL."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

from app import auth, ai_billing, ai_process_guard as guard, worker_cgroup_recovery as scopes
from app.ai_metering_agent import WorkerInterrupted, WorkerNotStarted
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def until(call, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = call()
        if value:
            return value
        threading.Event().wait(.02)
    raise AssertionError('Original worker did not reach the expected actual state')


def descendants(tmp_path, *, leader_exit=False):
    child = tmp_path / 'child.py'
    child.write_text('''import os,sys,time,subprocess
from pathlib import Path
root=Path(sys.argv[1]);(root/'child.pid').write_text(str(os.getpid()))
subprocess.Popen([sys.executable,'-c',"import os,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(60)",str(root/'grandchild.pid')],start_new_session=True)
while not (root/'grandchild.pid').exists():time.sleep(.01)
while True:sum(range(1000))
''')
    leader = tmp_path / 'leader.py'
    leader.write_text('''import os,sys,time,subprocess
from pathlib import Path
root=Path(sys.argv[1]);(root/'leader.pid').write_text(str(os.getpid()))
subprocess.Popen([sys.executable,str(root/'child.py'),str(root)],start_new_session=True)
while not (root/'grandchild.pid').exists():time.sleep(.01)
(root/'ready').touch()
''' + ('' if leader_exit else 'while True:sum(range(1000))\n'))
    return [sys.executable, str(leader), str(tmp_path)]


def dead_tree(tmp_path):
    for name in ('leader', 'child', 'grandchild'):
        pid = int((tmp_path / (name + '.pid')).read_text())
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


@pytest.mark.parametrize('mode', ['normal-leader-exit', 'cancel', 'callback-error', 'timeout'])
def test_kernel_reaps_even_setsid_descendants_and_retains_actual_cpu(tmp_path, mode):
    argv = descendants(tmp_path, leader_exit=mode == 'normal-leader-exit')
    def cancelled():
        if not (tmp_path / 'ready').exists(): return False
        if mode == 'callback-error': raise ValueError('Original observer failed')
        return mode == 'cancel'
    if mode in ('cancel', 'callback-error'):
        with pytest.raises(WorkerInterrupted) as error:
            guard.run(argv, cwd=tmp_path, cancel_check=cancelled, timeout_seconds=5)
        result = error.value.measurement
    else:
        result = guard.run(argv, cwd=tmp_path, timeout_seconds=.5 if mode == 'timeout' else 5)
    assert result.isolated and result.tree_complete and result.usage['cpu_seconds'] > 0
    assert result.exit_code == (0 if mode == 'normal-leader-exit' else -1 if mode == 'timeout' else -signal.SIGKILL)
    dead_tree(tmp_path)


def test_precancel_never_starts_a_worker_or_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(guard.subprocess, 'Popen', lambda *a, **k: pytest.fail('Precanceled process created'))
    with pytest.raises(WorkerNotStarted) as error:
        guard.run([sys.executable, '-c', 'raise SystemExit(99)'], cwd=tmp_path, cancel_check=lambda: True)
    assert error.value.cancelled


def owned(account):
    job = ai_billing.create_job(account, 'whisper')
    credentials = {'worker_id': 'actual-original-guardian', 'claim_token': 'private-original-guardian-token'}
    from app.regime_worker_claims import claim
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE'); claim(c, job, worker_id=credentials['worker_id'], token=credentials['claim_token'])
    return job, credentials


def supervisor(tmp_path, argv, job, credentials):
    code = 'import json,os,sys\nfrom app.ai_process_guard import run\nrun(json.loads(sys.argv[1]),cwd=sys.argv[2],timeout_seconds=60,owner_receipt=json.loads(os.environ["MTA_TEST_OWNER"]))\n'
    return subprocess.Popen([sys.executable, '-c', code, json.dumps(argv), str(tmp_path)],
        env={**os.environ, 'PYTHONPATH': str(ROOT), 'MTA_DATA_DIR': str(auth.data_root()),
             'MTA_TEST_OWNER': json.dumps({'job_id': job, **credentials})},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_actual_supervisor_sigkill_leaves_complete_kernel_receipt_and_original_claim(account, tmp_path):
    job, credentials = owned(account)
    process = supervisor(tmp_path, descendants(tmp_path), job, credentials)
    try:
        until(lambda: (tmp_path / 'ready').exists())
        with auth.db() as c:
            scope, raw = c.execute('SELECT id,binding_json FROM worker_cgroup_scopes WHERE job_id=?', (job,)).fetchone()
            binding = json.loads(raw)
            assert binding['supervisor_pid'] == process.pid
            assert c.execute('SELECT worker_scope_count FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[0] == 1
        process.kill(); process.wait(timeout=5)
        def receipt():
            with auth.db() as c: return scopes._receipt(c, scope)
        proof = until(receipt)
        assert proof['method'].endswith(':supervisor_lost') and proof['populated'] == 0
        assert not proof['financial_settlement']
        dead_tree(tmp_path)
        with auth.db() as c:
            scopes.require_quiescent(c, job)
            assert c.execute('SELECT status,usage_json FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[:] == ('running', '{}')
            assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0] == 'running'
            assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0] == 'open'
        assert scopes.recover(scope, 1, 'actual-guardian-recovery-0001') == proof
        from app import worker_loss_resolution as loss
        with auth.db() as c: plan = loss.preview(c, job, 1)
        approved = loss.resolve(job, 1, {'request_id': 'actual-guardian-loss-0001', 'expected_sha256': plan['expected_sha256'],
            'reason': 'Actual supervisor SIGKILL: operator absorbs unknown consumption without charging the owner.',
            'evidence_sha256': 'a' * 64, 'confirm_operator_loss': True,
            'confirm_no_customer_charge': True, 'confirm_no_reallocation': True})
        assert approved['unknown_consumption'] and approved['customer_charge_micro'] == 0
        with auth.db() as c:
            assert c.execute('SELECT status,usage_json,resource_source FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[:] == ('failed', '{}', 'unmetered')
            assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0] == 'finished'
            assert loss.audit(c)['verified']
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)


def test_original_supervisor_cannot_forge_a_guardian_receipt(account, tmp_path):
    job, credentials = owned(account)
    process = supervisor(tmp_path, descendants(tmp_path), job, credentials)
    try:
        until(lambda: (tmp_path / 'ready').exists())
        with auth.db() as c: scope = c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?', (job,)).fetchone()[0]
        from app.worker_process_guard import quiescent
        with pytest.raises(FenceBlocked, match='original Linux guardian'):
            quiescent(scope, reason='completed')
        with pytest.raises(FenceBlocked, match='receipt unavailable'):
            scopes.recover(scope, 1, 'no-guardian-evidence-0001')
        with auth.db() as c:
            assert scopes._receipt(c, scope) is None
            with pytest.raises(FenceBlocked): scopes.require_quiescent(c, job)
    finally:
        process.kill(); process.wait(timeout=5)
        def stopped():
            with auth.db() as c: return scopes._receipt(c, scope)
        until(stopped)
        dead_tree(tmp_path)


def test_guard_never_signals_a_sibling_unrelated_to_its_job(tmp_path):
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
    try:
        result = guard.run(descendants(tmp_path, leader_exit=True), cwd=tmp_path, timeout_seconds=5)
        assert result.tree_complete and unrelated.poll() is None
        dead_tree(tmp_path)
    finally:
        unrelated.kill(); unrelated.wait(timeout=5)


def test_short_lived_child_cpu_is_collected_even_without_proc_samples(tmp_path):
    child = 'import time;end=time.monotonic()+.2\nwhile time.monotonic()<end:sum(range(1000))'
    code = 'import subprocess,sys\nsubprocess.run([sys.executable,"-c",' + repr(child) + '],check=True)'
    result = guard.run([sys.executable, '-c', code], cwd=tmp_path)
    assert result.tree_complete and result.isolated and result.usage['cpu_seconds'] >= .15


def test_empty_proc_samples_cannot_turn_a_live_child_into_quiescence(tmp_path, monkeypatch):
    state = {'cpu': 0., 'reaped': 0, 'exit_code': None}
    monkeypatch.setattr(guard, '_children', lambda: [])
    child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(.25)'])
    try:
        assert not guard._reap(child.pid, state)
        guard._stop_children()
        assert not guard._reap(child.pid, state) and child.poll() is None
    finally:
        child.kill(); child.wait(timeout=5)


def test_lost_guardian_is_not_replaced_by_a_pid_guess_or_fabricated_cpu(account, tmp_path):
    job, credentials = owned(account)
    worker = tmp_path / 'cooperative.py'
    worker.write_text('import os,time\nfrom pathlib import Path\np=Path(' + repr(str(tmp_path)) + ')\n(p/"worker.pid").write_text(str(os.getpid()))\nwhile not (p/"exit").exists():time.sleep(.02)\n')
    process = supervisor(tmp_path, [sys.executable, str(worker)], job, credentials)
    try:
        until(lambda: (tmp_path / 'worker.pid').exists())
        with auth.db() as c:
            scope, raw = c.execute('SELECT id,binding_json FROM worker_cgroup_scopes WHERE job_id=?', (job,)).fetchone()
            guardian = json.loads(raw)['guardian_pid']
        fd = os.pidfd_open(guardian)
        try: signal.pidfd_send_signal(fd, signal.SIGKILL)
        finally: os.close(fd)
        process.wait(timeout=5)
        assert process.returncode != 0
        with auth.db() as c:
            assert scopes._receipt(c, scope) is None
            with pytest.raises(FenceBlocked): scopes.require_quiescent(c, job)
        with pytest.raises(FenceBlocked, match='receipt unavailable'):
            scopes.recover(scope, 1, 'missing-real-guardian-0001')
        with pytest.raises(FenceBlocked):
            ai_billing.finish_job(job, 'done', {'cpu_seconds': 1}, source='worker', **credentials)
        with auth.db() as c:
            row = c.execute('SELECT status,usage_json FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()
            assert row[:] == ('running', '{}')
    finally:
        (tmp_path / 'exit').touch()
        if process.poll() is None: process.kill(); process.wait(timeout=5)


def test_ace_external_service_cannot_be_cleared_with_only_a_local_tree_receipt(account, tmp_path):
    job = ai_billing.create_job(account, 'ace-step')
    credentials = {'worker_id': 'external-service-fixture', 'claim_token': 'synthetic-external-claim'}
    from app.regime_worker_claims import claim
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE'); claim(c, job, worker_id=credentials['worker_id'], token=credentials['claim_token'])
    process = supervisor(tmp_path, descendants(tmp_path), job, credentials)
    try:
        until(lambda: (tmp_path / 'ready').exists())
        process.kill(); process.wait(timeout=5)
        def receipt():
            with auth.db() as c:
                row = c.execute('SELECT id,binding_json FROM worker_cgroup_scopes WHERE job_id=?', (job,)).fetchone()
                return scopes._receipt(c, row[0])
        until(receipt)
        dead_tree(tmp_path)
        from app import worker_loss_resolution as loss
        with auth.db() as c:
            with pytest.raises(FenceBlocked, match='External ACE service quiescence'):
                loss.preview(c, job, 1)
            assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[0] == 'running'
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)


def test_real_registered_ffmpeg_tree_settles_only_after_guardian_kernel_receipt(account, tmp_path, monkeypatch):
    from app import ai_metering_agent as agent, ai_arranger_runtime as queue
    from test_r208_unified_adapter_billing_e2e import source_audio
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'actual-ffmpeg-queue')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.delenv('MTA_AI_WORKER_BACKING_VOCALS_EXECUTABLE', raising=False)
    monkeypatch.delenv('MTA_LEAD_BACKING_COMMAND', raising=False)
    monkeypatch.setattr(agent, '_descendants', lambda _: pytest.fail('Proc samples certified a tree'))
    payload, meta = agent.execute_registered_worker(account, 'backing-vocals',
        {'model': 'ffmpeg-center-side'}, source_wav=source_audio())
    assert payload[:2] == b'PK' and meta['usage']['cpu_seconds'] > 0 and meta['process_tree_metered']
    with auth.db() as c:
        job = c.execute('SELECT status,worker_scope_count FROM ai_compute_jobs WHERE id=?', (meta['job_id'],)).fetchone()
        assert job[:] == ('done', 1)
        scope = c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?', (meta['job_id'],)).fetchone()[0]
        assert scopes._receipt(c, scope)['method'].endswith(':completed')


@pytest.mark.parametrize('regime', ['COMMERCIAL', 'NON_COMMERCIAL'])
def test_real_http_supervisor_loss_admin_recovery_and_original_request_no_reexecution(account, tmp_path, monkeypatch, regime):
    from concurrent.futures import ThreadPoolExecutor
    import socket
    import httpx
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app import ai_access, ai_billing_routes, resource_routes, ai_arranger_runtime as queue
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'http-queue')
    (auth.data_root() / 'service-regime.json').write_text(json.dumps({'regime': regime, 'revision': 0}))
    with auth.db() as c:
        c.execute('UPDATE regime_fence_state SET regime=? WHERE singleton=1', (regime,))
    token = ai_access.issue(account, 'Actual HTTP supervisor crash')['token']
    argv = descendants(tmp_path)
    worker = tmp_path / 'protocol_worker.py'
    worker.write_text('import runpy,sys\nsys.argv=' + repr(argv[1:]) + '\nrunpy.run_path(' + repr(argv[1]) + ',run_name="__main__")\n')
    worker.chmod(0o700)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    bootstrap = '''import sys
from pathlib import Path
from fastapi import FastAPI
import uvicorn
from app import ai_billing_routes,ai_worker_registry,ai_arranger_runtime as queue
queue._ROOT=Path(sys.argv[2])
original=ai_worker_registry.resolve_worker
ai_worker_registry.resolve_worker=lambda kind:Path(sys.argv[1]) if kind=='whisper' else original(kind)
app=FastAPI();app.include_router(ai_billing_routes.router)
@app.get('/guard-test-ready')
def ready():return {'ready':True}
uvicorn.run(app,host='127.0.0.1',port=int(sys.argv[3]),log_level='error',access_log=False)
'''
    server = subprocess.Popen([sys.executable, '-c', bootstrap, str(worker), str(queue._ROOT), str(port)],
        env={**os.environ, 'PYTHONPATH': str(ROOT), 'MTA_DATA_DIR': str(auth.data_root()),
             'MTA_AI_WORKER_ENABLED': 'true', 'MTA_AI_EXECUTION_MODE': 'local'},
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base = f'http://127.0.0.1:{port}'
    def ready():
        if server.poll() is not None: raise AssertionError(server.stderr.read().decode())
        try: return httpx.get(base + '/guard-test-ready', timeout=.2, trust_env=False).status_code == 200
        except httpx.HTTPError: return False
    key = 'original-http-guard-' + regime.lower()
    headers = {'Authorization': 'Bearer ' + token, 'X-MTA-AI-Idempotency-Key': key}
    try:
        until(ready)
        with ThreadPoolExecutor(1) as pool:
            request = pool.submit(httpx.post, base + '/api/ai-jobs/execute', headers=headers,
                                  json={'kind': 'whisper', 'plan': {}}, timeout=15, trust_env=False)
            until(lambda: (tmp_path / 'ready').exists())
            with auth.db() as c:
                job = c.execute('SELECT id FROM ai_compute_jobs WHERE user_id=?', (account,)).fetchone()[0]
                scope = c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?', (job,)).fetchone()[0]
            server.kill(); server.wait(timeout=5)
            with pytest.raises(httpx.HTTPError): request.result(timeout=5)
        def receipt():
            with auth.db() as c: return scopes._receipt(c, scope)
        until(receipt)
        dead_tree(tmp_path)
        app = FastAPI(); app.include_router(resource_routes.router); app.include_router(ai_billing_routes.router)
        with TestClient(app) as client:
            client.cookies.update(cookie(1))
            url = '/api/admin/service-regime/worker-losses/' + job
            preview = client.get(url + '/preview')
            assert preview.status_code == 200, preview.text
            body = {'request_id': 'http-guardian-loss-' + regime.lower(),
                'expected_sha256': preview.json()['expected_sha256'], 'reason': 'Actual HTTP supervisor crash with independent kernel tree cleanup; operator absorbs unknown cost.',
                'evidence_sha256': 'b' * 64, 'confirm_operator_loss': True,
                'confirm_no_customer_charge': True, 'confirm_no_reallocation': True}
            approved = client.post(url + '/resolve', json=body, headers={'X-MTA-Request': '1'})
            assert approved.status_code == 200, approved.text
            assert approved.json()['unknown_consumption'] and approved.json()['customer_charge_micro'] == 0
            assert client.post(url + '/resolve', json=body, headers={'X-MTA-Request': '1'}).json() == approved.json()
            duplicate = client.post('/api/ai-jobs/execute', headers=headers, json={'kind': 'whisper', 'plan': {}})
            assert duplicate.status_code == 409 and 'duplicate_request' in duplicate.text
        with auth.db() as c:
            assert c.execute('SELECT count(*) FROM ai_compute_jobs WHERE user_id=?', (account,)).fetchone()[0] == 1
            assert c.execute('SELECT status,usage_json,resource_source FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[:] == ('failed', '{}', 'unmetered')
            assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0] == 'finished'
            assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0] == 'closed'
    finally:
        if server.poll() is None: server.kill(); server.wait(timeout=5)


def test_guardian_can_finish_original_cleanup_during_drain_without_releasing_its_debt(account, tmp_path, monkeypatch):
    from app import service_admission as admission
    monkeypatch.setenv('MTA_SERVICE_ADMISSION', admission.MODE)
    with admission.operation('provision-original-guardian'): pass
    with admission.control(): job, credentials = owned(account)
    process = supervisor(tmp_path, descendants(tmp_path), job, credentials)
    try:
        until(lambda: (tmp_path / 'ready').exists())
        stopped = admission.change(actor=1, expected_generation=0, draining=True,
                                   identifier='drain-original-guardian', confirm=True)
        assert stopped['phase'] == 'draining' and not stopped['drained']
        with admission.control(), auth.db() as c:
            scope = c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=?', (job,)).fetchone()[0]
        process.kill(); process.wait(timeout=5)
        def receipt():
            with admission.control(), auth.db() as c: return scopes._receipt(c, scope)
        until(receipt)
        dead_tree(tmp_path)
        # Kernel cleanup is an allowed original continuation. It cannot clear
        # the separate financial claim or silently authorize cutover/resume.
        after = admission.inspect(actor=1)
        assert after['phase'] == 'draining' and not after['drained']
        with admission.control(), auth.db() as c:
            assert scopes._receipt(c, scope)['populated'] == 0
            assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (job,)).fetchone()[0] == 'running'
            assert c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?', ('job:ledger:' + job,)).fetchone()[0] == 'running'
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=5)
