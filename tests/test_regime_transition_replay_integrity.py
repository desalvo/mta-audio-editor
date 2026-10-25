"""Transition journal replay must never override the durable fence state."""
import sqlite3

import pytest

from app.regime_operation_fence import FenceBlocked, initialize
from app.regime_transition_journal import reserve


def _connection():
    c = sqlite3.connect(':memory:')
    c.execute('BEGIN IMMEDIATE')
    initialize(c)
    c.commit()
    return c


def _reserve(c):
    return reserve(c, transition_id='ticket-1', target='COMMERCIAL',
                   expected_revision=0, evidence={'ready': True, 'unresolved': []})


def test_replay_requires_matching_barrier_state():
    c = _connection()
    c.execute('BEGIN IMMEDIATE')
    assert _reserve(c)['idempotent'] is False
    assert _reserve(c)['idempotent'] is True
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    c.execute('UPDATE regime_fence_state SET transitioning=0 WHERE singleton=1')
    with pytest.raises(FenceBlocked, match='inconsistent'):
        _reserve(c)
    c.rollback()


def test_replay_rejects_revision_drift():
    c = _connection()
    c.execute('BEGIN IMMEDIATE')
    _reserve(c)
    c.commit()
    c.execute('BEGIN IMMEDIATE')
    c.execute('UPDATE regime_fence_state SET revision=revision+1 WHERE singleton=1')
    with pytest.raises(FenceBlocked, match='inconsistent'):
        _reserve(c)
    c.rollback()
