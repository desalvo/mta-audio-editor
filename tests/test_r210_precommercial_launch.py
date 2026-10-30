"""Configured first commercial launch, zero monetary history and NC continuity."""
import sqlite3

import pytest
from app import auth,paypal_payments as paypal,credit_purchases as stripe
from app import regime_admin_cutover as cutover,commercial_launch
from app.regime_balance_continuity import snapshot
from app.regime_operation_fence import FenceBlocked
from test_r210_admin_cutover_e2e import ready as ready,account as account,begin,BASE,HEADERS  # noqa:F401


def prepare(ready):
    client,uid,admin=ready
    body=begin(client)
    assert client.post(BASE,headers=HEADERS,json=body).status_code==200
    paypal.settings({'enabled':True,'environment':'sandbox','client_id':'prepared-client',
        'client_secret':'prepared-secret','webhook_id':'prepared-webhook'})
    stripe.settings({'secret_key':'sk_test_prepared','webhook_secret':'whsec_prepared'})
    with auth.db() as c:
        c.execute('UPDATE resource_plans SET price_micro=5000000')
    return client,uid,admin


def test_prepared_providers_and_prices_are_not_money_and_actual_api_preserves_every_row(ready):
    client,uid,admin=prepare(ready)
    statement=client.post('/api/admin/service-regime/noncommercial-statements',headers=HEADERS,
        json={'start':1,'end':2,'documented_cost_cents':0,'operator_cost_exclusion_confirmed':True})
    assert statement.status_code==200,statement.text
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');before=snapshot(c)
    review=client.get(BASE+'/preflight?target=COMMERCIAL').json()
    assert review['maintenance_eligibility']=='verified_precommercial_profile'
    assert review['financial_model']['legacy_migration_supported'] is False
    assert review['preview']['readiness']['provider_history']=='absent_in_verified_schemas'
    assert 'prepared-secret' not in str(review) and 'sk_test_prepared' not in str(review)
    body=begin(client,target='COMMERCIAL',identifier='prepared-first-commercial')
    response=client.post(BASE,headers=HEADERS,json=body)
    assert response.status_code==200,response.text
    assert response.json()['phase']=='finalized'
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');assert snapshot(c)==before
    assert client.post(BASE,headers=HEADERS,json=body).status_code==200
    back=begin(client,target='NON_COMMERCIAL',identifier='prepared-return-before-checkout')
    assert client.post(BASE,headers=HEADERS,json=back).status_code==200
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');assert snapshot(c)==before


@pytest.mark.parametrize('table,sql',[
    ('paypal_events',"INSERT INTO paypal_events VALUES('unexpected',1)"),
    ('credit_payment_events',"INSERT INTO credit_payment_events VALUES('unexpected',1)"),
    ('paypal_refunds',None),('operator_refunds',None),('unknown',None)])
def test_any_unexpected_money_or_unknown_schema_blocks_without_erasing_it(ready,table,sql):
    client,_,_=prepare(ready)
    if sql:
        with auth.db() as c:c.execute(sql)
    elif table=='paypal_refunds':
        with auth.db() as c:
            c.execute('DROP TABLE paypal_refunds')
            c.execute('CREATE TABLE paypal_refunds(unrecognized_amount INTEGER)')
            c.execute('INSERT INTO paypal_refunds VALUES(7)')
    elif table=='operator_refunds':
        with auth.db() as c:
            c.execute('CREATE TABLE operator_refunds(unrecognized_amount INTEGER)')
            c.execute('INSERT INTO operator_refunds VALUES(7)')
    else:
        # Unknown financial storage cannot be inferred empty or migrated.
        with auth.db() as c:c.execute('CREATE TABLE unexpected_legacy_money(amount INTEGER)');c.execute('INSERT INTO unexpected_legacy_money VALUES(7)')
    response=client.get(BASE+'/preview?target=COMMERCIAL')
    assert response.status_code==409
    assert client.get('/api/service-regime').json()['regime']=='NON_COMMERCIAL'
    with auth.db() as c:
        queries={'paypal_events':'SELECT count(*) FROM paypal_events',
                 'credit_payment_events':'SELECT count(*) FROM credit_payment_events',
                 'paypal_refunds':'SELECT count(*) FROM paypal_refunds',
                 'operator_refunds':'SELECT count(*) FROM operator_refunds',
                 'unknown':'SELECT count(*) FROM unexpected_legacy_money'}
        query=queries[table]
        assert c.execute(query).fetchone()[0]==1


