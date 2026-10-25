import sqlite3
import pytest
from app.regime_provider_reconcile_service import observe_and_journal
from app.regime_financial_evidence import audit_observations
from app.regime_operation_fence import FenceBlocked


def db_fixture():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE regime_fence_operations (operation_id TEXT PRIMARY KEY,kind TEXT,regime TEXT)')
    db.execute('CREATE TABLE regime_payment_outbox (operation_id TEXT PRIMARY KEY,provider TEXT,state TEXT,provider_reference TEXT)')
    db.execute("INSERT INTO regime_fence_operations VALUES ('checkout:stripe:a','checkout','COMMERCIAL')")
    db.execute("INSERT INTO regime_payment_outbox VALUES ('checkout:stripe:a','stripe','confirmed','cs_test_a')")
    db.commit()
    return db


def observed(ref, amount, currency):
    return {'provider':'stripe','reference':ref,'amount_minor':amount,'currency':currency,
            'remote_payment_observed':True,'local_ledger_reconciled':False,
            'authorizes_entitlement':False,'authorizes_cutover':False}


def call(db, verifier=observed, evidence_id='obs1'):
    return observe_and_journal(db,operation_id='checkout:stripe:a',provider='stripe',
       provider_reference='cs_test_a',amount_minor=200,currency='EUR',
       evidence_id=evidence_id,credentials={},client=None,verifier=verifier)


def test_authenticated_handoff_journals_idempotently_without_entitlements():
    db=db_fixture()
    assert call(db)['created'] is True
    assert call(db)['created'] is False
    assert call(db)['settlement_authorized'] is False
    assert audit_observations(db)['verified']
    assert db.execute('SELECT count(*) FROM regime_financial_evidence').fetchone()[0]==1


def test_changed_checkout_during_remote_lookup_rolls_back():
    db=db_fixture()
    def changed(ref, amount, currency):
        db.execute("UPDATE regime_payment_outbox SET provider_reference='cs_other'")
        db.commit()
        return observed(ref,amount,currency)
    with pytest.raises(FenceBlocked,match='changed'):
        call(db,changed)
    assert not db.in_transaction
    assert db.execute("SELECT name FROM sqlite_master WHERE name='regime_financial_evidence'").fetchone() is None

@pytest.mark.parametrize('change',[
    {'amount_minor':201},{'authorizes_entitlement':True},{'currency':'USD'},
    {'local_ledger_reconciled':True},{'remote_payment_observed':False},
])
def test_untrusted_provider_response_rejected(change):
    db=db_fixture()
    def tampered(ref, amount, currency):
        evidence=observed(ref,amount,currency)
        evidence.update(change)
        return evidence
    with pytest.raises(FenceBlocked):call(db,tampered)
    assert not db.in_transaction


def test_unconfirmed_checkout_rejected_before_network():
    db=db_fixture()
    db.execute("UPDATE regime_payment_outbox SET state='uncertain'")
    db.commit()
    with pytest.raises(FenceBlocked):call(db,lambda *_:pytest.fail('network called'))


def test_preexisting_transaction_rejected():
    db=db_fixture();db.execute('BEGIN')
    with pytest.raises(FenceBlocked):call(db)
    db.rollback()
