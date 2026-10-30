"""Actual enabled API, real SQLite money/periods and crash recovery; no readiness doubles."""
import sqlite3
import sys
import time
import json
import os
import signal
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, resource_accounts as accounts, credit_purchases, paypal_payments, payment_reconciliation
from app import regime_admin_cutover as cutover
from app.regime_balance_continuity import snapshot
from app.regime_operation_fence import FenceBlocked
from app.regime_service_lease import lease
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r210_legal_documents import cookie

BASE = '/api/admin/service-regime/cutovers'
HEADERS = {'X-MTA-Request': '1'}


@pytest.fixture
def ready(account, monkeypatch, tmp_path):
    from app import main, ai_arranger_runtime as queue
    monkeypatch.setenv('MTA_REGIME_CUTOVER', 'local-authority-v1')
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    monkeypatch.setenv('MTA_AI_JOB_STATE_DIR', str(tmp_path / 'queue'))
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda request: False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER', raising=False)
    plan(account)
    admin = auth.find_user('admin')['id']
    accounts.grant(account, 1_000_000, 'Explicit operator issued test credits', admin, 'cutover-credit-1')
    with auth.db() as con:
        from app import account_lifecycle
        account_lifecycle.init(con)
        credit_purchases.init(con)
        paypal_payments.init(con)
        con.execute('BEGIN IMMEDIATE')
        payment_reconciliation.initialize(con)
    client = TestClient(main.app)
    client.cookies.update(cookie(admin))
    return client, account, admin


def begin(client, *, target='NON_COMMERCIAL', identifier='actual-cutover-1'):
    review = client.get(BASE + '/preview', params={'target': target})
    assert review.status_code == 200, review.text
    data = review.json()
    assert data['transition_enabled'] is True
    body = {'request_id': identifier, 'target': target, 'expected_revision': data['source_revision'],
            'preview_sha256': data['preview_sha256'], 'confirm': True}
    return body


def test_actual_admin_roundtrip_preserves_wallet_periods_and_real_nc_history(ready):
    client, uid, _ = ready
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        original = snapshot(con)
        balance = accounts._balance(con, uid)
    body = begin(client)
    result = client.post(BASE, headers=HEADERS, json=body)
    assert result.status_code == 200, result.text
    assert result.json()['phase'] == 'finalized' and result.json()['barrier_held'] is False
    assert client.get('/api/service-regime').json() == {'regime': 'NON_COMMERCIAL'}
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        assert snapshot(con) == original and accounts._balance(con, uid) == balance == 1_000_000
    # Real authenticated NC closure in the newly active regime, then carry that
    # exact immutable statement through the actual return API. No provider/model.
    statement = client.post('/api/admin/service-regime/noncommercial-statements', headers=HEADERS,
                           json={'start': 1, 'end': 2, 'documented_cost_cents': 0,
                                 'operator_cost_exclusion_confirmed': True})
    assert statement.status_code == 200, statement.text
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        with_history = snapshot(con)
    back = begin(client, target='COMMERCIAL', identifier='actual-cutover-back')
    result = client.post(BASE, headers=HEADERS, json=back)
    assert result.status_code == 200, result.text
    assert result.json()['revision'] == 2 and result.json()['phase'] == 'finalized'
    assert client.get('/api/service-regime').json() == {'regime': 'COMMERCIAL'}
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        assert snapshot(con) == with_history and accounts._balance(con, uid) == balance
    assert len(client.get('/api/admin/service-regime/noncommercial-statements').json()['statements']) == 1
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
    assert client.post(BASE, headers=HEADERS, json=back).status_code == 200
    history = client.get(BASE).json()
    assert history['total'] == 2 and all(row['phase'] == 'finalized' for row in history['items'])
    assert all([event['phase'] for event in row['events']] == ['committed', 'finalized'] for row in history['items'])
    assert client.get(BASE + '/actual-cutover-back').json()['phase'] == 'finalized'
    assert client.get(BASE + '/not-committed').status_code == 404
    reservations = client.get('/api/admin/service-regime/transition-reservations').json()
    assert reservations['integrity_verified'] and not reservations['reservations']