def test_changed_prepared_merchant_invalidates_the_actual_preview(ready):
    client,_,_=prepare(ready)
    body=begin(client,target='COMMERCIAL',identifier='stale-prepared-provider')
    paypal.settings({'client_secret':'changed-prepared-secret'})
    assert client.post(BASE,headers=HEADERS,json=body).status_code==409
    assert client.get('/api/service-regime').json()['regime']=='NON_COMMERCIAL'


def test_commercial_start_marker_is_transactional_immutable_and_not_personal(ready):
    client,_,_=ready
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');commercial_launch.mark_started(c);c.rollback()
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');commercial_launch.require_not_started(c)
        commercial_launch.mark_started(c)
    with auth.db() as c:
        assert [r[1] for r in c.execute('PRAGMA table_info(regime_commercial_origin)')]==['singleton','revision']
        with pytest.raises(sqlite3.IntegrityError):c.execute('DELETE FROM regime_commercial_origin')
        with pytest.raises(sqlite3.IntegrityError):c.execute('UPDATE regime_commercial_origin SET revision=9')
        with pytest.raises(FenceBlocked):commercial_launch.require_not_started(c)
    assert client.get(BASE+'/preview?target=NON_COMMERCIAL').status_code==409


def test_original_admitted_checkout_marks_start_before_external_dispatch(ready,monkeypatch):
    from app import resource_accounts
    client,uid,_=ready
    stripe.settings({'secret_key':'sk_test_prepared','webhook_secret':'whsec_prepared'})
    def lost(*args):raise ValueError('Original provider response lost')
    monkeypatch.setattr(stripe,'_stripe',lost)
    with pytest.raises(ValueError):stripe.checkout(uid,500,'first-live-dispatch')
    with auth.db() as c:
        assert c.execute('SELECT revision FROM regime_commercial_origin').fetchone()[0]==0
        assert c.execute('SELECT state FROM regime_payment_outbox').fetchone()[0]=='uncertain'
    assert client.get(BASE+'/preview?target=NON_COMMERCIAL').status_code==409
    assert resource_accounts.state(uid)['credits_micro']>=0


def test_initial_activation_crash_recovery_with_prepared_credentials_is_forward_only(ready,monkeypatch):
    client,_,_=prepare(ready)
    body=begin(client,target='COMMERCIAL',identifier='initial-activation-recovery')
    real=cutover.reconcile_mirror
    def crash(*args):raise OSError('interrupted mirror replacement')
    monkeypatch.setattr(cutover,'reconcile_mirror',crash)
    assert client.post(BASE,headers=HEADERS,json=body).status_code==503
    assert client.get(BASE+'/'+body['request_id']).json()['barrier_held']
    monkeypatch.setattr(cutover,'reconcile_mirror',real)
    result=client.post(BASE+'/'+body['request_id']+'/recover',headers=HEADERS,
        json={'expected_revision':2,'confirm':True})
    assert result.status_code==200,result.text
    assert client.post(BASE,headers=HEADERS,json=body).status_code==200
    assert client.get('/api/service-regime').json()['regime']=='COMMERCIAL'


@pytest.mark.parametrize('damage',['schema','trigger'])
def test_partial_origin_marker_schema_is_not_repaired_as_unused_history(ready,damage):
    client,_,_=ready
    with auth.db() as c:
        if damage=='schema':c.execute('CREATE TABLE regime_commercial_origin(unrelated TEXT)')
        else:
            c.execute('BEGIN IMMEDIATE');commercial_launch.mark_started(c)
            c.execute('DROP TRIGGER regime_commercial_origin_no_delete')
    assert client.get(BASE+'/preview?target=NON_COMMERCIAL').status_code==409


def test_ui_explains_initial_activation_and_post_checkout_limit_in_both_languages():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'app/static/regime_cutover_panel.js').read_text()
    assert 'Prepared credentials alone do not block activation' in source
    assert 'Le sole credenziali configurate non bloccano' in source
    assert 'switching requires a separate financial workflow' in source
    assert 'nessuna migrazione legacy è prevista' in source
