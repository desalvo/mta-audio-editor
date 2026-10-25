import sqlite3
import pytest
from app.regime_financial_evidence import record_observation, audit_observations
from app.regime_operation_fence import FenceBlocked


def make_db():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE regime_fence_operations (operation_id TEXT PRIMARY KEY, kind TEXT, regime TEXT)')
    db.execute('CREATE TABLE regime_payment_outbox (operation_id TEXT PRIMARY KEY, provider TEXT, state TEXT, provider_reference TEXT)')
    db.execute("INSERT INTO regime_fence_operations VALUES('checkout:stripe:a','checkout','COMMERCIAL')")
    db.execute("INSERT INTO regime_payment_outbox VALUES('checkout:stripe:a','stripe','confirmed','cs_test_a')")
    db.commit()
    return db


def evidence():
    return dict(provider='stripe',reference='cs_test_a',amount_minor=200,currency='EUR',
                remote_payment_observed=True,local_ledger_reconciled=False,
                authorizes_entitlement=False, authorizes_cutover=False)


def test_journal_idempotence_and_never_settles():
    db=make_db()
    db.execute("BEGIN")
    with db:
        assert record_observation(db,'checkout:stripe:a',evidence(),evidence_id='event1')['created']
        assert not record_observation(db,'checkout:stripe:a',evidence(),evidence_id='event1')['created']
    assert audit_observations(db)['verified']
    assert not audit_observations(db)['transition_safe']


def test_reject_missing_transaction():
    db=make_db()
    with pytest.raises(FenceBlocked):record_observation(db,'checkout:stripe:a',evidence(),evidence_id='evt')

@pytest.mark.parametrize('mutation', [
    {'reference':'cs_test_other'}, {'provider':'paypal'}, {'amount_minor':True},
    {'remote_payment_observed':False}, {'authorizes_entitlement':True},
    {'local_ledger_reconciled':True}, {'authorizes_cutover':True},
])
def test_bad_evidence_rejected(mutation):
    db=make_db(); ev=evidence();ev.update(mutation)
    with db, pytest.raises(FenceBlocked):record_observation(db,'checkout:stripe:a',ev,evidence_id='evt')


def test_conflicting_replay_and_tamper_detection():
    db=make_db()
    db.execute("BEGIN")
    with db:record_observation(db,'checkout:stripe:a',evidence(),evidence_id='evt')
    db.execute("BEGIN")
    with db, pytest.raises(FenceBlocked):
        ev=evidence();ev['amount_minor']=201
        record_observation(db,'checkout:stripe:a',ev,evidence_id='evt')
    db.execute("UPDATE regime_financial_evidence SET observed_json='{}'")
    assert audit_observations(db)['inconsistencies']['tampered']==1
