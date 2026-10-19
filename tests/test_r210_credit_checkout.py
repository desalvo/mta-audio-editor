"""Subscription-only purchases, verified fulfillment, refunds and denial before queueing."""
import hashlib
import hmac
import json
import time
import pytest
from app import auth,resource_accounts as r,resource_entitlements as e,credit_purchases as shop
from test_r210_subscriptions import account as quota_account,plan,finish  # noqa: F401


@pytest.fixture
def account(request):return request.getfixturevalue('quota_account')


def signed(payload):
    raw=json.dumps(payload).encode();stamp=str(int(time.time()))
    sig=hmac.new(b'whsec_test',stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return raw,'t='+stamp+',v1='+sig


def prepare(account,monkeypatch):
    plan(account);shop.settings({'secret_key':'sk_test_test','webhook_secret':'whsec_test'})
    calls=[]
    def provider(data,key,order):
        calls.append((data,key,order));return {'id':'cs_test_'+order,'url':'https://checkout.stripe.com/c/pay/'+order}
    monkeypatch.setattr(shop,'_stripe',provider)
    return calls


def paid_event(order,identifier='evt_paid'):
    return {'id':identifier,'type':'checkout.session.completed','data':{'object':{'id':'cs_test_'+order,'metadata':{'mta_order':order},'client_reference_id':order,'amount_total':500,'currency':'eur','payment_status':'paid','payment_intent':'pi_test'}}}


def test_eligibility_and_global_switch_are_enforced_on_backend(account):
    assert not shop.catalog(account)['eligible']
    with pytest.raises(ValueError):r.grant(account,100,'free grant',1,'no-sub-grant-key')
    plan(account);r.grant(account,100,'free grant',1,'with-sub-grant-key')
    r.configure({'credits_enabled':False})
    assert not shop.catalog(account)['eligible']
    with pytest.raises(ValueError):r.grant(account,100,'free grant',1,'disabled-grant-key')
    e.set_policy(account,{'subscriptions_allowed':False},1)
    assert not r.state(account)['access']['blocked'] and not r.state(account)['policy']['credit_billing']
    before=r.state(account)['credits_micro'];finish(account,12)
    assert r.state(account)['credits_micro']==before


def test_checkout_is_quoted_and_only_signed_paid_event_adds_money(account,monkeypatch):
    calls=prepare(account,monkeypatch)
    x=shop.checkout(account,500,'request-id-123');y=shop.checkout(account,500,'request-id-123')
    assert x==y and len(calls)==1 and r.state(account)['credits_micro']==0
    raw,sig=signed(paid_event(x['order_id']))
    with pytest.raises(ValueError):shop.event(raw,sig+'bad')
    assert r.state(account)['credits_micro']==0
    shop.event(raw,sig);shop.event(raw,sig)
    assert r.state(account)['credits_micro']==5_000_000
    shop.event(*signed(paid_event(x['order_id'],'evt_duplicate_other_id')))
    assert r.state(account)['credits_micro']==5_000_000
    with pytest.raises(ValueError):shop.checkout(account,1000,'request-id-123')


def test_wrong_amount_unpaid_forged_and_refunded_events(account,monkeypatch):
    prepare(account,monkeypatch);order=shop.checkout(account,500,'other-request-123')['order_id']
    data=paid_event(order);data['data']['object']['payment_status']='unpaid'
    shop.event(*signed(data));assert r.state(account)['credits_micro']==0
    data=paid_event(order);data['data']['object']['amount_total']=1000
    with pytest.raises(ValueError):shop.event(*signed(data))
    shop.event(*signed(paid_event(order)))
    refund={'id':'evt_refund','type':'charge.refunded','data':{'object':{'payment_intent':'pi_test','amount_refunded':200,'currency':'eur'}}}
    shop.event(*signed(refund));shop.event(*signed(refund))
    assert r.state(account)['credits_micro']==3_000_000
    assert shop.catalog(account)['orders'][0]['refunded_cents']==200


def test_zero_credit_overage_refuses_before_queue_entry(account,monkeypatch,tmp_path):
    from app import ai_arranger_runtime as queue,resource_access
    plan(account);finish(account,10)
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    with pytest.raises(resource_access.CreditAdmissionError):queue.start('project-test','arranger',lambda *_:None,job_id='refused-credit-job',payload={'actor_user_id':account},defer_spawn=True)
    assert queue.get('refused-credit-job') is None


def test_legal_minimum_exactly_five_fields_and_pdf_omits_optional(account):
    from app import legal
    fields={'operator_name':'Example operator','operator_country':'Italy','support_email':'support@example.test','public_url':'https://mta.example.test','effective_date':'2026-10-19'}
    cfg=legal.save(fields,1);assert cfg['ready'] and not cfg['reviewed']
    for kind in ('privacy','terms'):
        for lang in ('it','en'):
            html,_=legal.document_html(kind,lang)
            assert 'Example operator' in html and 'support@example.test' in html and '{{' not in html
            assert 'DPO:' not in html
            assert legal.pdf_document(kind,lang).body.startswith(b'%PDF')
    for key in fields:
        with pytest.raises(ValueError):legal.save({**fields,key:''},1)


def test_provider_secrets_are_masked_and_sealed_at_rest(account):
    visible=shop.settings({'secret_key':'sk_test_secret','webhook_secret':'whsec_secret'})
    assert 'sk_test_secret' not in json.dumps(visible) and visible['configured']
    with auth.db() as c:
        row=c.execute('SELECT * FROM credit_payment_config WHERE id=1').fetchone()
        assert row['secret_key']!='sk_test_secret' and auth._open(row['secret_key'])=='sk_test_secret'


def test_paid_plan_fees_do_not_consume_overage_credits(account):
    plan(account,price_micro=1234)
    assert r.state(account)['funded'] and r.state(account)['credits_micro']==0
    r.grant(account,1000,'overage funds',1,'plan-separate-fees')
    assert r.state(account)['credits_micro']==1000
    with auth.db() as c:assert c.execute('SELECT amount_micro FROM resource_plan_charges WHERE user_id=?',(account,)).fetchone()[0]==1234


def test_legacy_schema_migrates_before_first_job(account):
    with auth.db() as c:
        c.execute('ALTER TABLE resource_config DROP COLUMN credits_enabled')
        r.prepare_upgrade(c)
        assert 'credits_enabled' in {x[1] for x in c.execute('PRAGMA table_info(resource_config)')}
    assert not r.state(account)['credits_enabled']


def test_subscription_refusal_never_offers_credits_as_replacement(account):
    from app import resource_access
    e.set_policy(account,{'subscriptions_allowed':True,'access_required':True},1)
    with pytest.raises(resource_access.CreditAdmissionError) as exc:resource_access.preflight(account)
    assert exc.value.code=='subscription_required'