@pytest.mark.parametrize('providers_prepared',[False,True])
def test_real_registered_builtin_harmony_and_measured_nc_statement_survive_actual_return_cutover(ready, monkeypatch, providers_prepared):
    client, uid, _ = ready
    if providers_prepared:
        paypal_payments.settings({'enabled':True,'environment':'sandbox','client_id':'prepared-client',
            'client_secret':'prepared-secret','webhook_id':'prepared-webhook'})
        credit_purchases.settings({'secret_key':'sk_test_prepared','webhook_secret':'whsec_prepared'})
        with auth.db() as con:con.execute('UPDATE resource_plans SET price_micro=5000000')
    body = begin(client)
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
    from app import ai_metering_agent, ai_studio_adapter
    from app.studio_score import Score
    from app.music_interchange import MusicResult, MusicPart
    from app.models import MidiNote
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_VOCAL_HARMONY_EXECUTABLE', str(Path(ai_studio_adapter.__file__).resolve()))
    monkeypatch.setenv('MTA_AI_WORKER_VOCAL_HARMONY_PYTHON', sys.executable)
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    score = Score(music=MusicResult(parts=[MusicPart(id='melody', name='Melody', notes=[
        MidiNote(id='n', pitch=60, start_ms=0, duration_ms=500)])])).model_dump_json().encode()
    start = int(time.time()) - 1
    payload, meta = ai_metering_agent.execute_registered_worker(uid, 'vocal-harmony', {}, source_json=score, timeout_seconds=30)
    assert payload and meta['usage']['cpu_seconds'] > 0 and meta['metering_source'] == 'worker'
    statement = client.post('/api/admin/service-regime/noncommercial-statements', headers=HEADERS,
        json={'start': start, 'end': int(time.time()) + 1, 'documented_cost_cents': 10,
              'operator_cost_exclusion_confirmed': True})
    assert statement.status_code == 200, statement.text
    assert statement.json()['jobs_count'] == 1
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        original = snapshot(con)
    back = begin(client, target='COMMERCIAL', identifier='with-real-job-back')
    response = client.post(BASE, headers=HEADERS, json=back)
    assert response.status_code == 200, response.text
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        assert snapshot(con) == original and accounts._balance(con, uid) == 1_000_000
    assert client.get('/api/admin/service-regime/noncommercial-statements').json()['statements'][0]['sha256'] == statement.json()['sha256']


@pytest.mark.parametrize('after_replace', [False, True])
def test_interruption_keeps_barrier_auth_and_original_finances_then_forward_recovers(ready, monkeypatch, after_replace):
    client, uid, _ = ready
    body = begin(client)
    real = cutover.reconcile_mirror
    def interrupted(*args):
        if after_replace:
            real(*args)
        raise OSError('Injected filesystem interruption')
    monkeypatch.setattr(cutover, 'reconcile_mirror', interrupted)
    result = client.post(BASE, headers=HEADERS, json=body)
    assert result.status_code == 503, result.text
    assert client.get('/api/service-regime').status_code == 503
    history = client.get(BASE).json()
    assert history['items'][0]['phase'] == 'committed' and history['items'][0]['barrier_held']
    # A surviving pre-crash session is not required: the real login path can
    # authenticate against the frozen, existing schema and issue a fresh cookie.
    client.cookies.clear()
    login = client.post('/login', data={'identifier': 'admin', 'password': 'a-secure-test-password', 'next': '/settings'}, follow_redirects=False)
    assert login.status_code == 303, login.text
    assert client.get(BASE).status_code == 200
    with auth.db() as con:
        assert accounts._balance(con, uid) == 1_000_000
        with pytest.raises(sqlite3.DatabaseError):
            con.execute('UPDATE resource_credits SET delta_micro=0')
    # Recovery remains authenticated while ordinary ingress and monetary writes
    # are stopped. A stale recovery epoch cannot clear the held barrier.
    url = BASE + '/' + body['request_id'] + '/recover'
    assert client.post(url, headers=HEADERS, json={'expected_revision': 2, 'confirm': True}).status_code == 409
    monkeypatch.setattr(cutover, 'reconcile_mirror', real)
    result = client.post(url, headers=HEADERS, json={'expected_revision': 1, 'confirm': True})
    assert result.status_code == 200, result.text
    assert result.json()['barrier_held'] is False
    assert client.post(url, headers=HEADERS, json={'expected_revision': 1, 'confirm': True}).status_code == 200
    with auth.db() as con:
        assert accounts._balance(con, uid) == 1_000_000


