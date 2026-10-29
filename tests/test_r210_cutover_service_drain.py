"""Real admin cutover plus original durable service drain; no readiness doubles."""
from contextlib import closing
import sqlite3
import threading
import json
import os
import signal
import subprocess
import sys

import pytest

from app import auth, regime_admin_cutover as cutover, service_admission as gate, storage
from app.regime_balance_continuity import snapshot
from app.regime_operation_fence import FenceBlocked
from test_r210_admin_cutover_e2e import ready as ready, begin, BASE, HEADERS  # noqa: F401
from test_r210_subscriptions import account as account  # noqa: F401


@pytest.fixture
def drained(ready, monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_SERVICE_ADMISSION', gate.MODE)
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    storage.ROOT.mkdir(exist_ok=True)
    client, uid, admin = ready
    initial = client.get('/api/admin/service-admission')
    assert initial.status_code == 200 and initial.json()['phase'] == 'open'
    result = change(client, 0, True, 'cutover-drain-1')
    assert result.status_code == 200 and result.json()['drained'], result.text
    return ready


def change(client, generation, draining, identifier):
    return client.post('/api/admin/service-admission/change', headers=HEADERS,
        json={'expected_generation': generation, 'draining': draining,
              'identifier': identifier, 'confirm': True})


def test_actual_two_way_cutover_keeps_original_drain_until_explicit_resume(drained):
    client, uid, admin = drained
    with gate.control(), auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        original = snapshot(con)
    preview = client.get(BASE + '/preview?target=NON_COMMERCIAL').json()
    binding = preview['readiness']['service_admission']
    assert binding['generation'] == 1 and binding['drain_id'] == 'cutover-drain-1'
    assert len(binding['build']) == len(binding['instance']) == 64
    for target, identifier, revision in [('NON_COMMERCIAL', 'drained-cutover-nc', 1),
                                          ('COMMERCIAL', 'drained-cutover-co', 2)]:
        body = begin(client, target=target, identifier=identifier)
        result = client.post(BASE, headers=HEADERS, json=body)
        assert result.status_code == 200, result.text
        assert result.json()['phase'] == 'finalized' and result.json()['revision'] == revision
        assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
        state = client.get('/api/admin/service-admission').json()
        assert state['drained'] and state['generation'] == 1
        assert client.get('/api/service-regime').status_code == 503
        with gate.control(), auth.db() as con:
            con.execute('BEGIN IMMEDIATE')
            assert snapshot(con) == original
    resumed = change(client, 1, False, 'cutover-drain-1')
    assert resumed.status_code == 200 and resumed.json()['phase'] == 'open'
    assert client.get('/api/service-regime').json() == {'regime': 'COMMERCIAL'}
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
    assert client.post(BASE, headers=HEADERS, json={**body, 'preview_sha256': '0'*64}).status_code == 409


def test_open_service_cannot_preview_or_execute_old_confirmation(drained):
    client, _, _ = drained
    body = begin(client)
    assert change(client, 1, False, 'cutover-drain-1').status_code == 200
    assert client.get(BASE + '/preview?target=NON_COMMERCIAL').status_code == 409
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 409
    assert client.get(BASE).json()['total'] == 0


def test_resume_and_new_drain_invalidate_unchanged_financial_preview(drained):
    client, _, _ = drained
    old = begin(client)
    assert change(client, 1, False, 'cutover-drain-1').status_code == 200
    assert change(client, 2, True, 'cutover-drain-2').json()['drained']
    fresh = begin(client)
    assert old['preview_sha256'] != fresh['preview_sha256']
    assert client.post(BASE, headers=HEADERS, json=old).status_code == 409
    assert client.post(BASE, headers=HEADERS, json=fresh).status_code == 200


def test_original_predrain_ticket_blocks_cutover_even_without_financial_work(drained):
    client, _, _ = drained
    assert change(client, 1, False, 'cutover-drain-1').status_code == 200
    ticket = gate.reserve('original-uncertain-timer')
    assert not change(client, 2, True, 'cutover-drain-2').json()['drained']
    assert client.get(BASE + '/preview?target=NON_COMMERCIAL').status_code == 409
    gate.release(ticket)
    assert client.get(BASE + '/preview?target=NON_COMMERCIAL').status_code == 200


def test_committed_crash_cannot_resume_and_only_original_forward_recovery_clears_it(drained, monkeypatch):
    client, _, _ = drained
    body = begin(client)
    real = cutover.reconcile_mirror
    def crash(*args):
        raise OSError('Simulated durable mirror replacement failure')
    monkeypatch.setattr(cutover, 'reconcile_mirror', crash)
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 503
    assert client.get(BASE + '/' + body['request_id']).json()['phase'] == 'committed'
    assert change(client, 1, False, 'cutover-drain-1').status_code == 409
    assert client.get('/api/admin/service-admission').json()['phase'] == 'draining'
    monkeypatch.setattr(cutover, 'reconcile_mirror', real)
    assert client.post(BASE + '/foreign-original/recover', headers=HEADERS,
                       json={'expected_revision': 1, 'confirm': True}).status_code == 409
    response = client.post(BASE + '/' + body['request_id'] + '/recover', headers=HEADERS,
                           json={'expected_revision': 1, 'confirm': True})
    assert response.status_code == 200, response.text
    assert response.json()['phase'] == 'finalized'
    assert change(client, 1, False, 'cutover-drain-1').status_code == 200


@pytest.mark.parametrize('damage', ['missing-journal', 'missing-instance', 'build', 'event', 'active', 'schema'])
def test_damaged_or_unfinished_original_admission_never_authorizes_cutover(drained, damage):
    client, _, _ = drained
    body = begin(client)
    if damage == 'missing-journal':
        gate.path().unlink()
    elif damage == 'missing-instance':
        gate.path().with_suffix('.instance').unlink()
    else:
        with closing(sqlite3.connect(gate.path())) as con:
            if damage == 'build': con.execute("UPDATE state SET build='foreign'")
            elif damage == 'event': con.execute('UPDATE state SET generation=generation+1')
            elif damage == 'active':
                con.execute("INSERT INTO admissions VALUES('lost','nonce','lost-worker',NULL,0,123,'open',0,NULL)")
            else: con.execute('DROP TRIGGER no_event_delete')
            con.commit()
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 409
    with gate.control(), auth.db() as con:
        assert not con.execute("SELECT 1 FROM sqlite_master WHERE name='regime_admin_cutovers'").fetchone()


def test_removed_configuration_cannot_bypass_persisted_drain(drained, monkeypatch):
    client, _, _ = drained
    monkeypatch.setenv('MTA_SERVICE_ADMISSION', 'off')
    assert gate.active()
    assert client.post(BASE, headers=HEADERS, json=begin(client)).status_code == 200
    with pytest.raises(FenceBlocked): gate.reserve('new-work')


def test_financial_history_is_still_blocked_after_successful_service_drain(drained):
    client, _, _ = drained
    with gate.control(), auth.db() as con:
        con.execute("UPDATE paypal_config SET enabled=1 WHERE id=1")
    assert client.get('/api/admin/service-admission').json()['drained']
    result = client.get(BASE + '/preview?target=NON_COMMERCIAL')
    assert result.status_code == 409 and 'financial reconciliation' in result.json()['detail']


def test_held_original_reservation_requires_abort_before_service_resume(drained):
    from test_r210_transition_progress import reserve_actual
    client, _, _ = drained
    with gate.control(): identifier = reserve_actual(drained)
    assert change(client, 1, False, 'cutover-drain-1').status_code == 409
    result = client.post(BASE + '/reservations/' + identifier + '/abort', headers=HEADERS,
                         json={'expected_revision': 0, 'confirm': True})
    assert result.status_code == 200
    assert change(client, 1, False, 'cutover-drain-1').status_code == 200


def test_forward_recovery_cannot_waive_an_unrelated_unfinished_publication(drained, monkeypatch):
    client, _, _ = drained
    real = cutover.reconcile_mirror
    def crash(*args): raise OSError('Simulated mirror failure')
    monkeypatch.setattr(cutover, 'reconcile_mirror', crash)
    body = begin(client)
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 503
    monkeypatch.setattr(cutover, 'reconcile_mirror', real)
    folder = storage.ROOT / 'original-project'; folder.mkdir()
    pending = folder / 'publication.pending.json'; pending.write_text('{}')
    url = BASE + '/' + body['request_id'] + '/recover'
    confirmation = {'expected_revision': 1, 'confirm': True}
    assert client.post(url, headers=HEADERS, json=confirmation).status_code == 409
    assert client.get(BASE + '/' + body['request_id']).json()['phase'] == 'committed'
    pending.unlink()
    assert client.post(url, headers=HEADERS, json=confirmation).status_code == 200


def test_actual_process_sigkill_releases_os_locks_but_preserves_original_drain_and_cutover(drained):
    client, _, _ = drained
    body = begin(client, identifier='drain-process-crash')
    script = '''import json,os,signal,sys
from app import main,regime_admin_cutover as cutover
from fastapi.testclient import TestClient
data=json.load(sys.stdin)
def crash(*args):os.kill(os.getpid(),signal.SIGKILL)
cutover.reconcile_mirror=crash
client=TestClient(main.app);client.cookies.update(data['cookies'])
client.post('/api/admin/service-regime/cutovers',headers={'X-MTA-Request':'1'},json=data['body'])
raise RuntimeError('Crash injection not reached')
'''
    result = subprocess.run([sys.executable, '-c', script], input=json.dumps({'body': body, 'cookies': dict(client.cookies)}),
                            capture_output=True, text=True, timeout=30, env=dict(os.environ))
    assert result.returncode == -signal.SIGKILL, result.stderr
    state = client.get('/api/admin/service-admission').json()
    assert state['phase'] == 'draining' and state['drain_id'] == 'cutover-drain-1'
    assert state['pending']['by_kind']['cutover_recovery'] == 1
    assert change(client, 1, False, 'cutover-drain-1').status_code == 409
    assert client.post(BASE + '/' + body['request_id'] + '/recover', headers=HEADERS,
                       json={'expected_revision': 1, 'confirm': True}).status_code == 200
    assert change(client, 1, False, 'cutover-drain-1').status_code == 200


def test_resume_waits_until_financial_commit_mirror_and_finalization_release_original_guard(drained, monkeypatch):
    client, _, admin = drained
    body = begin(client)
    entered = threading.Event(); finish = threading.Event(); result = []; resumed = []
    real = cutover.reconcile_mirror
    def paused(*args):
        entered.set()
        assert finish.wait(5)
        return real(*args)
    monkeypatch.setattr(cutover, 'reconcile_mirror', paused)
    runner = threading.Thread(target=lambda: result.append(client.post(BASE, headers=HEADERS, json=body)))
    runner.start()
    try:
        assert entered.wait(4)
        def resume():
            try:
                resumed.append(gate.change(actor=admin, expected_generation=1, draining=False,
                                           identifier='cutover-drain-1', confirm=True))
            except FenceBlocked:
                resumed.append('blocked')
        other = threading.Thread(target=resume); other.start()
        # Attempt is synchronized at a real SQLite write reservation. It may
        # refuse the nonblocking lease, but can never reopen before finalize.
        with closing(sqlite3.connect(gate.path(), timeout=0)) as con:
            with pytest.raises(sqlite3.OperationalError): con.execute('BEGIN IMMEDIATE')
        assert not resumed or resumed == ['blocked']
        finish.set(); runner.join(6); other.join(6)
        assert not runner.is_alive() and not other.is_alive()
        assert result[0].status_code == 200
    finally:
        finish.set(); runner.join(6)
