import sqlite3

import pytest

from app.regime_cutover_finalize import finalize_cutover
from app.regime_operation_fence import FenceBlocked, initialize
from app.service_regime import Regime, RegimeState


def prepared(tmp_path):
    conn = sqlite3.connect(':memory:')
    conn.execute('BEGIN IMMEDIATE')
    initialize(conn)
    conn.execute('UPDATE regime_fence_state SET regime=?,revision=1,transitioning=1', ('COMMERCIAL',))
    conn.execute('CREATE TABLE regime_cutover_commits (transition_id TEXT PRIMARY KEY,source TEXT,target TEXT,previous_revision INTEGER,new_revision INTEGER)')
    conn.execute("INSERT INTO regime_cutover_commits VALUES('x','NON_COMMERCIAL','COMMERCIAL',0,1)")
    conn.commit()
    path = tmp_path/'regime.json'
    import json
    path.write_text(json.dumps(RegimeState(Regime('COMMERCIAL'), 1).as_dict()))
    return conn,path


def test_requires_authoritative_positive_check(tmp_path):
    conn,path=prepared(tmp_path)
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        finalize_cutover(conn,mirror_path=path,transition_id='x',readiness_check=lambda _: False)
    conn.rollback()
    assert conn.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0] == 1


def test_success_atomic_and_rollback(tmp_path):
    conn,path=prepared(tmp_path)
    conn.execute('BEGIN IMMEDIATE')
    result=finalize_cutover(conn,mirror_path=path,transition_id='x',readiness_check=lambda _: True)
    assert result['barrier_held'] is False
    conn.rollback()
    assert conn.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0] == 1
    conn.execute('BEGIN IMMEDIATE')
    finalize_cutover(conn,mirror_path=path,transition_id='x',readiness_check=lambda _: True)
    conn.commit()
    assert conn.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0] == 0


def test_rejects_stale_mirror(tmp_path):
    conn,path=prepared(tmp_path)
    import json
    path.write_text(json.dumps(RegimeState(Regime('NON_COMMERCIAL'), 0).as_dict()))
    conn.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        finalize_cutover(conn,mirror_path=path,transition_id='x',readiness_check=lambda _: True)
    conn.rollback()


def test_requires_transaction(tmp_path):
    conn,path=prepared(tmp_path)
    with pytest.raises(FenceBlocked):
        finalize_cutover(conn,mirror_path=path,transition_id='x',readiness_check=lambda _: True)
