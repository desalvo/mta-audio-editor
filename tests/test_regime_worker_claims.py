import sqlite3
import pytest
from app.regime_operation_fence import initialize, admit, settle, begin_transition, FenceBlocked
from app.regime_worker_claims import claim, heartbeat, finish, inspect_claims


def db():
    c=sqlite3.connect(':memory:', isolation_level=None)
    c.execute('BEGIN IMMEDIATE')
    initialize(c)
    admit(c,'job:ledger:abc','job')
    c.commit()
    return c


def test_cross_connection_ownership_and_idempotency(tmp_path):
    path=tmp_path/'worker.sqlite'
    c=sqlite3.connect(path, isolation_level=None)
    c.execute('BEGIN IMMEDIATE');initialize(c);admit(c,'job:ledger:abc','job');c.commit()
    other=sqlite3.connect(path, isolation_level=None)
    c.execute('BEGIN IMMEDIATE')
    assert claim(c,'abc',worker_id='node1',token='secret')['claimed']
    c.commit()
    other.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        claim(other,'abc',worker_id='node2',token='different')
    assert not claim(other,'abc',worker_id='node1',token='secret')['claimed']
    heartbeat(other,'job:ledger:abc',worker_id='node1',token='secret')
    with pytest.raises(FenceBlocked):
        finish(other,'job:ledger:abc',worker_id='node2',token='different')
    finish(other,'job:ledger:abc',worker_id='node1',token='secret')
    finish(other,'job:ledger:abc',worker_id='node1',token='secret')
    assert inspect_claims(other)=={'verified':True,'running':0,'finished':1}
    with pytest.raises(FenceBlocked):
        claim(other,'abc',worker_id='node2',token='new')
    other.commit()


def test_missing_schema_and_missing_job_fail_closed():
    c=db()
    assert inspect_claims(c)['verified'] is False
    c.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):claim(c,'missing',worker_id='w',token='t')
    claim(c,'abc',worker_id='w',token='t')
    assert inspect_claims(c)['running']==1
    with pytest.raises(FenceBlocked):begin_transition(c,expected_revision=0,target='COMMERCIAL')
    finish(c,'job:ledger:abc',worker_id='w',token='t')
    settle(c,'job:ledger:abc')
    with pytest.raises(FenceBlocked):heartbeat(c,'job:ledger:abc',worker_id='w',token='t')
    c.rollback()


def test_claim_requires_transaction_and_prohibits_transition():
    c=db()
    with pytest.raises(FenceBlocked):claim(c,'abc',worker_id='w',token='t')
    c.execute('BEGIN IMMEDIATE')
    c.execute('UPDATE regime_fence_state SET transitioning=1')
    with pytest.raises(FenceBlocked):claim(c,'abc',worker_id='w',token='t')
    c.rollback()

@pytest.mark.parametrize('worker,token', [('','x'),('w',''),(' ','x'),('w',None)])
def test_bad_worker_identity(worker,token):
    c=db();c.execute('BEGIN IMMEDIATE')
    with pytest.raises(ValueError):claim(c,'abc',worker_id=worker,token=token)
    c.rollback()


def test_real_auth_row_factory_claim_and_finish_retries_are_idempotent():
    c=db();c.row_factory=sqlite3.Row;c.execute('BEGIN IMMEDIATE')
    assert claim(c,'abc',worker_id='w',token='t')['claimed']
    assert not claim(c,'abc',worker_id='w',token='t')['claimed']
    finish(c,'job:ledger:abc',worker_id='w',token='t')
    finish(c,'job:ledger:abc',worker_id='w',token='t')
    assert inspect_claims(c)['finished']==1
