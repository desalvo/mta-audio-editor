"""Real ledger/claim/API with synthetic kernel files; no kernel certification."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

import pytest

from app import ai_billing, auth, ai_arranger_runtime as queue, worker_cgroup_recovery as recovery
from app.regime_operation_fence import FenceBlocked
from app.regime_worker_claims import claim
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401
from test_r210_worker_quiescence_safety import fake_cgroup as fake_cgroup  # noqa: F401


@pytest.fixture
def kernel(tmp_path, monkeypatch):
    root = tmp_path / 'delegated'
    root.mkdir()
    group = root / ('mta-' + uuid.uuid4().hex)
    group.mkdir()
    (group / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
    (group / 'cgroup.kill').touch()
    original = Path.is_relative_to
    monkeypatch.setattr(Path, 'is_relative_to', lambda path, other:
                        True if path == root else original(path, other))
    monkeypatch.setattr(recovery, '_kernel_filesystem', lambda _: None)
    return group


@pytest.fixture
def owned(account, kernel):
    plan(account)
    from app import resource_accounts as resources
    resources.grant(account, 1000, 'fixture funds', 1, 'worker-recovery-funds')
    jid = ai_billing.create_job(account, 'whisper')
    credentials = {'worker_id': 'original-worker', 'claim_token': 'original-private-token'}
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        claim(c, jid, worker_id=credentials['worker_id'], token=credentials['claim_token'])
    scope = recovery.register(kernel, jid, credentials)
    return jid, scope, credentials


def dead(monkeypatch):
    monkeypatch.setattr(queue, '_process_identity', lambda _: None)


def economic_state():
    with auth.db() as c:
        queries={'jobs':'SELECT * FROM ai_compute_jobs','claims':'SELECT * FROM regime_worker_claims',
                 'fences':'SELECT * FROM regime_fence_operations','contracts':'SELECT * FROM resource_job_contracts',
                 'budgets':'SELECT * FROM resource_job_budgets','credits':'SELECT * FROM resource_credits'}
        return {name:[tuple(r) for r in c.execute(query)] for name,query in queries.items()}


def test_registration_commits_original_binding_without_exposing_token(owned):
    jid, scope, credentials = owned
    with auth.db() as c:
        row = c.execute('SELECT * FROM worker_cgroup_scopes WHERE id=?', (scope,)).fetchone()
        b = json.loads(row['binding_json'])
        assert b['job_id'] == jid and b['supervisor_identity']
        assert credentials['claim_token'] not in row['binding_json']
        assert c.execute('SELECT worker_scope_count FROM ai_compute_jobs').fetchone()[0] == 1
        assert recovery.report(c)['pending'] == 1


@pytest.mark.parametrize('current', ['', 'same'])
def test_live_or_unknown_supervisor_never_stopped(owned, monkeypatch, current):
    if current == '':
        monkeypatch.setattr(queue, '_process_identity', lambda _: '')
    monkeypatch.setattr(recovery, '_stop', lambda _: pytest.fail('Unproven supervisor death'))
    with pytest.raises(FenceBlocked, match='live or its death'):
        recovery.recover(owned[1], 1, 'recovery-request-0001')


def test_recovery_preserves_actual_contract_reservations_and_money(owned, monkeypatch):
    before = economic_state()
    dead(monkeypatch)
    e = recovery.recover(owned[1], 1, 'recovery-request-0001')
    assert e['financial_settlement'] is False and e['populated'] == 0
    assert economic_state() == before
    with auth.db() as c:
        recovery.require_quiescent(c, owned[0])
        assert recovery.report(c)['pending'] == 0


def test_recursive_kernel_stop_persists_only_after_empty(owned, kernel, monkeypatch):
    (kernel / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
    dead(monkeypatch)
    observed = []
    def advance(_):
        assert (kernel / 'cgroup.kill').read_text() == '1'
        observed.append(True)
        (kernel / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
    monkeypatch.setattr(recovery.time, 'sleep', advance)
    recovery.recover(owned[1], 1, 'recovery-request-0001')
    assert observed == [True]


def test_failed_kernel_stop_keeps_financial_claim_and_no_false_receipt(owned, monkeypatch):
    before = economic_state()
    dead(monkeypatch)
    monkeypatch.setattr(recovery, '_stop', lambda _: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(PermissionError):
        recovery.recover(owned[1], 1, 'recovery-request-0001')
    assert economic_state() == before
    with auth.db() as c:
        assert recovery.report(c)['pending'] == 1


@pytest.mark.parametrize('method', ['finish', 'idempotent', 'fence'])
def test_uncertain_scope_blocks_every_financial_finalization(owned, method):
    jid, _, credentials = owned
    before = economic_state()
    with pytest.raises(FenceBlocked, match='quiescence'):
        if method == 'finish':
            ai_billing.finish_job(jid, 'failed', **credentials)
        elif method == 'idempotent':
            ai_billing.finish_job_idempotent(jid, 'failed', **credentials)
        else:
            from app.regime_job_fence import settle_metered_job
            with auth.db() as c:
                c.execute('BEGIN IMMEDIATE')
                settle_metered_job(c, jid)
    assert economic_state() == before


def test_original_owner_clean_exit_then_normal_billing_works(owned):
    jid, scope, credentials = owned
    recovery.owner_quiescent(scope)
    ai_billing.finish_job(jid, 'done', {'cpu_seconds': 1}, source='cgroup', **credentials)
    assert ai_billing.finish_job_idempotent(jid, 'done', {'cpu_seconds': 1}, source='cgroup', **credentials)['already_finalized']
    with auth.db() as c:
        assert recovery.report(c)['verified']
        assert c.execute('SELECT state FROM regime_worker_claims').fetchone()[0] == 'finished'


def test_bootstrap_enters_before_exec_under_original_scope(owned,kernel):
    (kernel/'cgroup.procs').touch()
    recovery.enter_before_exec(owned[1],str(kernel))
    assert (kernel/'cgroup.procs').read_text()==str(os.getpid())


@pytest.mark.parametrize('state',['dead','unknown','quiesced'])
def test_late_bootstrap_cannot_start_after_owner_loss_or_quiescence(owned,kernel,monkeypatch,state):
    (kernel/'cgroup.procs').touch()
    if state=='quiesced':recovery.owner_quiescent(owned[1])
    else:monkeypatch.setattr(queue,'_process_identity',lambda _:None if state=='dead' else '')
    with pytest.raises(FenceBlocked):recovery.enter_before_exec(owned[1],str(kernel))
    assert (kernel/'cgroup.procs').read_text()==''


def test_recovery_receipt_blocks_delayed_spawn_even_if_supervisor_is_reused(owned,kernel,monkeypatch):
    (kernel/'cgroup.procs').touch()
    original=queue._process_identity
    dead(monkeypatch);recovery.recover(owned[1],1,'recovery-before-bootstrap')
    monkeypatch.setattr(queue,'_process_identity',original)
    with pytest.raises(FenceBlocked,match='already quiesced'):
        recovery.enter_before_exec(owned[1],str(kernel))
    assert not (kernel/'cgroup.procs').read_text()


def test_bootstrap_join_and_recovery_cannot_cross_the_write_barrier(owned,kernel,monkeypatch):
    (kernel/'cgroup.procs').touch()
    entered=threading.Event();release=threading.Event();bootstrap_identity=[]
    original_group=recovery._group;original_identity=queue._process_identity(os.getpid())
    @contextmanager
    def guarded(*a,**kw):
        with original_group(*a,**kw) as value:
            bootstrap=threading.get_ident() in bootstrap_identity
            if bootstrap:
                entered.set();assert release.wait(5)
            yield value
            if bootstrap:(kernel/'cgroup.events').write_text('populated 1\n')
    monkeypatch.setattr(recovery,'_group',guarded)
    monkeypatch.setattr(queue,'_process_identity',lambda _:original_identity if threading.get_ident() in bootstrap_identity else None)
    def join():
        bootstrap_identity.append(threading.get_ident())
        recovery.enter_before_exec(owned[1],str(kernel))
    def stopped(_):
        assert (kernel/'cgroup.procs').read_text()==str(os.getpid())
        (kernel/'cgroup.events').write_text('populated 0\n')
    monkeypatch.setattr(recovery,'_stop',stopped)
    with ThreadPoolExecutor(2) as pool:
        joining=pool.submit(join)
        try:
            assert entered.wait(5)
            with auth.db() as c:
                c.execute('PRAGMA busy_timeout=0')
                with pytest.raises(sqlite3.OperationalError,match='locked'):c.execute('BEGIN IMMEDIATE')
            recovering=pool.submit(recovery.recover,owned[1],1,'recovery-launch-barrier')
        finally:release.set()
        joining.result(timeout=5)
        assert recovering.result(timeout=5)['populated']==0


def test_pagination_and_invalid_windows_are_explicit(owned,kernel):
    recovery.register(kernel,owned[0],owned[2]);recovery.register(kernel,owned[0],owned[2])
    with auth.db() as c:
        page=recovery.report(c,limit=1,offset=1)
        assert len(page['scopes'])==1 and page['total']==3 and page['truncated']
        with pytest.raises(ValueError):recovery.report(c,limit=0)
        with pytest.raises(ValueError):recovery.report(c,offset=-1)


def test_original_supervisor_ownership_cannot_be_reused_by_new_process(owned,kernel,monkeypatch):
    monkeypatch.setattr(queue,'_process_identity',lambda _:'another-process-creation-identity')
    with pytest.raises(FenceBlocked,match='cannot be transferred'):
        recovery.register(kernel,owned[0],owned[2])
    with auth.db() as c:assert c.execute('SELECT worker_scope_count FROM ai_compute_jobs').fetchone()[0]==1


def test_missing_history_refuses_new_launch_before_any_effect(owned,kernel):
    with auth.db() as c:
        c.execute('DROP TRIGGER worker_cgroup_scopes_immutable_delete');c.execute('DELETE FROM worker_cgroup_scopes')
    with pytest.raises(FenceBlocked,match='history incomplete'):
        recovery.register(kernel,owned[0],owned[2])


def test_missing_proof_blocks_second_scope_even_if_one_is_quiescent(owned, kernel):
    recovery.owner_quiescent(owned[1])
    second = recovery.register(kernel, owned[0], owned[2])
    assert second != owned[1]
    with auth.db() as c:
        with pytest.raises(FenceBlocked, match='quiescence'):
            recovery.require_quiescent(c, owned[0])


def test_reused_supervisor_pid_proves_old_process_death_without_signaling_new_one(owned, monkeypatch):
    monkeypatch.setattr(queue,'_process_identity',lambda _:'different-original-start-tick')
    monkeypatch.setattr(os,'kill',lambda *a:pytest.fail('Must not signal a reused PID'))
    assert recovery.recover(owned[1],1,'recovery-request-0001')['populated']==0


def test_crash_before_audit_commit_retries_without_changing_money(owned, monkeypatch):
    dead(monkeypatch)
    before=economic_state();original=recovery._store
    def fail(*a,**kw):
        original(*a,**kw)
        raise RuntimeError('Crash before commit')
    monkeypatch.setattr(recovery,'_store',fail)
    with pytest.raises(RuntimeError):recovery.recover(owned[1],1,'recovery-request-0001')
    with auth.db() as c:assert recovery.report(c)['pending']==1
    assert economic_state()==before
    monkeypatch.setattr(recovery,'_store',original)
    recovery.recover(owned[1],1,'recovery-request-0001')
    assert economic_state()==before


def test_real_supervisor_crash_after_durable_registration_before_spawn(account,kernel,tmp_path):
    jid=ai_billing.create_job(account,'whisper');credentials={'worker_id':'crash-owner','claim_token':'fixture-private-token'}
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');claim(c,jid,worker_id=credentials['worker_id'],token=credentials['claim_token'])
    ready=tmp_path/'registered.json'
    script='''import json,os,sys,time
from pathlib import Path
from app import worker_cgroup_recovery as r
os.getpid=lambda:int(Path('/proc/self/stat').read_text().split()[0])
group=Path(sys.argv[1]);original=Path.is_relative_to
Path.is_relative_to=lambda p,o:True if p==group.parent else original(p,o)
r._kernel_filesystem=lambda fd:None
scope=r.register(group,sys.argv[2],json.loads(sys.argv[3]))
Path(sys.argv[4]).write_text(scope)
time.sleep(30)
'''
    proc=subprocess.Popen([sys.executable,'-c',script,str(kernel),jid,json.dumps(credentials),str(ready)])
    try:
        deadline=time.monotonic()+5
        while not ready.exists() and proc.poll() is None and time.monotonic()<deadline:threading.Event().wait(.01)
        assert ready.exists()
        before=economic_state()
        proc.kill();proc.wait(timeout=5)
        proof=recovery.recover(ready.read_text(),1,'actual-death-request-0001')
        assert proof['method']=='dead_supervisor_kernel_quiescence' and economic_state()==before
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=5)


@pytest.mark.parametrize('field', ['boot', 'machine', 'namespace'])
def test_changed_host_boot_namespace_cannot_reinterpret_scope(owned, monkeypatch, field):
    original = recovery._host()
    original[field] = 'different'
    monkeypatch.setattr(recovery, '_host', lambda: original)
    dead(monkeypatch)
    with pytest.raises(FenceBlocked, match='original host'):
        recovery.recover(owned[1], 1, 'recovery-request-0001')


def test_recreated_cgroup_inode_is_not_the_original_worker_scope(owned, kernel, monkeypatch):
    old = kernel.with_name('retained-original')
    kernel.rename(old)
    kernel.mkdir()
    (kernel / 'cgroup.events').write_text('populated 0\n')
    dead(monkeypatch)
    with pytest.raises(FenceBlocked, match='replaced'):
        recovery.recover(owned[1], 1, 'recovery-request-0001')


def test_group_symlink_refused_without_signaling(owned, kernel, monkeypatch):
    old = kernel.with_name('retained-original')
    kernel.rename(old)
    kernel.symlink_to(old, target_is_directory=True)
    dead(monkeypatch)
    with pytest.raises((OSError, FenceBlocked)):
        recovery.recover(owned[1], 1, 'recovery-request-0001')


def test_non_kernel_directory_is_refused_even_with_similar_files(tmp_path):
    fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(FenceBlocked, match='actual cgroup'):
            recovery._kernel_filesystem(fd)
    finally:
        os.close(fd)


def test_recovery_request_is_durable_idempotent_under_concurrency(owned, monkeypatch):
    dead(monkeypatch)
    with ThreadPoolExecutor(3) as pool:
        results = list(pool.map(lambda _: recovery.recover(owned[1], 1, 'recovery-request-0001'), range(3)))
    assert results[0] == results[1] == results[2]
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM worker_cgroup_receipts').fetchone()[0] == 1


@pytest.mark.parametrize('table', ['worker_cgroup_scopes', 'worker_cgroup_receipts'])
def test_lost_journal_schema_is_not_recreated(owned, kernel, table):
    recovery.owner_quiescent(owned[1])
    with auth.db() as c:
        c.execute('PRAGMA foreign_keys=OFF')
        c.execute('DROP TABLE '+table)
    with pytest.raises(FenceBlocked, match='Incomplete'):
        recovery.register(kernel, owned[0], owned[2])
    with auth.db() as c:
        assert recovery.report(c)['verified'] is False
        with pytest.raises(FenceBlocked):recovery.require_quiescent(c, owned[0])


@pytest.mark.parametrize('field', ['binding_json', 'sha256'])
def test_tampered_binding_fails_closed(owned, field):
    with auth.db() as c:
        c.execute('DROP TRIGGER worker_cgroup_scopes_immutable_update')
        query={'binding_json':'UPDATE worker_cgroup_scopes SET binding_json=?',
               'sha256':'UPDATE worker_cgroup_scopes SET sha256=?'}[field]
        c.execute(query, ('{}',))
        assert recovery.report(c)['verified'] is False
        with pytest.raises(FenceBlocked):recovery.require_quiescent(c, owned[0])


def test_missing_counted_scope_does_not_look_quiescent(owned):
    with auth.db() as c:
        c.execute('DROP TRIGGER worker_cgroup_scopes_immutable_delete')
        c.execute('DELETE FROM worker_cgroup_scopes')
        assert recovery.report(c)['verified'] is False
        with pytest.raises(FenceBlocked, match='incomplete'):
            recovery.require_quiescent(c, owned[0])


def test_immutable_rows_and_scoped_retired_owner_erasure(owned, account):
    from app.account_lifecycle import init, _rows_for_user
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM worker_cgroup_scopes')
    recovery.owner_quiescent(owned[1])
    with auth.db() as c:
        init(c)
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):recovery.authorize_account_erasure(c, account, 1)
        c.execute('UPDATE users SET active=0 WHERE id=?', (account,))
        c.execute("INSERT OR REPLACE INTO account_lifecycle(user_id,state) VALUES(?,'erasing')", (account,))
        recovery.authorize_account_erasure(c, account, 1)
        rows, _ = _rows_for_user(c, account)
        assert len(rows['worker_cgroup_scopes']) == len(rows['worker_cgroup_receipts']) == 1
        c.execute('DELETE FROM worker_cgroup_receipts')
        c.execute('DELETE FROM worker_cgroup_scopes')


def test_foreign_owner_cannot_erase_worker_evidence(owned, account):
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):recovery.authorize_account_erasure(c, account, account)


def test_actual_admin_api_requires_auth_csrf_confirmation_and_hides_claim_token(owned, monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    client = TestClient(main.app)
    url = '/api/admin/service-regime/worker-processes'
    assert client.get(url, follow_redirects=False).status_code in (401, 403, 303)
    identity=[auth.get_user(1)]
    monkeypatch.setattr(auth, 'session_user', lambda request: identity[0])
    monkeypatch.setattr(main, 'session_user', lambda request: identity[0])
    assert client.get(url).status_code == 200
    assert owned[2]['claim_token'] not in client.get(url).text
    path = url+'/'+owned[1]+'/quiesce'
    assert client.post(path, json={'request_id':'recovery-request-0001','confirm_stop':True}).status_code == 403
    headers={'X-MTA-Request':'1'}
    assert client.post(path, json={'request_id':'recovery-request-0001','confirm_stop':False}, headers=headers).status_code == 422
    dead(monkeypatch)
    result=client.post(path, json={'request_id':'recovery-request-0001','confirm_stop':True}, headers=headers)
    assert result.status_code == 200 and result.json()['financial_settlement'] is False
    identity[0]=auth.get_user(2)
    assert client.get(url).status_code == 403


@pytest.mark.parametrize('explicit',[True,False])
def test_registered_runner_commits_scope_before_spawn_and_cleanup_before_measurement(owned, fake_cgroup, monkeypatch, explicit):
    from app import ai_cgroup_metering as runner
    fake_cgroup['populated']='0'
    monkeypatch.setattr(recovery, '_kernel_filesystem', lambda _: None)
    receipt={'job_id':owned[0],**owned[2]}
    if not explicit:
        from app import deferred_execution_owner as owners
        monkeypatch.setattr(owners,'cgroup_receipt',lambda:receipt)
    result=runner.run_cgroup_process(['/bin/true'],cwd='/',parent=str(fake_cgroup['root']),
                                    **({'owner_receipt':receipt} if explicit else {}))
    assert result.source=='cgroup'
    with auth.db() as c:
        assert c.execute('SELECT worker_scope_count FROM ai_compute_jobs').fetchone()[0]==2
        assert c.execute('SELECT count(*) FROM worker_cgroup_receipts').fetchone()[0]==1


def test_metering_failure_with_unknown_cleanup_keeps_gpu_lease_and_claim(operator, kernel, monkeypatch):
    from app import ai_metering_agent as agent, ai_gpu_slot_accounting as slots
    monkeypatch.setenv('MTA_AI_CGROUP_PARENT',str(kernel.parent))
    monkeypatch.setattr(slots,'slot_enabled_for_kind',lambda _:True)
    acquired=[]
    monkeypatch.setattr(slots,'acquire',lambda *a:acquired.append(a))
    monkeypatch.setattr(slots,'release',lambda *a,**kw:pytest.fail('Unknown worker still owns GPU lease'))
    from app import ai_cgroup_metering
    def unresolved(*args,owner_receipt,**kwargs):
        recovery.register(kernel,owner_receipt['job_id'],owner_receipt)
        raise RuntimeError('Kernel cleanup unavailable')
    monkeypatch.setattr(ai_cgroup_metering,'run_cgroup_process',unresolved)
    with pytest.raises(FenceBlocked,match='quiescence'):
        agent.execute_registered_worker(operator,'whisper',{'kind':'whisper'},source_wav=source_audio())
    assert acquired
    with auth.db() as c:
        assert c.execute('SELECT status FROM ai_compute_jobs').fetchone()[0]=='running'
        assert c.execute('SELECT state FROM regime_worker_claims').fetchone()[0]=='running'
