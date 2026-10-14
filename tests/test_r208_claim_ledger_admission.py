"""Claim-time admission guard across concurrent scheduler processes."""
from app import ai_arranger_runtime as queue, ai_billing


def test_claim_blocks_missing_opted_in_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(ai_billing, 'user_billing_enabled', lambda uid: True)
    monkeypatch.setattr(ai_billing, 'existing_inference_ledger_job', lambda *args: None)
    accepted, _ = queue.start('project', 'arranger', lambda _: None,
        job_id='claimmissingledger', defer_spawn=True,
        payload={'schema_version': 1, 'actor_user_id': 7, 'adapter':'arranger'})
    assert accepted and not queue._claim('claimmissingledger')
    row = queue.get('claimmissingledger')
    assert row['state'] == 'blocked'
    assert row['message'] == 'Ledger admission needs reconciliation'


def test_claim_succeeds_with_existing_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(ai_billing, 'user_billing_enabled', lambda uid: True)
    monkeypatch.setattr(ai_billing, 'existing_inference_ledger_job', lambda *args: 'ledger-id')
    queue.start('project', 'remix', lambda _: None,
        job_id='claimvalidledger', defer_spawn=True,
        payload={'schema_version': 1, 'actor_user_id': 7, 'adapter':'remix'})
    assert queue._claim('claimvalidledger')
    assert queue.get('claimvalidledger')['state'] == 'running'


def test_claim_without_billing_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(ai_billing, 'user_billing_enabled', lambda uid: False)
    monkeypatch.setattr(ai_billing, 'existing_inference_ledger_job', lambda *args: None)
    queue.start('project', 'arranger', lambda _: None,
        job_id='claimunbilled', defer_spawn=True,
        payload={'schema_version': 1, 'actor_user_id': 7, 'adapter':'arranger'})
    assert queue._claim('claimunbilled')
