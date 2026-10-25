import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.regime_readiness_cli import inspect_snapshot


def test_empty_existing_db_is_never_ready(tmp_path):
    db = tmp_path / 'db.sqlite'
    sqlite3.connect(db).close()
    result = inspect_snapshot(str(db), current='NON_COMMERCIAL', target='COMMERCIAL')
    assert result['ready_for_automatic_transition'] is False
    assert result['offline_snapshot_only'] is True
    assert result['unresolved']


def test_snapshot_is_never_modified(tmp_path):
    db = tmp_path / 'db.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE marker(v INTEGER)')
        con.execute('INSERT INTO marker VALUES (42)')
    before = db.read_bytes()
    inspect_snapshot(str(db), current='COMMERCIAL', target='NON_COMMERCIAL')
    assert db.read_bytes() == before
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT v FROM marker').fetchone() == (42,)


@pytest.mark.parametrize('bad', ['NONCOMMERCIAL', 'INVALID', '', 'commercial'])
def test_invalid_regime_fails(bad, tmp_path):
    db = tmp_path / 'db.sqlite'
    sqlite3.connect(db).close()
    with pytest.raises(ValueError):
        inspect_snapshot(str(db), current=bad, target='COMMERCIAL')


def test_missing_and_symlink_blocked(tmp_path):
    missing = tmp_path / 'missing.sqlite'
    with pytest.raises(ValueError):
        inspect_snapshot(str(missing), current='NON_COMMERCIAL', target='COMMERCIAL')
    db = tmp_path / 'existing.sqlite'
    sqlite3.connect(db).close()
    link = tmp_path / 'link.sqlite'
    link.symlink_to(db)
    with pytest.raises(ValueError):
        inspect_snapshot(str(link), current='NON_COMMERCIAL', target='COMMERCIAL')


def test_cli_writes_private_report_never_overwrites(tmp_path):
    db = tmp_path / 'db.sqlite'
    sqlite3.connect(db).close()
    out = tmp_path / 'result.json'
    cmd = [sys.executable, '-m', 'app.regime_readiness_cli', '--db', str(db),
           '--current', 'NON_COMMERCIAL', '--target', 'COMMERCIAL', '--output', str(out)]
    root = Path(__file__).resolve().parents[1]
    first = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert first.returncode == 1, first.stderr
    result = json.loads(out.read_text())
    assert not result['ready_for_automatic_transition']
    assert out.stat().st_mode & 0o777 == 0o600
    second = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert second.returncode == 2
    assert out.read_text() == json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
