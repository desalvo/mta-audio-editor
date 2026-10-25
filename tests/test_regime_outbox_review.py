import sqlite3
import pytest
from app.regime_operation_fence import initialize, admit, settle, FenceBlocked
from app.regime_payment_outbox import enqueue, mark_attempt_uncertain, confirm
from app.regime_outbox_review import review


def test_missing_schema_is_not_ready():
    c=sqlite3.connect(':memory:')
    with pytest.raises(FenceBlocked): review(c)


def test_uncertain_and_confirmed_open_checkout_both_visible():
    c=sqlite3.connect(':memory:',isolation_level=None)
    initialize(c,initial_regime='COMMERCIAL')
    c.execute('BEGIN IMMEDIATE')
    admit(c,'checkout:stripe:one','checkout',required_regime='COMMERCIAL')
    enqueue(c,provider='stripe',order_id='one',request_key='one')
    c.commit()
    c.execute('BEGIN IMMEDIATE');mark_attempt_uncertain(c,'checkout:stripe:one');c.commit()
    assert review(c)['items'][0]['state']=='uncertain'
    c.execute('BEGIN IMMEDIATE');confirm(c,'checkout:stripe:one',provider_reference='cs_1');c.commit()
    assert review(c)['items'][0]['state']=='confirmed'
    c.execute('BEGIN IMMEDIATE');settle(c,'checkout:stripe:one');c.commit()
    assert review(c)['unresolved_count']==0


def test_review_read_only_and_pagination():
    c=sqlite3.connect(':memory:',isolation_level=None)
    initialize(c,initial_regime='COMMERCIAL')
    c.execute('BEGIN IMMEDIATE')
    for i in range(3):
        admit(c,f'checkout:paypal:{i}','checkout',required_regime='COMMERCIAL')
        enqueue(c,provider='paypal',order_id=str(i),request_key=str(i))
    c.commit()
    before=c.total_changes
    r=review(c,limit=2,offset=1)
    assert len(r['items'])==2 and r['unresolved_count']==3
    assert before==c.total_changes
    for kwargs in ({'limit':0},{'limit':501},{'offset':-1},{'limit':True}):
        with pytest.raises(ValueError):review(c,**kwargs)
