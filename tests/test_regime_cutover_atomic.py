import sqlite3

import pytest

from app.regime_cutover_atomic import commit_reserved_database_cutover
from app.regime_operation_fence import FenceBlocked, initialize, begin_transition


def _db():
    con = sqlite3.connect(':memory:')
    con.execute('BEGIN IMMEDIATE')
    initialize(con)
    con.execute('CREATE TABLE regime_transition_journal (id TEXT PRIMARY KEY,source_regime TEXT,target_regime TEXT,source_revision INTEGER,evidence_sha256 TEXT,status TEXT)')
    begin_transition(con, expected_revision=0, target='COMMERCIAL')
    con.execute("INSERT INTO regime_transition_journal VALUES ('t','NON_COMMERCIAL','COMMERCIAL',0,'digest','reserved')")
    con.commit()
    return con


def test_atomic_sqlite_half_keeps_barrier():
    con = _db()
    con.execute('BEGIN IMMEDIATE')
    result = commit_reserved_database_cutover(con, transition_id='t', expected_revision=0, readiness_check=lambda db: True)
    con.commit()
    assert result['barrier_held']
    assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone() == ('COMMERCIAL', 1, 1)
    assert con.execute('SELECT new_revision FROM regime_cutover_commits').fetchone()[0] == 1


@pytest.mark.parametrize('ready', [False, None, 1, 'yes'])
def test_not_ready_does_not_mutate(ready):
    con = _db()
    con.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        commit_reserved_database_cutover(con, transition_id='t', expected_revision=0, readiness_check=lambda db: ready)
    con.rollback()
    assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone() == ('NON_COMMERCIAL', 0, 1)


def test_stale_epoch_refused():
    con = _db()
    con.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        commit_reserved_database_cutover(con, transition_id='t', expected_revision=1, readiness_check=lambda db: True)


def test_no_transaction_refused():
    con = _db()
    with pytest.raises(FenceBlocked):
        commit_reserved_database_cutover(con, transition_id='t', expected_revision=0, readiness_check=lambda db: True)
