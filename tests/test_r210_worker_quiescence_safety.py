"""Uncertain identity is not death; nested cgroup cleanup is fail-closed."""
import io
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from app import ai_arranger_runtime as queue, ai_cgroup_metering as groups
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    return tmp_path


def insert_job(jid, state='running', identity='boot:123'):
    with queue._db() as con:
        con.execute("""INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,
          phase,message,runner_pid,runner_identity) VALUES(?,'p','test',?,1,1,?,'test',?,?)""",
                    (jid, state, state, os.getpid(), identity))


@pytest.mark.parametrize('failure', [PermissionError, OSError, ValueError])
def test_unreadable_proc_is_unknown_not_dead(monkeypatch, failure):
    original = Path.read_text
    def read(path, *args, **kwargs):
        if str(path).endswith('/stat'):
            raise failure('unavailable')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    assert queue._process_identity(os.getpid()) == ''


@pytest.mark.parametrize('text', ['', 'malformed', '1 (x) R ' + '0 ' * 19])
def test_malformed_proc_is_unknown(monkeypatch, text):
    original = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **kw:
                        text if str(path).endswith('/stat') else original(path, *a, **kw))
    assert queue._process_identity(os.getpid()) == ''


def test_missing_boot_identity_does_not_prove_death(monkeypatch):
    monkeypatch.setattr(Path, 'read_text', lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    assert queue._process_identity(os.getpid()) == ''


@pytest.mark.parametrize('missing', [FileNotFoundError, ProcessLookupError])
def test_absent_proc_is_confirmed_dead(monkeypatch, missing):
    original = Path.read_text
    def read(path, *args, **kwargs):
        if str(path).endswith('/stat'):
            raise missing()
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    monkeypatch.setattr(queue.os, 'kill', lambda *a: (_ for _ in ()).throw(ProcessLookupError()))
    assert queue._process_identity(os.getpid()) is None


@pytest.mark.parametrize('denied', [False, True])
def test_hidden_proc_is_not_dead(monkeypatch, denied):
    original = Path.read_text
    def read(path, *args, **kwargs):
        if str(path).endswith('/stat'):
            raise FileNotFoundError()
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    def probe(*_):
        if denied:
            raise PermissionError()
    monkeypatch.setattr(queue.os, 'kill', probe)
    assert queue._process_identity(os.getpid()) == ''


@pytest.mark.parametrize('pid', [0, -1, True, None, '123'])
def test_invalid_pid_never_probes_a_process_group(monkeypatch, pid):
    monkeypatch.setattr(queue.os, 'kill', lambda *a: pytest.fail('invalid identity probe'))
    assert queue._process_identity(pid) == ''


@pytest.mark.parametrize('state', ['Z', 'X', 'x'])
def test_dead_kernel_states(monkeypatch, state):
    original = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda path, *a, **kw:
                        '12 (worker (nested)) ' + state if str(path).endswith('/stat') else original(path, *a, **kw))
    assert queue._process_identity(os.getpid()) is None


@pytest.mark.parametrize('state', ['queued', 'running'])
def test_unknown_identity_preserves_original_owner_and_no_receipt(isolated, monkeypatch, state):
    insert_job('uncertain', state)
    monkeypatch.setattr(queue, '_process_identity', lambda _: '')
    assert queue.get('uncertain')['state'] == state
    with queue._db() as con:
        assert con.execute('SELECT runner_identity FROM jobs').fetchone()[0] == 'boot:123'
        assert con.execute('SELECT count(*) FROM terminal_receipts').fetchone()[0] == 0


@pytest.mark.parametrize('identity', [None, ''])
def test_new_claim_requires_verifiable_scheduler_identity(isolated, monkeypatch, identity):
    insert_job('unverifiable', 'queued')
    monkeypatch.setattr(queue, '_process_identity', lambda _: identity)
    assert not queue._claim('unverifiable')
    with queue._db() as con:
        assert con.execute('SELECT state FROM jobs').fetchone()[0] == 'queued'
        assert con.execute('SELECT count(*) FROM terminal_receipts').fetchone()[0] == 0


