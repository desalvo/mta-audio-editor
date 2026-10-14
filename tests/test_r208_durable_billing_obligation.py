"""Durable billing obligations survive later changes to the opt-in setting."""
from app import ai_metering_bridge as bridge


def test_existing_ledger_remains_required_when_preference_is_disabled(monkeypatch):
    monkeypatch.setattr(bridge, '_identity', lambda job_id: (7, 'arranger'))
    monkeypatch.setattr(bridge.ai_billing, 'user_billing_enabled', lambda user: False)
    monkeypatch.setattr(bridge.ai_billing, 'existing_inference_ledger_job',
                        lambda job, user, operation: 'ledger-123')
    assert bridge.billing_required('valid-job') is True


def test_non_provisioned_nonbillable_job_remains_unbilled(monkeypatch):
    monkeypatch.setattr(bridge, '_identity', lambda job_id: (7, 'remix'))
    monkeypatch.setattr(bridge.ai_billing, 'user_billing_enabled', lambda user: False)
    monkeypatch.setattr(bridge.ai_billing, 'existing_inference_ledger_job',
                        lambda job, user, operation: None)
    assert bridge.billing_required('valid-job') is False
    assert bridge.register_settlement('valid-job') is False
