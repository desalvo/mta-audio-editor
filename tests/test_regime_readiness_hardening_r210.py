"""Offline operator CLI must never certify live authorization, including error cases."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.regime_readiness_cli import inspect_snapshot


@pytest.mark.parametrize('current,target', [
    ('COMMERCIAL', 'NON_COMMERCIAL'),
    ('NON_COMMERCIAL', 'COMMERCIAL'),
    ('COMMERCIAL', 'COMMERCIAL'),
    ('NON_COMMERCIAL', 'NON_COMMERCIAL'),
])
def test_all_directions_are_diagnostic_only(tmp_path, current, target):
    db = tmp_path / 'snapshot.sqlite'
    sqlite3.connect(db).close()
    result = inspect_snapshot(str(db), current=current, target=target)
    assert result['ready_for_automatic_transition'] is False
    assert result['diagnostic_only'] is True
    assert result['offline_snapshot_only'] is True
    assert result['authorization_scope'] == 'none'
    assert result['snapshot_file_identity']['size_bytes'] == db.stat().st_size


@pytest.mark.parametrize('current,target', [
    ('COMMERCIAL', 'NON_COMMERCIAL'),
    ('NON_COMMERCIAL', 'COMMERCIAL'),
])
def test_malformed_database_fail_closed(tmp_path, current, target):
    db = tmp_path / 'bad.sqlite'
    db.write_bytes(b'not a sqlite database')
    result = inspect_snapshot(str(db), current=current, target=target)
    assert result['ready_for_automatic_transition'] is False
    assert result['unresolved'] == ['readiness_inspection_failed']
    assert result['offline_snapshot_only'] is True


@pytest.mark.parametrize('body', [b'', b'not a sqlite database', b'\x00' * 128])
def test_cli_produces_nonzero_code_and_unprivileged_report(tmp_path, body):
    db = tmp_path / 'db.sqlite'
    db.write_bytes(body)
    output = tmp_path / 'report.json'
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, '-m', 'app.regime_readiness_cli', '--db', str(db),
           '--current', 'COMMERCIAL', '--target', 'NON_COMMERCIAL', '--output', str(output)]
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(output.read_text())
    assert report['ready_for_automatic_transition'] is False
    assert report['offline_snapshot_only'] is True
    assert report['authorization_scope'] == 'none'
    assert output.stat().st_mode & 0o777 == 0o600
    again = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert again.returncode == 2


def test_symlinked_report_not_overwritten(tmp_path):
    db = tmp_path / 'db.sqlite'
    sqlite3.connect(db).close()
    protected = tmp_path / 'protected.txt'
    protected.write_text('protected')
    output = tmp_path / 'output.json'
    output.symlink_to(protected)
    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, '-m', 'app.regime_readiness_cli', '--db', str(db),
           '--current', 'COMMERCIAL', '--target', 'NON_COMMERCIAL', '--output', str(output)]
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert result.returncode == 2
    assert protected.read_text() == 'protected'
