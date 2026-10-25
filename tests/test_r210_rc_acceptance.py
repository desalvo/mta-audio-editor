import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.rc_acceptance import evaluate


def test_no_evidence_is_blocked():
    result = evaluate()
    assert result['status'] == 'BLOCKED'
    assert not result['candidate'] and not result['release_authorized']
    assert len(result['checks']) == 8


def test_forged_evidence_cannot_authorize_rc():
    from app.rc_acceptance import _REQUIRED
    forged = {name: {'status': 'passed'} for name in _REQUIRED}
    result = evaluate(evidence=forged)
    assert all(x['claimed_pass'] for x in result['checks'].values())
    assert not result['candidate'] and not result['cutover_authorized']


def test_snapshot_diagnostic_cannot_authorize_rc(tmp_path):
    db = tmp_path / 'db.sqlite'
    sqlite3.connect(db).close()
    result = evaluate(db=str(db))
    assert result['database_diagnostic']['offline_snapshot_only']
    assert 'offline_snapshot_cannot_certify_live_readiness' in result['blockers']
    assert result['status'] == 'BLOCKED'


def test_cli_exit_and_private_exclusive_report(tmp_path):
    outfile = tmp_path / 'acceptance.json'
    cmd = [sys.executable, '-m', 'app.rc_acceptance', '--output', str(outfile)]
    root = Path(__file__).resolve().parents[1]
    a = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert a.returncode == 1, a.stderr
    assert json.loads(outfile.read_text())['candidate'] is False
    assert outfile.stat().st_mode & 0o777 == 0o600
    b = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert b.returncode == 2


def test_cli_symlink_report_rejected(tmp_path):
    target = tmp_path / 'important.txt'
    target.write_text('preserve')
    link = tmp_path / 'report.json'
    link.symlink_to(target)
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, '-m', 'app.rc_acceptance', '--output', str(link)],
                       cwd=root, capture_output=True, text=True)
    assert r.returncode == 2
    assert target.read_text() == 'preserve'
