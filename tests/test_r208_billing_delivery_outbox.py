import pytest

from app import ai_billing_outbox as outbox


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    from app import ai_arranger_runtime as queue
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    return tmp_path


def test_replay_and_conflict(sandbox):
    assert outbox.register('inference1', 'billing1', 'done')
    assert not outbox.register('inference1', 'billing1', 'done')
    with pytest.raises(ValueError, match='Conflicting'):
        outbox.register('inference1', 'billing1', 'failed')
    with pytest.raises(ValueError, match='Conflicting'):
        outbox.register('inference2', 'billing1', 'done')


def test_recovery_after_ledger_commit(sandbox, monkeypatch):
    seen = set()
    def fake_finish(jid, status, usage, **kwargs):
        if jid in seen:
            return {'already_finalized': True}
        seen.add(jid)
        return {'already_finalized': False}
    monkeypatch.setattr(outbox.ai_billing, 'finish_job_idempotent', fake_finish)
    outbox.register('inference1', 'billing1', 'done')
    with pytest.raises(RuntimeError, match='crash'):
        outbox.deliver(on_applied=lambda _: (_ for _ in ()).throw(RuntimeError('crash')))
    assert outbox.inspect('inference1')['state'] == 'pending'
    assert outbox.deliver() == 1
    assert outbox.deliver() == 0
    assert seen == {'billing1'}
    assert outbox.inspect('inference1')['state'] == 'delivered'


def test_failed_delivery_remains_pending(sandbox, monkeypatch):
    outbox.register('inference1', 'billing1', 'done')
    def failure(*args, **kwargs):
        raise ValueError('ledger offline')
    monkeypatch.setattr(outbox.ai_billing, 'finish_job_idempotent', failure)
    with pytest.raises(ValueError, match='ledger offline'):
        outbox.deliver()
    assert outbox.inspect('inference1')['state'] == 'pending'
    assert 'ledger offline' in outbox.inspect('inference1')['last_error']


def test_invalid_measurements(sandbox):
    with pytest.raises(ValueError):
        outbox.register('inference1', 'billing1', 'done', {'gpu_seconds': 4}, source='worker')
    with pytest.raises(ValueError):
        outbox.register('../bad', 'billing1', 'done')