@pytest.mark.parametrize('change', ['history', 'credit', 'missing-schema', 'unknown-journal', 'unprefixed-legacy-schema', 'running-job'])
def test_unverifiable_or_financially_unsupported_states_refuse_actual_api(ready, change):
    client, _, _ = ready
    body = begin(client)
    with auth.db() as con:
        if change == 'history':
            con.execute("INSERT INTO paypal_events VALUES('unmatched-history',1)")
        elif change == 'credit':
            con.execute("UPDATE resource_credits SET id='imported-provider-credit' WHERE delta_micro>0")
        elif change == 'missing-schema':
            con.execute('DROP TABLE payment_reconciliation_events')
        elif change == 'unknown-journal':
            con.execute('CREATE TABLE payment_unknown_liability(id TEXT)')
            con.execute("INSERT INTO payment_unknown_liability VALUES('unresolved')")
        elif change == 'unprefixed-legacy-schema':
            con.execute('CREATE TABLE legacy_cash_history(amount INTEGER)')
            con.execute('INSERT INTO legacy_cash_history VALUES(123)')
        else:
            from app import ai_billing
            ai_billing.create_job(ready[1], 'whisper')
    assert client.get(BASE + '/preview?target=NON_COMMERCIAL').status_code == 409
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 409
    assert client.get('/api/service-regime').json()['regime'] == 'COMMERCIAL'
    assert client.get(BASE).json()['total'] == 0


def test_preview_staleness_auth_csrf_default_off_and_confirmation_are_not_bypassable(ready, monkeypatch):
    client, uid, admin = ready
    body = begin(client)
    assert client.post(BASE, json=body).status_code == 403
    for update in ({'confirm': False}, {'expected_revision': False}, {'ready': True}):
        assert client.post(BASE, headers=HEADERS, json=body | update).status_code == 422
    client.cookies.clear()
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 401
    client.cookies.update(cookie(uid))
    assert client.get(BASE + '/preview?target=NON_COMMERCIAL').status_code == 403
    client.cookies.update(cookie(admin))
    accounts.grant(uid, 1, 'New explicit grant after preview', admin, 'cutover-credit-2')
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 409
    monkeypatch.delenv('MTA_REGIME_CUTOVER')
    assert client.get(BASE + '/preview?target=NON_COMMERCIAL').status_code == 409
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 409
    assert client.get(BASE).json()['total'] == 0


def test_live_accounting_connection_blocks_exclusive_cutover(ready):
    client, _, admin = ready
    body = begin(client)
    with auth.db():
        with pytest.raises(FenceBlocked, match='lease'):
            cutover.execute(identifier=body['request_id'], target=body['target'], expected_revision=0,
                            preview_sha256=body['preview_sha256'], confirm=True, actor=admin)
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 200


def test_independent_process_lease_blocks_api_and_sigkill_releases_only_os_lock(ready):
    client, _, _ = ready
    body = begin(client)
    code = 'from app import auth\nimport sys\nwith auth.db() as con:\n print("ready",flush=True)\n sys.stdin.read()\n'
    process = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == 'ready'
        assert client.post(BASE, headers=HEADERS, json=body).status_code == 409
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode == -signal.SIGKILL
        assert client.post(BASE, headers=HEADERS, json=body).status_code == 200
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)