def test_identity_loss_before_completion_never_creates_terminal_receipt(isolated, monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    def run(*_):
        entered.set()
        assert release.wait(5)
    _, job = queue.start('p', 'test', run, job_id='lost-identity')
    assert entered.wait(5)
    monkeypatch.setattr(queue, '_process_identity', lambda _: '')
    release.set()
    deadline = time.monotonic() + 5
    while 'lost-identity' in queue._LOCAL and time.monotonic() < deadline:
        threading.Event().wait(.01)
    assert queue.get(job['job_id'])['state'] == 'running'
    with queue._db() as con:
        assert con.execute('SELECT count(*) FROM terminal_receipts').fetchone()[0] == 0


@pytest.mark.parametrize('identity', [None, ''])
def test_deferred_owner_cannot_claim_with_unknown_identity(isolated, operator, monkeypatch, identity):
    from app import ai_billing, auth
    from app.deferred_execution_owner import execution_scope
    from app.regime_operation_fence import FenceBlocked
    queue.start('p', 'arranger', None, job_id='unknown-owner', defer_spawn=True,
                payload={'schema_version': 1, 'actor_user_id': operator, 'adapter': 'arranger'})
    ledger = ai_billing.provision_inference_job('unknown-owner', operator, 'arranger')
    assert queue._claim('unknown-owner')
    monkeypatch.setattr(queue, '_process_identity', lambda _: identity)
    with pytest.raises(FenceBlocked, match='current durable scheduler owner'):
        with execution_scope('unknown-owner', threading.Event()):
            pytest.fail('unknown process became the execution owner')
    with auth.db() as c:
        assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (ledger,)).fetchone()[0] == 'running'


def test_real_supervisor_death_does_not_prove_external_worker_exit(isolated, operator):
    """Actual SIGKILL, actual surviving child; no inference replay or ledger closure."""
    child_file = isolated / 'child.pid'
    ready = isolated / 'ready'
    from app import ai_billing, auth
    ledger = ai_billing.create_job(operator, 'whisper', started_at=1)
    script = '''import os,sys,time,subprocess
from pathlib import Path
from app import ai_arranger_runtime as q
from app import ai_billing
from app.regime_worker_claims import claim
q._ROOT=Path(sys.argv[1])
with ai_billing.db() as c:
 c.execute('BEGIN IMMEDIATE')
 claim(c,sys.argv[4],worker_id='supervisor-crash-fixture',token='original-crash-token')
child_code="import os,sys,time;from pathlib import Path;Path(sys.argv[1]).write_text(str(os.getpid()));time.sleep(30)"
child=subprocess.Popen([sys.executable,'-c',child_code,sys.argv[2]],start_new_session=True)
# The process-view adapter resolves namespace-local OS PIDs safely.
pid=os.getpid()
with q._db() as c:
 c.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,runner_pid,runner_identity) VALUES('orphan','p','arranger','running',1,1,'running','test',?,?)",(pid,q._process_identity(pid)))
deadline=time.monotonic()+5
while not Path(sys.argv[2]).exists() and time.monotonic()<deadline:time.sleep(.01)
assert Path(sys.argv[2]).exists()
Path(sys.argv[3]).touch()
time.sleep(30)
'''
    proc = subprocess.Popen([sys.executable, '-c', script, str(queue._ROOT), str(child_file), str(ready), ledger])
    child_pid = None
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
            threading.Event().wait(.01)
        assert ready.exists()
        child_pid = int(child_file.read_text())
        child_identity = queue._process_identity(child_pid)
        assert child_identity
        proc.kill()
        proc.wait(timeout=5)
        assert queue.get('orphan')['state'] == 'interrupted'
        assert queue._process_identity(child_pid) == child_identity
        assert queue.recover_queued() == 0
        assert not queue._claim('orphan')
        recovered = ai_billing.recover_stale_jobs(older_than_seconds=3600, dry_run=False)
        assert recovered['recovered_job_ids'] == []
        assert recovered['blocked_jobs'] == [{'job_id': ledger, 'reason': 'worker_claim_requires_audited_resolution'}]
        with auth.db() as c:
            assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (ledger,)).fetchone()[0] == 'running'
            assert c.execute('SELECT state FROM regime_worker_claims').fetchone()[0] == 'running'
            assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?', ('job:ledger:' + ledger,)).fetchone()[0] == 'open'
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        if child_pid is None and child_file.exists():
            child_pid = int(child_file.read_text())
        if child_pid is not None:
            try:
                os.kill(child_pid, 9)
            except ProcessLookupError:
                pass


