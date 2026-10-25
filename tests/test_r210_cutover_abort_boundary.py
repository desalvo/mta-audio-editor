import sqlite3

import pytest

from app.regime_operation_fence import FenceBlocked, initialize
from app.regime_transition_journal import abort_verified, reserve
from app.regime_cutover_atomic import commit_reserved_database_cutover


def prepared_db():
    con = sqlite3.connect(':memory:')
    con.execute('BEGIN IMMEDIATE')
    initialize(con)
    reserve(con, transition_id='t1', target='COMMERCIAL', expected_revision=0,
            evidence={'ready': True, 'unresolved': []})
    con.commit()
    return con


def test_pre_cutover_abort_remains_possible():
    con = prepared_db()
    con.execute('BEGIN IMMEDIATE')
    assert abort_verified(con, transition_id='t1', expected_revision=0)['aborted']
    con.commit()
    assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone() == ('NON_COMMERCIAL', 0, 0)


def test_committed_cutover_cannot_abort_and_open_barrier():
    con = prepared_db()
    con.execute('BEGIN IMMEDIATE')
    commit_reserved_database_cutover(con, transition_id='t1', expected_revision=0,
                                    readiness_check=lambda _: True)
    con.commit()
    con.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked, match='inconsistent|forward recovery'):
        abort_verified(con, transition_id='t1', expected_revision=1)
    con.rollback()
    assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone() == ('COMMERCIAL', 1, 1)


def test_cutover_replayed_at_old_revision_rejected():
    con = prepared_db()
    con.execute('BEGIN IMMEDIATE')
    commit_reserved_database_cutover(con, transition_id='t1', expected_revision=0,
                                    readiness_check=lambda _: True)
    con.commit()
    con.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        commit_reserved_database_cutover(con, transition_id='t1', expected_revision=0,
                                        readiness_check=lambda _: True)


def test_direct_abort_after_cutover_also_refused():
    from app.regime_transition_journal import abort
    con = prepared_db()
    con.execute('BEGIN IMMEDIATE')
    commit_reserved_database_cutover(con, transition_id='t1', expected_revision=0,
                                    readiness_check=lambda _: True)
    con.commit()
    con.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked, match='forward recovery'):
        abort(con, transition_id='t1')
    con.rollback()
    assert con.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0] == 1