def test_actual_api_process_sigkill_after_sqlite_commit_preserves_durable_barrier(ready, monkeypatch):
    client, uid, _ = ready
    body = begin(client, identifier='real-process-crash')
    script = '''import json,os,signal,sys
from app import main,regime_admin_cutover as cutover
from fastapi.testclient import TestClient
data=json.load(sys.stdin)
def crash(*args):os.kill(os.getpid(),signal.SIGKILL)
cutover.reconcile_mirror=crash
client=TestClient(main.app)
client.cookies.update(data['cookies'])
client.post('/api/admin/service-regime/cutovers',headers={'X-MTA-Request':'1'},json=data['body'])
raise RuntimeError('Crash injection not reached')
'''
    outcome = subprocess.run([sys.executable, '-c', script], input=json.dumps({'body': body, 'cookies': dict(client.cookies)}),
                             capture_output=True, text=True, timeout=30, env=dict(os.environ))
    assert outcome.returncode == -signal.SIGKILL, outcome.stderr
    assert client.get('/api/service-regime').status_code == 503
    assert client.get(BASE).json()['items'][0]['phase'] == 'committed'
    result = client.post(BASE + '/real-process-crash/recover', headers=HEADERS,
                         json={'expected_revision': 1, 'confirm': True})
    assert result.status_code == 200, result.text
    with auth.db() as con:
        assert accounts._balance(con, uid) == 1_000_000


def test_changed_original_receipt_cannot_rebaseline_or_abort_committed_transition(ready, monkeypatch):
    client, _, _ = ready
    body = begin(client)
    real = cutover.reconcile_mirror
    monkeypatch.setattr(cutover, 'reconcile_mirror', lambda *args: (_ for _ in ()).throw(OSError('Injected crash')))
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 503
    # Simulate out-of-protocol disk/admin modification. Ordinary application
    # connections cannot perform this write while the durable barrier is held.
    with sqlite3.connect(auth.db_path()) as con:
        con.execute('UPDATE resource_credits SET delta_micro=7 WHERE delta_micro>0')
    monkeypatch.setattr(cutover, 'reconcile_mirror', real)
    assert client.post(BASE + '/' + body['request_id'] + '/recover', headers=HEADERS,
                       json={'expected_revision': 1, 'confirm': True}).status_code == 409
    assert client.get(BASE).json()['items'][0]['barrier_held']
    with lease(exclusive=True), auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        from app.regime_transition_journal import abort
        with pytest.raises(FenceBlocked, match='forward recovery'):
            abort(con, transition_id=body['request_id'])


def test_forward_recovery_records_the_actual_second_administrator(ready, monkeypatch):
    client, _, admin = ready
    with auth.db() as con:
        con.execute('''INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at)
            SELECT 'recovery-admin','recovery@example.test',password_hash,'admin',1,1,1,1 FROM users WHERE id=?''', (admin,))
        second = con.execute("SELECT id FROM users WHERE username='recovery-admin'").fetchone()[0]
    body = begin(client, identifier='separate-admin-recovery')
    real = cutover.reconcile_mirror
    monkeypatch.setattr(cutover, 'reconcile_mirror', lambda *args: (_ for _ in ()).throw(OSError('Injected crash')))
    assert client.post(BASE, headers=HEADERS, json=body).status_code == 503
    monkeypatch.setattr(cutover, 'reconcile_mirror', real)
    client.cookies.update(cookie(second))
    result = client.post(BASE + '/separate-admin-recovery/recover', headers=HEADERS,
                         json={'expected_revision': 1, 'confirm': True})
    assert result.status_code == 200, result.text
    assert [(r['phase'], r['actor_id']) for r in result.json()['events']] == [('committed', admin), ('finalized', second)]
    with auth.db() as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute('DELETE FROM regime_admin_cutover_events')
