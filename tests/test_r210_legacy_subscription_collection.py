"""Canonical refunds remain recorded without inventing legacy collection authority."""
import json
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import auth, paypal_payments as paypal, resource_accounts as resources
from app import payment_reconciliation as journal
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_original_subscription_loss import paid as paid  # noqa: F401
from test_r210_paypal_reconciliation_e2e import HEADERS


@pytest.mark.parametrize('surplus', [0, 1_000_000, 5_000_000])
def test_legacy_refund_does_not_guess_original_fee_from_mutable_surplus(paid, surplus):
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        c.execute('UPDATE paypal_orders SET refund_due_micro=? WHERE id=?', (surplus, paid[0]))
    result = paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    assert result['received']
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_refunds').fetchone()[0] == 1
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0] == 0
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?', (paid[0],)).fetchone()[0] == surplus
        report = journal.report(c)
        assert not report['verified']
        assert report['subscription_reversal_due_micro'] is None
        assert 'subscription_original_basis_unverified' in report['issues']


def test_preexisting_unproved_legacy_receivable_cannot_start_another_payment(paid, account, provider):
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    before = len(provider[1])
    with pytest.raises(ValueError, match='original|Original|evidence'):
        paypal.checkout(account, {'kind': 'subscription_reversal', 'refund_id': 'REFUND111',
                                 'expected_due_micro': 3_000_000, 'request_id': 'legacy-collection-refused'})
    assert len(provider[1]) == before
    # Preserve the original disputed record; denial is not debt forgiveness.
    with auth.db() as c:
        assert c.execute('SELECT amount_micro FROM paypal_subscription_reversals').fetchone()[0] == 3_000_000
        assert c.execute('SELECT count(*) FROM subscription_repayment_targets').fetchone()[0] == 0
    row = resources.transactions(account)['subscription_reversals'][0]
    assert row['collection_verified'] is False
    assert row['due_micro'] is None and row['covered_micro'] is None


@pytest.mark.parametrize('change', ['basis_missing', 'owner', 'period', 'capture', 'funding', 'excess_obligation'])
def test_collection_revalidates_original_identity_and_allocation(paid, account, provider, change):
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    with auth.db() as c:
        if change == 'basis_missing':
            c.execute('DROP TABLE subscription_payment_basis')
        elif change in ('owner', 'period'):
            c.execute('DROP TRIGGER paypal_subscription_reversals_immutable_update')
            c.execute({'owner': 'UPDATE paypal_subscription_reversals SET user_id=1',
                       'period': 'UPDATE paypal_subscription_reversals SET period_start=1'}[change])
        elif change == 'capture':
            c.execute("UPDATE paypal_captures SET amount_cents=299 WHERE id='CAPTURE111'")
        elif change == 'funding':
            c.execute('UPDATE payment_reconciliation_positions SET funded=0')
        else:
            c.execute('DROP TRIGGER paypal_subscription_reversals_immutable_update')
            c.execute('UPDATE paypal_subscription_reversals SET amount_micro=6000000')
    before = len(provider[1])
    with pytest.raises(ValueError):
        paypal.checkout(account, {'kind': 'subscription_reversal', 'refund_id': 'REFUND111',
                                 'expected_due_micro': 3_000_000, 'request_id': 'invalid-original-collection'})
    assert len(provider[1]) == before
    with auth.db() as c:
        assert not journal.report(c)['verified']


def test_approved_repayment_cannot_capture_after_original_proof_disappears(paid, account, provider):
    from test_r210_subscription_repayment_e2e import checkout
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    local = checkout(account)['order_id']
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    before = len(provider[1])
    with pytest.raises(ValueError, match='original evidence'):
        paypal.capture(account, local)
    assert len(provider[1]) == before
    with auth.db() as c:
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?', (local,)).fetchone()[0] == 'pending'
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0] == 0
        assert c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',
                         ('checkout:paypal:' + local,)).fetchone()[0] == 'open'


