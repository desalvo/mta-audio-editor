import json
import sqlite3

import pytest

from app.regime_cutover_recovery import recover_committed_mirror
from app.regime_operation_fence import FenceBlocked, initialize


def prepared(tmp_path):
    connection = sqlite3.connect(':memory:')
    connection.execute('BEGIN IMMEDIATE')
    initialize(connection)
    connection.execute("UPDATE regime_fence_state SET regime='COMMERCIAL',revision=1,transitioning=1")
    connection.execute('CREATE TABLE regime_cutover_commits (transition_id TEXT PRIMARY KEY,source TEXT,target TEXT,previous_revision INTEGER,new_revision INTEGER)')
    connection.execute("INSERT INTO regime_cutover_commits VALUES ('x','NON_COMMERCIAL','COMMERCIAL',0,1)")
    connection.commit()
    mirror = tmp_path / 'regime.json'
    mirror.write_text(json.dumps({'regime': 'NON_COMMERCIAL', 'revision': 0}))
    return connection, mirror


def test_recovers_without_activating(tmp_path):
    db, mirror = prepared(tmp_path)
    db.execute('BEGIN IMMEDIATE')
    result = recover_committed_mirror(db, mirror_path=mirror, transition_id='x')
    db.commit()
    assert result['mirror_matches'] and result['barrier_held']
    assert result['activation_permitted'] is False
    assert json.loads(mirror.read_text())['revision'] == 1
    assert db.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0] == 1


def test_retry_is_idempotent(tmp_path):
    db, mirror = prepared(tmp_path)
    for _ in range(2):
        db.execute('BEGIN IMMEDIATE')
        assert recover_committed_mirror(db, mirror_path=mirror, transition_id='x')['barrier_held']
        db.commit()


def test_open_operations_block_mirror_recovery(tmp_path):
    db, mirror = prepared(tmp_path)
    db.execute('BEGIN IMMEDIATE')
    db.execute("INSERT INTO regime_fence_operations VALUES ('job:1','job','NON_COMMERCIAL',0,'open')")
    with pytest.raises(FenceBlocked, match='Open operations'):
        recover_committed_mirror(db, mirror_path=mirror, transition_id='x')
    db.rollback()
    assert json.loads(mirror.read_text())['revision'] == 0


def test_requires_transaction(tmp_path):
    db, mirror = prepared(tmp_path)
    with pytest.raises(FenceBlocked, match='BEGIN IMMEDIATE'):
        recover_committed_mirror(db, mirror_path=mirror, transition_id='x')


def test_wrong_epoch_rejected(tmp_path):
    db, mirror = prepared(tmp_path)
    mirror.write_text(json.dumps({'regime':'COMMERCIAL','revision':42}))
    db.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        recover_committed_mirror(db, mirror_path=mirror, transition_id='x')
    db.rollback()
