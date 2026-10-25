import json
import sqlite3

import pytest

from app.regime_cutover_mirror import inspect_mirror, reconcile_mirror
from app.regime_operation_fence import FenceBlocked, initialize


def setup_db():
    db = sqlite3.connect(':memory:')
    db.execute('BEGIN IMMEDIATE')
    initialize(db)
    db.execute("UPDATE regime_fence_state SET regime='COMMERCIAL',revision=1,transitioning=1")
    db.execute('CREATE TABLE regime_cutover_commits (transition_id TEXT PRIMARY KEY,source TEXT,target TEXT,previous_revision INTEGER,new_revision INTEGER)')
    db.execute("INSERT INTO regime_cutover_commits VALUES ('cut','NON_COMMERCIAL','COMMERCIAL',0,1)")
    db.commit()
    return db


def write(path, regime='NON_COMMERCIAL', revision=0):
    path.write_text(json.dumps({'regime':regime,'revision':revision}))


def test_recovers_only_mirror_and_keeps_barrier(tmp_path):
    db = setup_db()
    path = tmp_path / 'service-regime.json'
    write(path)
    db.execute('BEGIN IMMEDIATE')
    result = reconcile_mirror(db, path, 'cut')
    db.commit()
    assert result['mirror_matches'] and not result['activation_permitted']
    assert path.stat().st_mode & 0o777 == 0o600
    assert db.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0] == 1
    db.execute('BEGIN IMMEDIATE')
    assert reconcile_mirror(db, path, 'cut')['mirror_matches']


def test_unexpected_epoch_never_overwritten(tmp_path):
    db = setup_db()
    path = tmp_path / 'service-regime.json'
    write(path,'COMMERCIAL', 9)
    db.execute('BEGIN IMMEDIATE')
    with pytest.raises(FenceBlocked):
        reconcile_mirror(db,path,'cut')
    assert json.loads(path.read_text())['revision'] == 9


def test_symlink_rejected(tmp_path):
    db = setup_db()
    real = tmp_path / 'real.json'
    write(real)
    link = tmp_path / 'service-regime.json'
    link.symlink_to(real)
    with pytest.raises(ValueError):
        inspect_mirror(db,link,'cut')


def test_closed_barrier_rejected(tmp_path):
    db=setup_db()
    path=tmp_path/'service-regime.json'
    write(path)
    db.execute('UPDATE regime_fence_state SET transitioning=0')
    with pytest.raises(FenceBlocked):
        inspect_mirror(db,path,'cut')


def test_requires_caller_transaction(tmp_path):
    db=setup_db()
    path=tmp_path/'service-regime.json'
    write(path)
    with pytest.raises(FenceBlocked):
        reconcile_mirror(db,path,'cut')
