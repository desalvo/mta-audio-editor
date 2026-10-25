"""Actual deferred publication/settlement must retain original epoch ownership."""
import pytest

from app import auth, ai_billing, ai_billing_outbox as billing, ai_publish_outbox as publication
from app import ai_metering_bridge as bridge
from app.regime_operation_fence import FenceBlocked
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401
from test_r210_deferred_owner_e2e import setup as setup, staged_execution  # noqa: F401


@pytest.mark.parametrize('drift', ['revision', 'regime', 'transitioning', 'claim_revision'])
def test_stale_staged_result_cannot_publish_or_charge(setup, drift):
    job, ledger, _ = staged_execution(setup, publish_now=False)
    statements = {
        'revision': 'UPDATE regime_fence_state SET revision=revision+1',
        'regime': "UPDATE regime_fence_state SET regime='COMMERCIAL'",
        'transitioning': 'UPDATE regime_fence_state SET transitioning=1',
        'claim_revision': 'UPDATE regime_worker_claims SET revision=revision+1',
    }
    with auth.db() as c:
        c.execute(statements[drift])
    with pytest.raises(FenceBlocked):
        publication.recover(lambda *_: pytest.fail('Published stale audio'), job_id=job)
    with pytest.raises(FenceBlocked):
        bridge.register_settlement(job)
    with auth.db() as c:
        assert c.execute('SELECT status FROM ai_compute_jobs WHERE id=?', (ledger,)).fetchone()[0] == 'running'
        assert c.execute('SELECT state FROM regime_worker_claims').fetchone()[0] == 'running'
        assert c.execute('SELECT status FROM regime_fence_operations').fetchone()[0] == 'open'
    with publication._open() as c:
        assert c.execute('SELECT state FROM publications').fetchone()[0] == 'pending'
    assert billing.inspect(job) is None


def test_original_outbox_ack_after_new_epoch_never_recharges(setup, monkeypatch):
    job, ledger, receipt = staged_execution(setup, publish_now=True)
    bridge.register_settlement(job)
    with pytest.raises(RuntimeError, match='ack lost'):
        billing.deliver(job_id=job, on_applied=lambda _: (_ for _ in ()).throw(RuntimeError('ack lost')))
    assert billing.inspect(job)['state'] == 'pending'
    with auth.db() as c:
        before = tuple(c.execute('SELECT status,finished_at,usage_json,resource_source FROM ai_compute_jobs WHERE id=?', (ledger,)).fetchone())
        c.execute('UPDATE regime_fence_state SET revision=revision+1')
    original = ai_billing.finish_job_idempotent
    def recover(*a, **kw):
        assert kw['worker_id'] == receipt['worker_id']
        assert kw['claim_token'] == receipt['claim_token']
        result = original(*a, **kw)
        assert result['already_finalized']
        return result
    monkeypatch.setattr(ai_billing, 'finish_job_idempotent', recover)
    monkeypatch.setattr(ai_billing, 'finish_job', lambda *_a, **_kw: pytest.fail('Charged twice'))
    assert billing.deliver(job_id=job) == 1
    assert billing.deliver(job_id=job) == 0
    assert billing.inspect(job)['state'] == 'delivered'
    with auth.db() as c:
        assert tuple(c.execute('SELECT status,finished_at,usage_json,resource_source FROM ai_compute_jobs WHERE id=?', (ledger,)).fetchone()) == before
