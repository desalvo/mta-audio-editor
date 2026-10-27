"""Actual legacy financial gaps before a loss; never fabricate a fee or debt."""
import sqlite3

import pytest

from app import auth
from app.payment_reconciliation import report
from app.subscription_basis_audit import review
from test_r210_subscriptions import account as account, plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_original_subscription_loss import paid as paid, reverse  # noqa: F401


def test_new_fulfillment_basis_passes_without_modifying_account(paid):
    with auth.db() as c:
        before=c.total_changes
        c.execute('PRAGMA query_only=ON')
        result=review(c)
        assert result['verified'] and result['checked']==1 and result['total']==0
        assert c.total_changes==before and not c.in_transaction
        assert not result['transition_safe'] and not result['automatic_reconstruction_allowed']


def test_missing_legacy_basis_blocks_before_any_dispute_or_reversal(paid):
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        before=c.total_changes
        result=report(c)
        assert not result['verified']
        assert 'subscription_original_basis_unverified' in result['issues']
        assert result['subscription_original_basis_review']['items']==[
            {'order_id':paid[0],'reason':'original_payment_basis_missing'}]
        assert result['subscription_original_loss_review']['verified']  # no loss yet
        assert c.total_changes==before
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==0


def test_current_price_paid_status_and_refund_balance_cannot_reconstruct_legacy(paid):
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        c.execute('UPDATE resource_plan_charges SET amount_micro=5000000,status=\'paid\'')
        c.execute('UPDATE paypal_orders SET refund_due_micro=0')
        assert review(c)['items'][0]['reason']=='original_payment_basis_missing'
    reverse()
    with auth.db() as c:
        assert review(c)['total']==1
        assert c.execute('SELECT count(*) FROM subscription_payment_basis').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM paypal_subscription_reversals').fetchone()[0]==0


@pytest.mark.parametrize('field,value',[
    ('user_id',999),('period_start',1),('gross_micro',6000000),('fee_micro',4000000),
])
def test_conflicting_basis_is_not_treated_as_historical_proof(paid,field,value):
    with auth.db() as c:
        c.execute('DROP TRIGGER subscription_payment_basis_immutable_update')
        c.execute('PRAGMA ignore_check_constraints=ON')
        # Fixed test-only field allowlist; never interpolate request data.
        sql={'user_id':'UPDATE subscription_payment_basis SET user_id=?',
             'period_start':'UPDATE subscription_payment_basis SET period_start=?',
             'gross_micro':'UPDATE subscription_payment_basis SET gross_micro=?',
             'fee_micro':'UPDATE subscription_payment_basis SET fee_micro=?'}[field]
        c.execute(sql,(value,))
        assert review(c)['items']==[{'order_id':paid[0],'reason':'original_payment_basis_conflict'}]


@pytest.mark.parametrize('sql',[
    'UPDATE paypal_captures SET amount_cents=299 WHERE id=\'CAPTURE111\'',
    'DELETE FROM paypal_captures',
    'UPDATE paypal_captures SET amount_cents=-1 WHERE id=\'CAPTURE111\'',
])
def test_partial_or_invalid_capture_inventory_cannot_verify_basis(paid,sql):
    with auth.db() as c:
        c.execute(sql)
        assert review(c)['items'][0]['reason']=='original_capture_total_unproved'


@pytest.mark.parametrize('sql',[
    "UPDATE payment_reconciliation_positions SET funded=0",
    "UPDATE payment_reconciliation_positions SET user_id=999",
    "UPDATE payment_reconciliation_positions SET currency='USD'",
    "UPDATE payment_reconciliation_positions SET amount_minor=499",
    "DELETE FROM payment_reconciliation_positions",
])
def test_original_funding_must_match_owner_currency_and_amount(paid,sql):
    with auth.db() as c:
        c.execute(sql)
        assert review(c)['items'][0]['reason']=='original_funding_position_unproved'


def test_unpaid_checkout_is_not_a_missing_original_payment(account,provider,monkeypatch):
    from test_r210_paypal_reconciliation_e2e import setup_order
    setup_order(account,provider,monkeypatch,subscription=True,before_capture=True)
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        assert review(c)['verified'] and review(c)['checked']==0


