"""First-admin creation is atomic across independent SQLite connections."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

from app import auth


@pytest.fixture
def empty_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'auth')
    monkeypatch.setenv('MTA_ADMIN_USERNAME', 'admin')
    monkeypatch.setenv('MTA_ADMIN_EMAIL', 'admin@example.test')
    monkeypatch.delenv('MTA_ADMIN_PASSWORD', raising=False)
    auth.init_auth_db()
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', 'administrator-password')


@pytest.mark.parametrize('entry', ['_bootstrap_admin', 'init_auth_db'])
@pytest.mark.parametrize('workers', [2, 8])
def test_concurrent_first_admin_has_one_identity(empty_auth, monkeypatch, entry, workers):
    start = threading.Barrier(workers)
    original_hash = auth._password_hash_unchecked

    def slow_hash(password):
        # Widen the SELECT/INSERT window that caused the CI race.
        time.sleep(.05)
        return original_hash(password)

    monkeypatch.setattr(auth, '_password_hash_unchecked', slow_hash)

    def initialize():
        start.wait(timeout=10)
        getattr(auth, entry)()

    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(initialize) for _ in range(workers)]
        for future in futures:
            future.result(timeout=20)
    with auth.db() as con:
        rows = con.execute('SELECT * FROM users').fetchall()
    assert len(rows) == 1
    assert rows[0]['username'] == 'admin' and rows[0]['email'] == 'admin@example.test'
    assert rows[0]['role'] == 'admin' and rows[0]['active'] == rows[0]['email_confirmed'] == 1
    assert auth._verify_password('administrator-password', rows[0]['password_hash'])


def test_empty_check_is_inside_write_transaction(empty_auth, monkeypatch):
    original_db = auth.db
    observations = []

    class Connection:
        def __init__(self, con):
            self.con = con

        def execute(self, sql, *args):
            if sql == 'SELECT COUNT(*) FROM users':
                observations.append(self.con.in_transaction)
            return self.con.execute(sql, *args)

    @contextmanager
    def observed_db():
        with original_db() as con:
            yield Connection(con)

    monkeypatch.setattr(auth, 'db', observed_db)
    auth._bootstrap_admin()
    assert observations == [True]


def test_first_admin_is_atomic_across_processes(empty_auth, tmp_path):
    program = r'''
from pathlib import Path
import sys,time
from app import auth
auth.DATA_ROOT=Path(sys.argv[1])
ready=Path(sys.argv[2]);go=Path(sys.argv[3])
original=auth._password_hash_unchecked
def slow_hash(password):
    time.sleep(.05)
    return original(password)
auth._password_hash_unchecked=slow_hash
ready.touch()
deadline=time.monotonic()+15
while not go.exists():
    if time.monotonic()>deadline:raise TimeoutError('Bootstrap start signal missing')
    time.sleep(.01)
auth._bootstrap_admin()
'''
    ready = [tmp_path / f'ready-{i}' for i in range(4)]
    go = tmp_path / 'go'
    children = []
    try:
        for marker in ready:
            children.append(subprocess.Popen(
                [sys.executable, '-c', program, str(auth.DATA_ROOT), str(marker), str(go)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        deadline = time.monotonic() + 15
        while not all(marker.exists() for marker in ready):
            assert time.monotonic() < deadline, 'Bootstrap children failed to become ready'
            time.sleep(.01)
        go.touch()
        for child in children:
            out, err = child.communicate(timeout=20)
            assert child.returncode == 0, out + err
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate()
    with auth.db() as con:
        rows = con.execute('SELECT * FROM users').fetchall()
    assert len(rows) == 1 and rows[0]['username'] == 'admin' and rows[0]['role'] == 'admin'


def test_existing_account_is_preserved_without_bootstrap_promotion(empty_auth, monkeypatch):
    with auth.db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) "
                    "VALUES('existing','existing@example.test','unused','user',1,1,1,1)")
        before = dict(con.execute('SELECT * FROM users').fetchone())
    monkeypatch.setattr(auth, '_password_hash_unchecked', lambda _: pytest.fail('Existing account rehashed'))
    auth._bootstrap_admin()
    auth.init_auth_db()
    with auth.db() as con:
        assert [dict(row) for row in con.execute('SELECT * FROM users')] == [before]


def test_bootstrap_requires_password(empty_auth, monkeypatch):
    monkeypatch.delenv('MTA_ADMIN_PASSWORD')
    auth._bootstrap_admin()
    with auth.db() as con:
        assert con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0


def test_bootstrap_database_errors_propagate_and_rollback(empty_auth):
    with auth.db() as con:
        con.execute("CREATE TRIGGER reject_admin BEFORE INSERT ON users "
                    "BEGIN SELECT RAISE(ABORT,'fixture constraint'); END")
    with pytest.raises(sqlite3.IntegrityError, match='fixture constraint'):
        auth._bootstrap_admin()
    with auth.db() as con:
        assert con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0
        con.execute('DROP TRIGGER reject_admin')
    auth._bootstrap_admin()
    with auth.db() as con:
        assert con.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 1
