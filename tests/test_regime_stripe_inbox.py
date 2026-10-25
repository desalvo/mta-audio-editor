import hashlib
import sqlite3

import pytest

from app.regime_operation_fence import FenceBlocked
from app.regime_stripe_inbox import mark_applied, prepare


def db(regime='COMMERCIAL'):
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE regime_fence_operations(operation_id TEXT PRIMARY KEY,kind TEXT,regime TEXT,revision INTEGER,status TEXT)')
    c.execute('INSERT INTO regime_fence_operations VALUES(?,?,?,?,?)', ('checkout:stripe:o1','checkout',regime,0,'open'))
    c.commit()
    return c


def test_stripe_inbox_atomic_commit_and_retry():
    c=db(); digest=hashlib.sha256(b'signed payload').hexdigest()
    c.execute('BEGIN IMMEDIATE')
    assert prepare(c,event_id='evt1',order_id='o1',payload_sha256=digest)
    mark_applied(c,event_id='evt1',order_id='o1',payload_sha256=digest)
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    assert prepare(c,event_id='evt1',order_id='o1',payload_sha256=digest)
    with pytest.raises(FenceBlocked,match='conflicting payload'):
        prepare(c,event_id='evt1',order_id='o1',payload_sha256='a'*64)
    c.rollback()


def test_stripe_inbox_rollback_and_bad_epoch():
    c=db(); digest='b'*64
    c.execute('BEGIN IMMEDIATE')
    assert prepare(c,event_id='evt2',order_id='o1',payload_sha256=digest)
    mark_applied(c,event_id='evt2',order_id='o1',payload_sha256=digest)
    c.rollback()
    c.execute('BEGIN IMMEDIATE')
    assert prepare(c,event_id='evt2',order_id='o1',payload_sha256=digest)
    c.rollback()
    d=db('NON_COMMERCIAL');d.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked,match='incompatible'):
        prepare(d,event_id='evt2',order_id='o1',payload_sha256=digest)
    d.rollback()


def test_legacy_unenrolled_is_not_synthesized():
    c=db();c.execute('BEGIN IMMEDIATE')
    assert prepare(c,event_id='legacy',order_id='unknown',payload_sha256='c'*64) is False
    assert c.execute("SELECT name FROM sqlite_master WHERE name='regime_provider_inbox'").fetchone() is None
    c.rollback()
