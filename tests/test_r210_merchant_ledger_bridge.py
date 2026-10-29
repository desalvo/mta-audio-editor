"""Actual merchant snapshot -> canonical history -> original atomic ledger."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, parse_qs

import httpx
import pytest
from app import auth, paypal_payments as paypal, paypal_merchant_history as history
from app import paypal_merchant_reconcile as bridge, resource_accounts as resources
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_history_reconciliation import history_fixture
from test_r210_paypal_merchant_history import START, END


@pytest.fixture
def merchant(account, provider, monkeypatch):
    local, order, refunds, _ = history_fixture(account, provider, monkeypatch)
    admin = auth.find_user('admin')['id']
    pid = order['id']
    for cap in order['purchase_units'][0]['payments']['captures']:
        cap['supplementary_data'] = {'related_ids': {'order_id': pid}}
    original = paypal._api
    rows = []
    calls = []
    hook = {'run': None}

    def api(cfg, method, path, *args):
        assert method == 'GET', 'Merchant reconciliation must never capture/refund money'
        calls.append(path)
        if hook['run']:
            hook['run'](cfg, path)
        if urlsplit(path).path == '/v1/reporting/transactions':
            q = parse_qs(urlsplit(path).query)
            page = int(q['page'][0])
            return {'page': page, 'total_pages': (len(rows)+99)//100,
                    'total_items': len(rows), 'transaction_details': copy.deepcopy(rows[(page-1)*100:page*100])}
        return original(cfg, method, path, *args)

    monkeypatch.setattr(paypal, '_api', api)

    def observe(kind='capture', reference='ODR', **changes):
        item = {'transaction_id': 'CAPTURE111' if kind == 'capture' else 'REFUND111',
                'transaction_event_code': 'T0006' if kind == 'capture' else 'T1107',
                'transaction_status': 'S', 'transaction_amount': {'currency_code': 'EUR', 'value': '3.00' if kind == 'capture' else '-3.00'},
                'paypal_reference_id_type': reference,
                'paypal_reference_id': pid if reference == 'ODR' else 'CAPTURE111',
                'transaction_initiation_date': '2026-09-01T01:00:00Z',
                'transaction_subject': 'PRIVATE DO NOT TRUST', 'transaction_note': local}
        item.update(changes)
        rows[:] = [{'transaction_info': item}]
        receipt = history.acquire(admin, START, END, confirm=True)
        sha = history.digest(history.details(admin, receipt['snapshot_id'])['items'][0])
        return receipt['snapshot_id'], sha

    return {'admin': admin, 'local': local, 'order': order, 'refunds': refunds,
            'observe': observe, 'calls': calls, 'hook': hook}


@pytest.mark.parametrize('kind', ['capture', 'refund'])
@pytest.mark.parametrize('reference', ['ODR', 'TXN'])
def test_discovered_initial_refunded_principal_uses_exact_original_net(merchant, account, kind, reference):
    snap, sha = merchant['observe'](kind, reference)
    review = bridge.review(merchant['admin'], snap)
    assert review['total'] == 1 and not review['complete_account_history']
    assert 'PRIVATE' not in json.dumps(review)
    result = bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert result['ledger_reconciled'] and not result['transition_authorized']
    assert resources.state(account)['credits_micro'] == 1_000_000
    before = len(merchant['calls'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: bridge.reconcile(merchant['admin'], snap, sha, confirm=True), range(2)))
    assert len(merchant['calls']) > before  # Replays still revalidate canonical history.
    assert resources.state(account)['credits_micro'] == 1_000_000
    with auth.db() as c:
        bindings = c.execute("SELECT state,order_id,normalized_json FROM payment_reconciliation_events WHERE normalized_json LIKE '%merchant_discovery_binding%'").fetchall()
        assert len(bindings) == 1 and tuple(bindings[0][:2]) == ('applied', merchant['local'])
        assert json.loads(bindings[0][2])['observation_sha256'] == sha
        assert c.execute('SELECT count(*) FROM paypal_refunds').fetchone()[0] == 2


@pytest.mark.parametrize('change', ['fee', 'payout', 'pending', 'denied', 'currency', 'wrong_sign'])
def test_unsupported_observation_remains_unresolved_before_network(merchant, account, change):
    values = {'fee': {'transaction_event_code': 'T0100'}, 'payout': {'transaction_event_code': 'T1201'},
              'pending': {'transaction_status': 'P'}, 'denied': {'transaction_status': 'D'},
              'currency': {'transaction_amount': {'currency_code': 'USD', 'value': '3.00'}},
              'wrong_sign': {'transaction_amount': {'currency_code': 'EUR', 'value': '-3.00'}}}
    snap, sha = merchant['observe'](**values[change]); before = len(merchant['calls'])
    assert bridge.review(merchant['admin'], snap)['counts']['unsupported'] == 1
    with pytest.raises(FenceBlocked): bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert len(merchant['calls']) == before and resources.state(account)['credits_micro'] == 0


@pytest.mark.parametrize('change', ['amount', 'fraction', 'transaction', 'reference', 'timestamp', 'missing_time'])
def test_reporting_observation_alone_never_funds_or_closes_unknown_money(merchant, account, change):
    changes = {'amount': {'transaction_amount': {'currency_code': 'EUR', 'value': '2.00'}},
               'fraction': {'transaction_amount': {'currency_code': 'EUR', 'value': '3.001'}},
               'transaction': {'transaction_id': 'OTHER999'}, 'reference': {'paypal_reference_id_type': 'TXN', 'paypal_reference_id': 'FOREIGN999'},
               'timestamp': {'transaction_initiation_date': '2026-08-01T00:00:00Z'},
               'missing_time': {'transaction_initiation_date': None}}
    snap, sha = merchant['observe'](**changes[change])
    with pytest.raises((ValueError, FenceBlocked, StopIteration)): bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert resources.state(account)['credits_micro'] == 0
    with auth.db() as c:
        assert c.execute("SELECT count(*) FROM payment_reconciliation_events WHERE normalized_json LIKE '%merchant_discovery_binding%'").fetchone()[0] == 0


@pytest.mark.parametrize('change', ['actor', 'secret', 'merchant', 'owner', 'amount', 'kind', 'snapshot', 'epoch'])
def test_context_drift_during_canonical_reads_rolls_back_money(merchant, account, change):
    snap, sha = merchant['observe']()
    reads = []
    def mutate(cfg, path):
        if not path.startswith('/v2/checkout/orders/'): return
        reads.append(path)
        if len(reads) != 3: return
        with auth.db() as c:
            if change == 'actor': c.execute('UPDATE users SET active=0 WHERE id=?', (merchant['admin'],))
            if change == 'secret': c.execute("UPDATE paypal_config SET client_secret='rotated'")
            if change == 'merchant': c.execute("UPDATE paypal_config SET client_id='different'")
            if change == 'owner': c.execute('UPDATE paypal_orders SET user_id=1 WHERE id=?', (merchant['local'],))
            if change == 'amount': c.execute('UPDATE paypal_orders SET amount_cents=600 WHERE id=?', (merchant['local'],))
            if change == 'kind': c.execute("UPDATE paypal_orders SET kind='subscription' WHERE id=?", (merchant['local'],))
            if change == 'epoch': c.execute('UPDATE regime_fence_state SET revision=revision+1')
            if change == 'snapshot': c.execute('DELETE FROM paypal_merchant_history WHERE id=?', (snap,))
    merchant['hook']['run'] = mutate
    with pytest.raises((FenceBlocked, ValueError, PermissionError)): bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert resources.state(account)['credits_micro'] == 0
    with auth.db() as c: assert c.execute('SELECT count(*) FROM paypal_captures').fetchone()[0] == 0


def test_failure_after_binding_and_partial_refund_rolls_back_then_recovers(merchant, account, monkeypatch):
    snap, sha = merchant['observe'](); original = paypal._apply_refund; calls = []
    def fail(c, data, event):
        calls.append(event)
        if len(calls) == 2: raise RuntimeError('injected transaction failure')
        return original(c, data, event)
    monkeypatch.setattr(paypal, '_apply_refund', fail)
    with pytest.raises(RuntimeError): bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert resources.state(account)['credits_micro'] == 0
    with auth.db() as c:
        # DDL participates in the money transaction too: a first failure must
        # roll back the newly created journal, not just its rows.
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone()
        assert not exists or c.execute('SELECT count(*) FROM payment_reconciliation_events').fetchone()[0] == 0
    monkeypatch.setattr(paypal, '_apply_refund', original)
    bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert resources.state(account)['credits_micro'] == 1_000_000


def test_private_admin_api_confirmation_and_no_provider_mutations(merchant, account, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda _: False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    snap, sha = merchant['observe'](); path = '/api/admin/paypal/merchant-history/'+snap
    with TestClient(main.app) as client:
        assert client.get(path+'/review').status_code == 401
        client.cookies.update(cookie(account)); assert client.get(path+'/review').status_code == 403
        client.cookies.update(cookie(merchant['admin']))
        response = client.get(path+'/review'); assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        body = {'observation_sha256': sha, 'confirm': True}
        assert client.post(path+'/reconcile', json=body).status_code == 403
        headers = {'X-MTA-Request': '1'}
        assert client.post(path+'/reconcile', json={**body, 'user_id': account}, headers=headers).status_code == 422
        assert client.post(path+'/reconcile', json={**body, 'confirm': False}, headers=headers).status_code == 422
        response = client.post(path+'/reconcile', json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()['ledger_reconciled'] and response.headers['cache-control'] == 'no-store'
        def unavailable(*_): raise httpx.ReadTimeout('SECRET PROVIDER DETAILS')
        merchant['hook']['run'] = unavailable
        response = client.post(path+'/reconcile', json=body, headers=headers)
        assert response.status_code == 409 and 'SECRET' not in response.text
    assert resources.state(account)['credits_micro'] == 1_000_000


def test_review_counts_all_cases_beyond_display_page_without_network(merchant):
    snap, _ = merchant['observe']()
    with auth.db() as c:
        original = dict(c.execute('SELECT * FROM paypal_merchant_history WHERE id=?', (snap,)).fetchone())
        data = json.loads(original['evidence_json']) * 101
        # A separately valid immutable snapshot can contain distinct observations
        # with repeated transaction IDs; review cannot truncate its totals.
        for i, row in enumerate(data):
            data[i] = {**row, 'transaction_id': 'UNKNOWN'+str(i)}
        digest = history.digest(data)
        identity = history.digest([original['environment'], original['merchant_fingerprint'], START, END, digest])
        c.execute('INSERT INTO paypal_merchant_history VALUES(?,?,?,?,?,?,?,?,?)',
                  (identity, original['environment'], original['merchant_fingerprint'], START, END, history.encode(data), digest, merchant['admin'], 1))
    before = len(merchant['calls']); result = bridge.review(merchant['admin'], identity, offset=100, limit=1)
    assert result['total'] == result['counts']['known_candidates'] == 101 and len(result['items']) == 1
    assert len(merchant['calls']) == before and not result['complete_account_history']


def test_refund_cannot_be_associated_with_another_capture_in_same_order(merchant, account):
    snap, sha = merchant['observe']('refund', 'TXN', paypal_reference_id='CAPTURE222')
    with pytest.raises(FenceBlocked, match='capture reference changed'):
        bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert resources.state(account)['credits_micro'] == 0


def test_discovery_never_adopts_payer_labels_when_original_order_is_missing(merchant, account):
    snap, sha = merchant['observe']('capture', 'TXN')
    with auth.db() as c:
        c.execute('DELETE FROM paypal_orders WHERE id=?', (merchant['local'],))
    with pytest.raises(FenceBlocked, match='Original local order missing'):
        bridge.reconcile(merchant['admin'], snap, sha, confirm=True)
    assert resources.state(account)['credits_micro'] == 0


def test_unknown_observation_and_unconfirmed_action_never_contact_provider(merchant, account):
    snap, sha = merchant['observe'](); before = len(merchant['calls'])
    for action in [lambda: bridge.reconcile(merchant['admin'], snap, sha),
                   lambda: bridge.reconcile(merchant['admin'], snap, 'a'*64, confirm=True),
                   lambda: bridge.reconcile(account, snap, sha, confirm=True)]:
        with pytest.raises((ValueError, PermissionError, FenceBlocked)): action()
    assert len(merchant['calls']) == before


def test_merchant_continuation_paths_are_exact_not_a_general_mutation_bypass():
    from app.service_admission import continuation
    base = '/api/admin/paypal/merchant-history/'+'a'*64
    for method, path in [('GET', base), ('GET', base+'/review'), ('POST', base+'/reconcile')]:
        assert continuation({'method': method, 'path': path})
    for method, path in [('POST', base), ('POST', base+'/review'), ('DELETE', base),
                         ('POST', base+'/reconcile/other'), ('POST', base.replace('a'*64,'invalid')+'/reconcile')]:
        assert not continuation({'method': method, 'path': path})


def test_actual_merchant_recovery_remains_available_under_service_drain(merchant, account, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, service_admission as gate
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda _: False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    snap, sha = merchant['observe'](); base = '/api/admin/paypal/merchant-history/'+snap
    monkeypatch.setenv('MTA_SERVICE_ADMISSION', gate.MODE)
    with TestClient(main.app) as client:
        client.cookies.update(cookie(merchant['admin'])); headers = {'X-MTA-Request': '1'}
        assert client.get('/api/admin/service-admission').status_code == 200
        drained = client.post('/api/admin/service-admission/change', headers=headers,
            json={'expected_generation': 0, 'draining': True, 'identifier': 'merchant-drain-1', 'confirm': True})
        assert drained.status_code == 200 and drained.json()['phase'] == 'draining', drained.text
        # The original unpaid local checkout still prevents complete drain.
        # Recovery must be available before it can close that original work.
        assert not drained.json()['drained']
        assert client.get('/api/service-regime').status_code == 503
        assert client.get(base+'/review').status_code == 200
        result = client.post(base+'/reconcile', headers=headers, json={'observation_sha256': sha, 'confirm': True})
        assert result.status_code == 200, result.text
        assert result.json()['ledger_reconciled'] and not result.json()['transition_authorized']
        import time
        deadline = time.monotonic()+10
        state = client.get('/api/admin/service-admission').json()
        while not state['drained'] and time.monotonic() < deadline:
            time.sleep(.05)
            state = client.get('/api/admin/service-admission').json()
        assert state['drained'], state
    with gate.control():
        assert resources.state(account)['credits_micro'] == 1_000_000