@pytest.fixture
def fake_cgroup(tmp_path, monkeypatch):
    """Synthetic kernel files, explicitly not a delegated-kernel acceptance test."""
    root = tmp_path / 'delegate'
    root.mkdir()
    (root / 'cgroup.controllers').write_text('cpu io')
    (root / 'cgroup.subtree_control').write_text('cpu io')
    original_mkdir = Path.mkdir
    original_relative = Path.is_relative_to
    original_write = Path.write_text
    state = {'root': root, 'kills': 0, 'populated': '1', 'kill_works': True,
             'kill_available': True, 'spawned': 0, 'returncode': 0}
    def mkdir(path, *a, **kw):
        result = original_mkdir(path, *a, **kw)
        if path.parent == root:
            state['group'] = path
            for name, value in {'cpu.stat': 'usage_usec 100', 'io.stat': '',
                                'cgroup.events': 'populated 0\nfrozen 0\n', 'cgroup.procs': ''}.items():
                original_write(path / name, value)
            if state['kill_available']:
                original_write(path / 'cgroup.kill', '')
        return result
    def write(path, value, *a, **kw):
        if path.name == 'cgroup.kill':
            state['kills'] += 1
            if state['kill_works']:
                original_write(path.parent / 'cgroup.events', 'populated 0\nfrozen 0\n')
        return original_write(path, value, *a, **kw)
    def spawn(*a, **kw):
        state['spawned'] += 1
        original_write(state['group'] / 'cgroup.events', 'populated ' + state['populated'] + '\nfrozen 0\n')
        class Child:
            pid = 99999999
            returncode = state['returncode']
            stderr = io.BytesIO(b'')
            def poll(self):
                if state.pop('poll_running_once', False):
                    return None
                return self.returncode
            def wait(self, **kwargs): return self.returncode
        return Child()
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    monkeypatch.setattr(Path, 'is_relative_to', lambda path, other:
                        True if path == root else original_relative(path, other))
    monkeypatch.setattr(Path, 'write_text', write)
    monkeypatch.setattr(groups.subprocess, 'Popen', spawn)
    return state


def test_nested_workers_are_killed_and_not_billed(fake_cgroup):
    with pytest.raises(RuntimeError, match='left running descendants'):
        groups.run_cgroup_process(['/bin/true'], cwd='/', parent=str(fake_cgroup['root']))
    assert fake_cgroup['kills'] == 1 and fake_cgroup['spawned'] == 1


def test_missing_recursive_kill_refuses_spawn(fake_cgroup):
    fake_cgroup['kill_available'] = False
    with pytest.raises(RuntimeError, match='requires cgroup.kill'):
        groups.run_cgroup_process(['/bin/true'], cwd='/', parent=str(fake_cgroup['root']))
    assert fake_cgroup['spawned'] == 0 and fake_cgroup['kills'] == 0


def test_empty_group_returns_only_its_measured_usage(fake_cgroup):
    fake_cgroup['populated'] = '0'
    result = groups.run_cgroup_process(['/bin/true'], cwd='/', parent=str(fake_cgroup['root']))
    assert result.source == 'cgroup' and result.usage['cpu_seconds'] == .0001
    assert fake_cgroup['kills'] == 0


@pytest.mark.parametrize('when', ['during_run', 'after_exit', 'timeout'])
def test_cancellation_or_timeout_stops_nested_workers_without_measurement(fake_cgroup, when):
    fake_cgroup['poll_running_once'] = when != 'after_exit'
    calls = []
    def cancelled():
        calls.append(True)
        return len(calls) >= 3
    kwargs = {'cancel_check': cancelled} if when != 'timeout' else {'timeout_seconds': 1e-9}
    with pytest.raises((RuntimeError, TimeoutError), match='cancelled|timed out'):
        groups.run_cgroup_process(['/bin/true'], cwd='/', parent=str(fake_cgroup['root']), **kwargs)
    assert fake_cgroup['kills'] == 1


def test_unknown_quiescence_is_never_a_measurement(fake_cgroup, monkeypatch):
    fake_cgroup['kill_works'] = False
    original = groups._stop_cgroup
    monkeypatch.setattr(groups, '_stop_cgroup', lambda path: original(path, timeout_seconds=0))
    with pytest.raises(RuntimeError, match='quiescence remains unverified'):
        groups.run_cgroup_process(['/bin/true'], cwd='/', parent=str(fake_cgroup['root']))
    assert fake_cgroup['group'].exists()


def test_empty_cleanup_failure_invalidates_pending_measurement(fake_cgroup, monkeypatch):
    fake_cgroup['populated'] = '0'
    monkeypatch.setattr(groups, '_stop_cgroup', lambda _: (_ for _ in ()).throw(PermissionError()))
    with pytest.raises(RuntimeError, match='cleanup failed; metering invalid'):
        groups.run_cgroup_process(['/bin/true'], cwd='/', parent=str(fake_cgroup['root']))


def test_kill_waits_for_recursive_empty(tmp_path, monkeypatch):
    (tmp_path / 'cgroup.events').write_text('populated 1\n')
    (tmp_path / 'cgroup.kill').touch()
    calls = []
    def wait(_):
        calls.append(True)
        (tmp_path / 'cgroup.events').write_text('populated 0\n')
    monkeypatch.setattr(groups.time, 'sleep', wait)
    groups._stop_cgroup(tmp_path)
    assert calls == [True]
    assert (tmp_path / 'cgroup.kill').read_text() == '1'