def test_lost_original_proof_during_approval_readback_denies_collection(paid, account, provider, monkeypatch):
    from test_r210_subscription_repayment_e2e import checkout
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    local = checkout(account)['order_id']
    original = paypal._api

    def api(config, method, path, *args):
        result = original(config, method, path, *args)
        if method == 'GET' and path.startswith('/v2/checkout/orders/'):
            with auth.db() as c:
                c.execute('DROP TABLE subscription_payment_basis')
        return result

    monkeypatch.setattr(paypal, '_api', api)
    before = sum(call[1].endswith('/capture') for call in provider[1])
    with pytest.raises(ValueError, match='original evidence'):
        paypal.capture(account, local)
    assert sum(call[1].endswith('/capture') for call in provider[1]) == before


def test_completed_external_repayment_cannot_allocate_unproved_obligation(paid, account, provider):
    from test_r210_subscription_repayment_e2e import checkout
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    local = checkout(account)['order_id']
    with auth.db() as c:
        pid = c.execute('SELECT provider_order FROM paypal_orders WHERE id=?', (local,)).fetchone()[0]
    canonical = paypal._api({}, 'POST', '/v2/checkout/orders/' + pid + '/capture')
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    with pytest.raises(FenceBlocked, match='original|Original'):
        paypal.fulfill(local, canonical)
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_captures WHERE order_id=?', (local,)).fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0] == 0
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?', (local,)).fetchone()[0] == 'pending'


def test_refund_of_earlier_repayment_is_recorded_without_guessing_legacy_refund_due(paid, account, provider, monkeypatch):
    from test_r210_subscription_repayment_e2e import checkout, refund, capture_id
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    local = checkout(account)['order_id']
    paypal.capture(account, local)
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        c.execute('UPDATE paypal_orders SET refund_due_micro=12345 WHERE id=?', (local,))
    assert refund(monkeypatch, capture_id(local))['received']
    with auth.db() as c:
        assert c.execute("SELECT amount_cents FROM paypal_refunds WHERE id='REFUND333'").fetchone()[0] == 100
        # A refund of this actual payment reduces its recorded refundable amount;
        # sync must not replace it with an invented coverage/excess calculation.
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?', (local,)).fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0] == 1
        report = journal.report(c)
        assert not report['verified'] and report['subscription_repayment_refund_due_micro'] is None


def test_concurrent_legacy_refunds_preserve_one_cash_receipt_without_a_guessed_debt(paid):
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    raw = json.dumps(paid[2]).encode()
    with ThreadPoolExecutor(3) as pool:
        assert all(r['received'] for r in pool.map(lambda _: paypal.webhook(raw, HEADERS), range(3)))
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM paypal_refunds').fetchone()[0] == 1
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0] == 0
        assert c.execute('SELECT refunded_minor FROM payment_reconciliation_positions').fetchone()[0] == 300


@pytest.mark.parametrize('surplus', [0, 5_000_000])
def test_known_original_basis_determines_fee_even_if_mutable_surplus_changes(paid, account, surplus):
    with auth.db() as c:
        c.execute('UPDATE paypal_orders SET refund_due_micro=? WHERE id=?', (surplus, paid[0]))
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    row = resources.transactions(account)['subscription_reversals'][0]
    assert row['collection_verified'] and row['due_micro'] == 3_000_000
    with auth.db() as c:
        assert c.execute('SELECT refund_due_micro FROM paypal_orders WHERE id=?', (paid[0],)).fetchone()[0] == 0


