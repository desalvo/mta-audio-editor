"""Security regression for the opt-in planning journal (never inference/billing)."""


import pytest
from app.ai_planning_sqlite import SQLitePlanningQueue


def test_rejects_symlink_ancestor(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    (tmp_path / 'alias').symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match='ancestor'):
        SQLitePlanningQueue(tmp_path / 'alias' / 'db.sqlite')


def test_rejects_symlink_sidecar_at_creation(tmp_path):
    db = tmp_path / 'db.sqlite'
    target = tmp_path / 'target'
    target.write_text('never edit')
    (tmp_path / 'db.sqlite-journal').symlink_to(target)
    with pytest.raises(ValueError, match='sidecar'):
        SQLitePlanningQueue(db)
    assert target.read_text() == 'never edit'


def test_rejects_sidecar_swapped_after_startup(tmp_path):
    db = tmp_path / 'db.sqlite'
    q = SQLitePlanningQueue(db)
    secret = tmp_path / 'other'
    secret.write_text('secret')
    (tmp_path / 'db.sqlite-wal').symlink_to(secret)
    with pytest.raises(ValueError, match='sidecar'):
        q.submit('p', 'owner', 'remix', {})
    assert secret.read_text() == 'secret'


def test_rejects_database_swapped_after_startup(tmp_path):
    db = tmp_path / 'db.sqlite'
    q = SQLitePlanningQueue(db)
    db.unlink()
    target = tmp_path / 'target.sqlite'
    target.write_text('not a database')
    db.symlink_to(target)
    with pytest.raises(ValueError, match='regular file'):
        q.list('p', 'owner')
    assert target.read_text() == 'not a database'
