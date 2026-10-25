"""Offline exclusive finalization regression (never enables the public API)."""
import json
import sqlite3

import pytest

from app.regime_maintenance import finalize_cutover_exclusively
from app.regime_operation_fence import FenceBlocked, initialize
from app.service_regime import Regime, RegimeState


def setup(tmp_path):
    db = tmp_path / 'regime.sqlite'
    conn = sqlite3.connect(db)
    conn.execute('BEGIN IMMEDIATE')
    initialize(conn)
    conn.execute("UPDATE regime_fence_state SET regime='COMMERCIAL',revision=1,transitioning=1")
    conn.execute('CREATE TABLE regime_cutover_commits (transition_id TEXT PRIMARY KEY,source TEXT,target TEXT,previous_revision INTEGER,new_revision INTEGER)')
    conn.execute("INSERT INTO regime_cutover_commits VALUES('x','NON_COMMERCIAL','COMMERCIAL',0,1)")
    conn.commit()
    conn.close()
    mirror = tmp_path / 'regime.json'
    mirror.write_text(json.dumps(RegimeState(Regime.COMMERCIAL, 1).as_dict()))
    lock = tmp_path / 'maintenance.lock'
    lock.touch(mode=0o600)
    return db, mirror, lock


def held(db):
    with sqlite3.connect(db) as c:
        return c.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0]


def test_finalization_requires_authoritative_check(tmp_path):
    db, mirror, lock = setup(tmp_path)
    with pytest.raises(FenceBlocked):
        finalize_cutover_exclusively(db, mirror, 'x', lock, lambda _: False)
    assert held(db) == 1


def test_caller_true_cannot_bypass_incomplete_provider_coverage(tmp_path):
    db, mirror, lock = setup(tmp_path)
    with pytest.raises(FenceBlocked, match='not authoritatively verified'):
        finalize_cutover_exclusively(db, mirror, 'x', lock, lambda _: True)
    assert held(db) == 1
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE name='regime_cutover_finalizations'").fetchone() is None


def test_missing_lock_fails_closed(tmp_path):
    db, mirror, lock = setup(tmp_path)
    lock.unlink()
    with pytest.raises(FenceBlocked):
        finalize_cutover_exclusively(db, mirror, 'x', lock, lambda _: True)
    assert held(db) == 1


def test_stale_mirror_fails_closed(tmp_path):
    db, mirror, lock = setup(tmp_path)
    mirror.write_text(json.dumps(RegimeState(Regime.NON_COMMERCIAL, 0).as_dict()))
    with pytest.raises(FenceBlocked):
        finalize_cutover_exclusively(db, mirror, 'x', lock, lambda _: True)
    assert held(db) == 1
