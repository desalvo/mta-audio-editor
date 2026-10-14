"""Cross-resource recovery must never convert pending billing into completed."""
import pytest
from app import ai_finalization


def test_nonpublished_never_finalizes(monkeypatch):
    monkeypatch.setattr(ai_finalization, 'readiness', lambda job: {'publication': 'pending', 'billing': None})
    monkeypatch.setattr(ai_finalization.ai_arranger_runtime, 'reconcile_published_audio', lambda job: pytest.fail('premature completion'))
    assert ai_finalization.reconcile('abcdef12') is False


def test_pending_delivery_does_not_complete(monkeypatch):
    monkeypatch.setattr(ai_finalization, 'readiness', lambda job: {'publication': 'published', 'billing': 'pending', 'ready': False})
    monkeypatch.setattr(ai_finalization.ai_billing_outbox, 'deliver', lambda **kw: 0)
    monkeypatch.setattr(ai_finalization.ai_arranger_runtime, 'reconcile_published_audio', lambda job: pytest.fail('premature completion'))
    assert ai_finalization.reconcile('abcdef12') is False


def test_delivery_then_reconciliation(monkeypatch):
    state = {'billing': 'pending', 'called': 0}
    monkeypatch.setattr(ai_finalization, 'readiness', lambda job: {'publication': 'published', 'billing': state['billing'], 'ready': state['billing'] == 'delivered'})
    def deliver(**kwargs):
        state['billing'] = 'delivered'
        return 1
    def done(job):
        state['called'] += 1
        return True
    monkeypatch.setattr(ai_finalization.ai_billing_outbox, 'deliver', deliver)
    monkeypatch.setattr(ai_finalization.ai_arranger_runtime, 'reconcile_published_audio', done)
    assert ai_finalization.reconcile('abcdef12') is True
    assert state['called'] == 1


def test_failed_billing_delivery_propagates(monkeypatch):
    monkeypatch.setattr(ai_finalization, 'readiness', lambda job: {'publication': 'published', 'billing': 'pending', 'ready': False})
    def fail(**kwargs):
        raise RuntimeError('ledger unavailable')
    monkeypatch.setattr(ai_finalization.ai_billing_outbox, 'deliver', fail)
    monkeypatch.setattr(ai_finalization.ai_arranger_runtime, 'reconcile_published_audio', lambda job: pytest.fail('premature completion'))
    with pytest.raises(RuntimeError, match='ledger unavailable'):
        ai_finalization.reconcile('abcdef12')


def test_missing_billing_intent_reconstructed_from_evidence(monkeypatch):
    state = {'billing': None, 'register': 0, 'deliver': 0}
    def status(_):
        return {'publication': 'published', 'billing': state['billing'],
                'billing_required': True, 'ready': state['billing'] == 'delivered'}
    def register(_):
        state['register'] += 1
        state['billing'] = 'pending'
    def deliver(**_):
        state['deliver'] += 1
        state['billing'] = 'delivered'
    monkeypatch.setattr(ai_finalization, 'readiness', status)
    monkeypatch.setattr(ai_finalization.ai_metering_bridge, 'register_settlement', register)
    monkeypatch.setattr(ai_finalization.ai_billing_outbox, 'deliver', deliver)
    monkeypatch.setattr(ai_finalization.ai_arranger_runtime, 'reconcile_published_audio', lambda _: True)
    assert ai_finalization.reconcile('abcdef12')
    assert (state['register'], state['deliver']) == (1, 1)
    assert ai_finalization.reconcile('abcdef12')
    assert (state['register'], state['deliver']) == (1, 1)

def test_missing_metering_fails_closed(monkeypatch):
    monkeypatch.setattr(ai_finalization, 'readiness', lambda _: {
        'publication': 'published', 'billing': None, 'billing_required': True, 'ready': False})
    def no_evidence(_):
        raise ValueError('Measured consumption is required')
    monkeypatch.setattr(ai_finalization.ai_metering_bridge, 'register_settlement', no_evidence)
    monkeypatch.setattr(ai_finalization.ai_arranger_runtime, 'reconcile_published_audio',
                        lambda _: pytest.fail('must not complete without metering'))
    with pytest.raises(ValueError, match='Measured consumption'):
        ai_finalization.reconcile('abcdef12')