def test_owner_and_admin_api_show_unknown_without_disclosing_another_owners_gaps(paid, account, provider, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    from test_r210_legal_documents import cookie
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda _: False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    body = {'kind': 'subscription_reversal', 'refund_id': 'REFUND111',
            'expected_due_micro': 3_000_000, 'request_id': 'unproved-source-api-123'}
    with TestClient(main.app) as client:
        assert client.get('/api/account/subscription').status_code == 401
        client.cookies.update(cookie(account))
        result = client.get('/api/account/subscription')
        assert result.status_code == 200, result.text
        data = result.json()['transactions']
        assert data['subscription_payment_evidence']['total'] == 1
        assert data['subscription_reversals'][0]['due_micro'] is None
        assert client.post('/api/account/paypal/checkout', json=body).status_code == 403
        before = len(provider[1])
        assert client.post('/api/account/paypal/checkout', json=body,
                           headers={'X-MTA-Request': '1'}).status_code == 422
        assert len(provider[1]) == before
        assert client.get('/api/admin/service-regime/subscription-evidence').status_code == 403
        client.cookies.update(cookie(auth.find_user('admin')['id']))
        own = client.get('/api/account/subscription').json()['transactions']
        assert own['subscription_payment_evidence']['verified']
        assert own['subscription_payment_evidence']['items'] == [] and own['subscription_reversals'] == []
        result = client.get('/api/admin/service-regime/payment-ledger').json()
        assert not result['verified'] and result['subscription_reversal_due_micro'] is None


def test_owner_evidence_cannot_disclose_a_misbound_basis_for_another_owners_order(paid, account):
    from app.subscription_basis_audit import review
    with auth.db() as c:
        # A corrupt legacy import claims this user's basis, but the actual order
        # belongs to another owner. Only the global administrator audit sees it.
        c.execute("UPDATE paypal_orders SET user_id=?,kind='credits' WHERE id=?",
                  (auth.find_user('admin')['id'], paid[0]))
        owner = review(c, user_id=account)
        assert owner['items'] == [] and owner['total'] == 0
        assert review(c)['items'] == [{'order_id': paid[0], 'reason': 'original_payment_basis_unbound'}]


def test_restored_exact_original_basis_resumes_same_approved_repayment_once(paid, account, provider):
    from app import subscription_receivables
    from test_r210_subscription_repayment_e2e import checkout
    paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    local = checkout(account)['order_id']
    with auth.db() as c:
        original = tuple(c.execute('SELECT * FROM subscription_payment_basis').fetchone())
        c.execute('DROP TABLE subscription_payment_basis')
    with pytest.raises(ValueError, match='original evidence'):
        paypal.capture(account, local)
    # Test-only restoration of an exact retained original, not reconstruction
    # from current fees or a new operator-supplied grant.
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        subscription_receivables.initialize(c)
        c.execute('INSERT INTO subscription_payment_basis VALUES(?,?,?,?,?,?)', original)
    assert paypal.capture(account, local)['status'] == 'paid'
    assert paypal.capture(account, local)['status'] == 'paid'
    assert len(provider[0]) == 2
    row = resources.transactions(account)['subscription_reversals'][0]
    assert row['collection_verified'] and row['due_micro'] == 0
    with auth.db() as c:
        assert c.execute('SELECT count(*) FROM subscription_repayment_allocations').fetchone()[0] == 1


@pytest.mark.parametrize('language', ['it', 'en'])
@pytest.mark.parametrize('existing_claim', [False, True])
def test_shipped_owner_panel_never_labels_unknown_as_zero_or_settled(paid, account, language, existing_claim):
    if existing_claim:
        paypal.webhook(json.dumps(paid[2]).encode(), HEADERS)
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    data = {'transactions': resources.transactions(account)}
    source = Path(__file__).resolve().parents[1] / 'app/static/subscriptions.js'
    script = r"""
const fs=require('fs'),vm=require('vm');
const data=JSON.parse(fs.readFileSync(0,'utf8'));
let source=fs.readFileSync(process.argv[1],'utf8').split('let ownerGeneration=0;')[0];
const context={window:{MtaLocale:{language:data.language}},Intl};
vm.runInNewContext(source+'globalThis.result={html:reversalPanel('+JSON.stringify(data.payload)+'),unknown:money(null)};})();',context);
process.stdout.write(JSON.stringify(context.result));
"""
    result = subprocess.run(['node', '-e', script, str(source)],
                            input=json.dumps({'language': language, 'payload': data}),
                            text=True, capture_output=True, check=True)
    rendered = json.loads(result.stdout)
    assert 'data-subscription-evidence-warning' in rendered['html']
    assert 'data-repayment=' not in rendered['html']
    assert ('Regolato' if language == 'it' else 'Settled') not in rendered['html']
    assert rendered['unknown'] == ('Da verificare' if language == 'it' else 'Unverified')
    if existing_claim:
        assert 'data-collection-unverified' in rendered['html']
