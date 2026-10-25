"""Recover an uncertain creation's provider ID using authenticated GET only.

The administrator supplies an identifier, never a URL or economic observation.
Binding a matched provider object confirms creation, not payment settlement.
"""
import hashlib
import json
import re
from urllib.parse import urlsplit

import httpx
from . import auth
from .regime_operation_fence import FenceBlocked
from .regime_provider_probe import _get,_reference,ProviderProbeError


def recover(provider,order_id,reference,*,client=None):
    if provider not in ('stripe','paypal') or not isinstance(order_id,str) or not 1<=len(order_id)<=120:
        raise ValueError('Invalid checkout recovery request')
    reference=_reference(reference)
    from . import credit_purchases as stripe,paypal_payments as paypal
    with auth.db() as c:
        if provider=='stripe':
            stripe.init(c)
            row=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()
            config=auth._open(c.execute('SELECT secret_key FROM credit_payment_config WHERE id=1').fetchone()[0])
        else:
            paypal.init(c)
            row=c.execute('SELECT * FROM paypal_orders WHERE id=?',(order_id,)).fetchone();config=paypal._keys(c)
        if row is None:raise ValueError('Unknown checkout order')
        initial=dict(row)
    from .checkout_terminal_outcomes import stripe_identity,paypal_identity
    if provider=='stripe':
        if not reference.startswith('cs_') or not config.startswith(('sk_test_','sk_live_')):
            raise ProviderProbeError('Invalid Stripe reference or credentials')
        if client is None:
            with httpx.Client(timeout=15,follow_redirects=False) as owned:
                return recover(provider,order_id,reference,client=owned)
        document=_get(client,'https://api.stripe.com/v1/checkout/sessions/'+reference,{'Authorization':'Bearer '+config})
        stripe_identity(document,{**initial,'session_id':reference})
        if document.get('status') not in ('open','complete','expired') or document.get('payment_status') not in ('paid','unpaid','no_payment_required'):
            raise ProviderProbeError('Invalid Stripe checkout status')
    else:
        if not re.fullmatch(r'[A-Z0-9]{6,64}',reference):raise ValueError('Invalid PayPal order reference')
        if initial['environment']!=config['environment'] or initial['client_fingerprint']!=hashlib.sha256(config['client_id'].encode()).hexdigest():
            raise FenceBlocked('PayPal merchant configuration changed')
        document=paypal._api(config,'GET','/v2/checkout/orders/'+reference)
        paypal_identity(document,{**initial,'provider_order':reference},require_empty=False)
        if document.get('status') not in ('CREATED','SAVED','APPROVED','VOIDED','COMPLETED','PAYER_ACTION_REQUIRED','PENDING_APPROVAL'):
            raise ProviderProbeError('Unknown PayPal checkout status')
    reference_field='session_id' if provider=='stripe' else 'provider_order'
    urls=[document.get('url')] if provider=='stripe' else [item.get('href') for item in document.get('links',[]) if item.get('rel') in ('approve','payer-action')]
    approval=None
    if len(urls)==1 and urls[0]:
        candidate=urlsplit(urls[0]);host='checkout.stripe.com' if provider=='stripe' else ('www.sandbox.paypal.com' if config['environment']=='sandbox' else 'www.paypal.com')
        if candidate.scheme!='https' or candidate.hostname!=host or candidate.username or candidate.password or candidate.port not in (None,443):
            raise ProviderProbeError('Invalid recovered checkout URL')
        approval=urls[0]
    immutable=('user_id','amount_cents','credit_value_micro') if provider=='stripe' else ('user_id','kind','period_start','amount_cents','environment','client_fingerprint')
    normalized={'type':'checkout.reference.recovered','order_id':order_id,'provider_reference':reference,
                'user_id':initial['user_id'],'amount_minor':initial['amount_cents'],'currency':'EUR',
                'merchant_fingerprint':hashlib.sha256((config if provider=='stripe' else config['client_id']).encode()).hexdigest()}
    raw=json.dumps(normalized,sort_keys=True,allow_nan=False).encode();digest=hashlib.sha256(raw).hexdigest();event_id='reference:'+digest
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        if provider=='stripe':
            current=c.execute('SELECT * FROM credit_purchase_orders WHERE id=?',(order_id,)).fetchone()
            fresh=auth._open(c.execute('SELECT secret_key FROM credit_payment_config WHERE id=1').fetchone()[0])
            duplicate=c.execute('SELECT 1 FROM credit_purchase_orders WHERE session_id=? AND id!=?',(reference,order_id)).fetchone()
        else:
            current=c.execute('SELECT * FROM paypal_orders WHERE id=?',(order_id,)).fetchone();fresh=paypal._keys(c)
            duplicate=c.execute('SELECT 1 FROM paypal_orders WHERE provider_order=? AND id!=?',(reference,order_id)).fetchone()
        if fresh!=config or current is None or any(current[k]!=initial[k] for k in immutable):
            raise FenceBlocked('Order or merchant changed during checkout reference recovery')
        if duplicate or current[reference_field] not in (None,reference):raise FenceBlocked('Provider reference already bound to a different order')
        op='checkout:'+provider+':'+order_id
        dispatch=c.execute('SELECT provider,state,attempts,provider_reference FROM regime_payment_outbox WHERE operation_id=?',(op,)).fetchone()
        if dispatch is None or dispatch[0]!=provider or dispatch[2]<1 or dispatch[1] not in ('uncertain','confirmed'):
            raise FenceBlocked('Uncertain attempted checkout creation required')
        from .payment_reconciliation import record_event,mark_applied,bind_object
        from .regime_payment_outbox import reconcile_verified_outcome
        # Retries after a later paid/terminal settlement acknowledge the earlier
        # immutable binding; they do not reopen or re-settle its closed fence.
        old=c.execute("SELECT 1 FROM sqlite_master WHERE name='payment_reconciliation_events'").fetchone()
        prior=c.execute('SELECT digest,state FROM payment_reconciliation_events WHERE provider=? AND event_id=?',(provider,event_id)).fetchone() if old else None
        if prior is not None and tuple(prior)==(digest,'applied') and current[reference_field]==reference and dispatch[1]=='confirmed' and dispatch[3]==reference:
            return {'provider':provider,'order_id':order_id,'reference_confirmed':True,'duplicate':True,'ledger_reconciled':False,'transition_authorized':False}
        if current['status']!='pending' or current['paid_at'] is not None:raise FenceBlocked('Checkout already has a financial outcome')
        from .service_regime import read_regime
        configured=read_regime(auth.data_root()/'service-regime.json')
        active=c.execute('SELECT regime,revision FROM regime_fence_state WHERE singleton=1').fetchone()
        if active is None or (configured.regime.value,configured.revision)!=tuple(active):
            raise FenceBlocked('Checkout recovery regime mirror differs from the active epoch')
        reconcile_verified_outcome(c,op,provider=provider,outcome='confirmed',provider_reference=reference)
        record_event(c,provider,event_id,digest,normalized);bind_object(c,provider,reference,order_id)
        if provider=='stripe':c.execute('UPDATE credit_purchase_orders SET session_id=?,checkout_url=coalesce(?,checkout_url) WHERE id=?',(reference,approval,order_id))
        else:c.execute('UPDATE paypal_orders SET provider_order=?,checkout_url=coalesce(?,checkout_url) WHERE id=?',(reference,approval,order_id))
        mark_applied(c,provider,event_id,order_id)
    return {'provider':provider,'order_id':order_id,'reference_confirmed':True,'duplicate':False,'ledger_reconciled':False,'transition_authorized':False}
