"""Owner/quote/fence changes during authenticated approval readback deny capture."""
import json
import pytest
from app import auth,paypal_payments as paypal,resource_entitlements
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account,plan  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401


@pytest.mark.parametrize('change',['epoch','merchant','owner','permission','inactive','settled_fee','dispatch','pending_evidence'])
def test_capture_rechecks_original_contract_after_provider_approval(account,provider,monkeypatch,change):
    state=plan(account,price_micro=5_000_000 if change=='settled_fee' else 0)
    body={'kind':'subscription','period_start':state['period']['start'],'request_id':'preflight-fee-checkout'} if change=='settled_fee' else {'kind':'credits','amount_cents':500,'request_id':'preflight-credit-checkout'}
    local=paypal.checkout(account,body)['order_id'];original=paypal._api;changed=[]
    def api(cfg,method,path,*args):
        value=original(cfg,method,path,*args)
        if method=='GET' and '/v2/checkout/orders/' in path and not changed:
            changed.append(change)
            if change=='epoch':
                (auth.data_root()/'service-regime.json').write_text(json.dumps({'regime':'COMMERCIAL','revision':1}))
                with auth.db() as c:c.execute('UPDATE regime_fence_state SET revision=1')
            elif change=='merchant':paypal.settings({'client_secret':'rotated-after-approval'})
            elif change=='permission':resource_entitlements.set_policy(account,{'subscriptions_allowed':False},1)
            else:
                with auth.db() as c:
                    if change=='owner':c.execute('UPDATE paypal_orders SET user_id=1 WHERE id=?',(local,))
                    if change=='inactive':c.execute('UPDATE users SET active=0 WHERE id=?',(account,))
                    if change=='settled_fee':c.execute("UPDATE resource_plan_charges SET status='paid' WHERE user_id=?",(account,))
                    if change=='dispatch':c.execute("UPDATE regime_payment_outbox SET state='uncertain',provider_reference=NULL WHERE operation_id=?",('checkout:paypal:'+local,))
                    if change=='pending_evidence':
                        from app.payment_reconciliation import record_event
                        record_event(c,'paypal','pending-original-money','a'*64,{'type':'risk','capture_id':'CAPTURE111'})
                        c.execute("UPDATE payment_reconciliation_events SET order_id=? WHERE event_id='pending-original-money'",(local,))
        return value
    monkeypatch.setattr(paypal,'_api',api);before=len(provider[1])
    with pytest.raises((ValueError,FenceBlocked)):paypal.capture(account,local)
    assert changed==[change]
    assert not any(method=='POST' and path.endswith('/capture') for method,path,_,_ in provider[1][before:])
    with auth.db() as c:
        assert c.execute('SELECT status FROM paypal_orders WHERE id=?',(local,)).fetchone()[0]=='pending'
        assert c.execute('SELECT coalesce(sum(delta_micro),0) FROM resource_credits WHERE user_id=?',(account,)).fetchone()[0]==0
