"""Authenticated webhook -> journal -> positions -> wallet -> readiness tests."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from app import auth, credit_purchases as shop, resource_accounts as r
from app import payment_reconciliation as pr
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_credit_checkout import prepare, paid_event, signed


def purchase(account,monkeypatch,key='reconciliation-e2e-123'):
    prepare(account,monkeypatch)
    return shop.checkout(account,500,key)['order_id']


def refund(amount,event='evt_refund',intent='pi_test'):
    return {'id':event,'type':'charge.refunded','data':{'object':{'id':'ch_test',
        'payment_intent':intent,'amount_refunded':amount,'amount':500,'currency':'eur'}}}


def dispute(status='needs_response',created=100,event='evt_dispute',amount=500):
    return {'id':event,'type':'charge.dispute.updated','created':created,'data':{'object':{
        'id':'dp_test','payment_intent':'pi_test','amount':amount,'currency':'eur','status':status}}}


def snapshot():
    with auth.db() as c:return pr.report(c)


def test_refund_before_paid_is_durable_and_applied_atomically(account,monkeypatch):
    order=purchase(account,monkeypatch)
    assert shop.event(*signed(refund(200)))['pending']
    assert snapshot()['pending']==1 and r.state(account)['credits_micro']==0
    shop.event(*signed(paid_event(order)))
    assert snapshot()['pending']==0
    assert r.state(account)['credits_micro']==3_000_000
    assert snapshot()['positions'][0]['refunded_minor']==200
    assert snapshot()['verified'] and not snapshot()['transition_safe']


def test_full_refund_after_closed_checkout_and_replay(account,monkeypatch):
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    for event in (refund(200),refund(500,'evt_full'),refund(100,'evt_old')):
        shop.event(*signed(event));shop.event(*signed(event))
    assert r.state(account)['credits_micro']==0
    assert snapshot()['positions'][0]['net_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0]=='closed'
        assert c.execute('SELECT count(*) FROM payment_reconciliation_movements').fetchone()[0]==3


def test_dispute_hold_won_then_stale_open_does_not_remove_credits(account,monkeypatch):
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    shop.event(*signed(dispute()));assert r.state(account)['credits_micro']==0
    shop.event(*signed(dispute('won',200,'evt_won')));assert r.state(account)['credits_micro']==5_000_000
    shop.event(*signed(dispute('under_review',150,'evt_stale')))
    assert r.state(account)['credits_micro']==5_000_000
    assert snapshot()['verified']


def test_pending_dispute_and_partial_refund_do_not_allow_overcredit(account,monkeypatch):
    order=purchase(account,monkeypatch)
    shop.event(*signed(dispute(amount=300)));shop.event(*signed(refund(200)))
    shop.event(*signed(paid_event(order)));assert r.state(account)['credits_micro']==0
    shop.event(*signed(dispute('won',200,'evt_won',amount=300)))
    assert r.state(account)['credits_micro']==3_000_000


def test_lost_dispute_never_reopens_on_stale_or_contradictory_event(account,monkeypatch):
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    shop.event(*signed(dispute('lost',200)))
    shop.event(*signed(dispute('needs_response',100,'evt_old')))
    with pytest.raises(FenceBlocked):shop.event(*signed(dispute('won',300,'evt_contradiction')))
    assert r.state(account)['credits_micro']==0


def test_event_identity_conflict_even_after_success_cannot_mutate_money(account,monkeypatch):
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    event=refund(200);shop.event(*signed(event));event['data']['object']['amount_refunded']=400
    with pytest.raises(FenceBlocked):shop.event(*signed(event))
    assert r.state(account)['credits_micro']==3_000_000


def test_payment_intent_cannot_fund_two_orders(account,monkeypatch):
    first=purchase(account,monkeypatch);shop.event(*signed(paid_event(first)))
    second=shop.checkout(account,500,'reconciliation-second-order')['order_id']
    with pytest.raises(FenceBlocked):shop.event(*signed(paid_event(second,'evt_second')))
    assert r.state(account)['credits_micro']==5_000_000


def test_credit_mutation_failure_rolls_back_journal_position_inbox_and_payment(account,monkeypatch):
    order=purchase(account,monkeypatch)
    from app import regime_checkout_fence
    original=regime_checkout_fence.settle_if_enrolled
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',lambda *a:(_ for _ in ()).throw(RuntimeError('crash')))
    with pytest.raises(RuntimeError):shop.event(*signed(paid_event(order)))
    assert r.state(account)['credits_micro']==0
    with auth.db() as c:
        assert c.execute('SELECT status FROM credit_purchase_orders').fetchone()[0]=='pending'
        assert c.execute("SELECT name FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone() is None
    monkeypatch.setattr(regime_checkout_fence,'settle_if_enrolled',original)
    shop.event(*signed(paid_event(order)));assert r.state(account)['credits_micro']==5_000_000


def test_concurrent_delivery_only_one_credit_and_refund(account,monkeypatch):
    order=purchase(account,monkeypatch)
    for payload in (paid_event(order),refund(200)):
        raw,sig=signed(payload)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:shop.event(raw,sig),range(8)))
        assert all(x['received'] for x in results)
    assert r.state(account)['credits_micro']==3_000_000
    assert snapshot()['total']==1 and snapshot()['verified']


def test_legacy_paid_position_is_reconciled_without_second_credit(account,monkeypatch):
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    with auth.db() as c:
        c.execute('DELETE FROM payment_reconciliation_movements')
        c.execute('DELETE FROM payment_reconciliation_positions')
        c.execute('DELETE FROM payment_reconciliation_events')
    shop.event(*signed(paid_event(order,'evt_legacy_readback')))
    shop.event(*signed(refund(200)))
    assert snapshot()['verified'] and r.state(account)['credits_micro']==3_000_000


def test_tampered_financial_credit_is_detected(account,monkeypatch):
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    with auth.db() as c:c.execute('UPDATE resource_credits SET delta_micro=1')
    assert not snapshot()['verified']


@pytest.mark.parametrize('mutation',[{'amount_refunded':True},{'amount_refunded':501},{'currency':'usd'},{'amount':499}])
def test_invalid_refund_is_rejected_without_committing_event(account,monkeypatch,mutation):
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    event=refund(200);event['data']['object'].update(mutation)
    with pytest.raises(ValueError):shop.event(*signed(event))
    assert r.state(account)['credits_micro']==5_000_000
    assert snapshot()['pending']==0


def test_financial_journal_payload_cannot_be_modified_or_reopened(account,monkeypatch):
    import sqlite3
    order=purchase(account,monkeypatch);shop.event(*signed(paid_event(order)))
    with auth.db() as c:
        with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE payment_reconciliation_events SET normalized_json='{}'")
        with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE payment_reconciliation_events SET state='pending'")
    assert snapshot()['verified']