def test_historical_terminal_label_does_not_hide_paid_order(paid):
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        c.execute("UPDATE paypal_orders SET status='refunded'")
        assert review(c)['checked']==1 and review(c)['total']==1


def test_basis_cannot_be_attached_to_a_different_payment_kind(paid):
    with auth.db() as c:
        c.execute("UPDATE paypal_orders SET kind='credits'")
        assert review(c)['items'][0]['reason']=='original_payment_basis_unbound'


def test_audit_preserves_callers_write_transaction_and_rollback(paid):
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute("UPDATE paypal_orders SET status='refunded'")
        assert review(c)['verified'] and c.in_transaction
        c.rollback()
        assert c.execute('SELECT status FROM paypal_orders').fetchone()[0]=='paid'


def add_legacy_orders(c,original_id,count):
    for n in range(count):
        c.execute('''INSERT INTO paypal_orders
            (id,user_id,request_id,kind,period_start,amount_cents,environment,client_fingerprint,
             provider_order,checkout_url,status,created_at,paid_at,refund_due_micro)
            SELECT ?,user_id,?,kind,period_start,amount_cents,environment,client_fingerprint,
             ?,checkout_url,status,created_at,paid_at,refund_due_micro FROM paypal_orders WHERE id=?''',
            (f'legacy-{n:03d}',f'legacy-request-{n}',f'PROVIDER{n:06d}',original_id))


def test_pagination_checks_all_orders_even_when_page_is_empty(paid):
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
        add_legacy_orders(c,paid[0],55)
        a=review(c,limit=25);b=review(c,limit=25,offset=25);d=review(c,limit=25,offset=50)
        assert a['total']==b['total']==d['total']==56
        ids=[row['order_id'] for page in (a,b,d) for row in page['items']]
        assert len(ids)==len(set(ids))==56 and ids==sorted(ids)
        empty=review(c,offset=999)
        assert not empty['verified'] and empty['total']==56 and empty['items']==[]


@pytest.mark.parametrize('kwargs',[{'limit':0},{'limit':201},{'limit':True},{'offset':-1},{'offset':False}])
def test_invalid_pages_are_rejected_without_starting_transaction(kwargs):
    c=sqlite3.connect(':memory:')
    try:
        with pytest.raises(ValueError):review(c,**kwargs)
        assert not c.in_transaction
    finally:c.close()


@pytest.fixture
def evidence_client(paid,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    from app.regime_payment_outbox import SCHEMA
    with auth.db() as c:
        c.execute(SCHEMA)
    with TestClient(main.app) as client:
        yield client


def test_actual_private_api_permissions_pagination_and_no_cache(evidence_client,paid,account):
    from test_r210_legal_documents import cookie
    url='/api/admin/service-regime/subscription-evidence'
    assert evidence_client.get(url).status_code==401
    evidence_client.cookies.update(cookie(account))
    assert evidence_client.get(url).status_code==403
    with auth.db() as c:
        c.execute('DROP TABLE subscription_payment_basis')
    evidence_client.cookies.update(cookie(auth.find_user('admin')['id']))
    response=evidence_client.get(url+'?limit=1&offset=0')
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert response.json()['items']==[{'order_id':paid[0],'reason':'original_payment_basis_missing'}]
    ledger=evidence_client.get('/api/admin/service-regime/payment-ledger')
    assert ledger.status_code==200 and not ledger.json()['verified']
    assert 'subscription_original_basis_unverified' in ledger.json()['issues']
    readiness=evidence_client.get('/api/admin/service-regime/combined-readiness?target=NON_COMMERCIAL')
    assert readiness.status_code==200
    assert 'payment_ledger_unverifiable' in readiness.json()['unresolved']
    assert evidence_client.get(url+'?limit=201').status_code==422
    assert evidence_client.get(url+'?offset=-1').status_code==422
    assert 'quota@example.test' not in response.text and 'client_secret' not in response.text


def test_actual_api_schema_failure_is_not_a_verified_empty_list(evidence_client):
    from test_r210_legal_documents import cookie
    with auth.db() as c:
        c.execute('ALTER TABLE subscription_payment_basis RENAME COLUMN fee_micro TO broken_fee')
    evidence_client.cookies.update(cookie(auth.find_user('admin')['id']))
    response=evidence_client.get('/api/admin/service-regime/subscription-evidence')
    assert response.status_code==409
