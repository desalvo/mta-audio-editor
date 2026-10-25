import sqlite3
import pytest
from app.regime_operation_fence import FenceBlocked, initialize, admit, inspect
from app.regime_transition_journal import reserve, abort_verified, inspect_reservations


def connect(path):
    return sqlite3.connect(path, isolation_level=None)


def test_recover_after_restart_and_preserve_epoch(tmp_path):
    p = tmp_path / 'db'
    with connect(p) as db:
        initialize(db)
        db.execute('BEGIN IMMEDIATE')
        reserve(db, transition_id='transition-1', target='COMMERCIAL', expected_revision=0,
                evidence={'ready': True, 'unresolved': []})
        db.commit()
    with connect(p) as db:
        assert inspect_reservations(db)['integrity_verified']
        db.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):
            abort_verified(db, transition_id='transition-1', expected_revision=1)
        assert inspect(db)['transitioning']
        assert abort_verified(db, transition_id='transition-1', expected_revision=0)['aborted']
        db.commit()
    with connect(p) as db:
        assert not inspect_reservations(db)['transitioning']
        assert inspect(db)['regime'] == 'NON_COMMERCIAL'
        db.execute('BEGIN IMMEDIATE')
        admit(db, 'job:allowed', 'job')
        db.commit()


def test_recovery_identity_conflict_rolls_back(tmp_path):
    with connect(tmp_path / 'db') as db:
        initialize(db)
        db.execute('BEGIN IMMEDIATE')
        reserve(db, transition_id='good', target='COMMERCIAL', expected_revision=0,
                evidence={'ready': True, 'unresolved': []})
        db.commit()
        db.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):
            abort_verified(db, transition_id='other', expected_revision=0)
        db.rollback()
        assert inspect(db)['transitioning']


def test_inconsistent_or_missing_journal_does_not_unlock(tmp_path):
    with connect(tmp_path / 'db') as db:
        initialize(db)
        db.execute('BEGIN IMMEDIATE')
        reserve(db, transition_id='one', target='COMMERCIAL', expected_revision=0,
                evidence={'ready': True, 'unresolved': []})
        db.commit()
        db.execute('DELETE FROM regime_transition_journal WHERE id=?', ('one',))
        assert not inspect_reservations(db)['integrity_verified']
        db.execute('BEGIN IMMEDIATE')
        with pytest.raises(FenceBlocked):
            abort_verified(db, transition_id='one', expected_revision=0)
        db.rollback()
        assert inspect(db)['transitioning']
