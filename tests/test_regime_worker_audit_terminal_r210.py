"""Fail-closed audit of ledger/fence/worker state inconsistencies."""
from app.regime_worker_claims import audit_claim_integrity
from test_regime_worker_completion_r210 import setup


def test_terminal_ledger_with_running_claim_is_unsafe(tmp_path):
    c, _ = setup(tmp_path, billable=0)
    c.execute("UPDATE ai_compute_jobs SET status='completed'")
    report = audit_claim_integrity(c)
    assert report['safe'] is False
    assert report['issues']['terminal_ledger_running_claim'] == 1


def test_finished_claim_with_open_fence_is_unsafe_even_if_ledger_running(tmp_path):
    c, _ = setup(tmp_path, billable=0)
    c.execute("UPDATE regime_worker_claims SET state='finished'")
    report = audit_claim_integrity(c)
    assert report['safe'] is False
    assert report['issues']['finished_claim_open_fence'] == 1


def test_closed_fence_on_running_ledger_is_unsafe(tmp_path):
    c, _ = setup(tmp_path, billable=0)
    c.execute("UPDATE regime_worker_claims SET state='finished'")
    c.execute("UPDATE regime_fence_operations SET status='closed'")
    report = audit_claim_integrity(c)
    assert report['safe'] is False
    assert report['issues']['unfinished_ledger_closed_fence'] == 1


def test_consistent_running_claim_is_safe(tmp_path):
    c, _ = setup(tmp_path, billable=0)
    assert audit_claim_integrity(c)['safe'] is True
