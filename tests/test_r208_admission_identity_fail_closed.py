"""Durable AI admission binds actor, operation and immutable ledger policy."""
import pytest
from app import ai_arranger_runtime as queue, ai_metering_bridge

@pytest.mark.parametrize('patch', [
    {'actor_user_id': None}, {'actor_user_id': True}, {'actor_user_id': -1},
    {'actor_user_id': '7'}, {'adapter': 'remix'}, {'adapter': 'unknown'},
])
def test_claim_rejects_malformed_actor_or_adapter(tmp_path, monkeypatch, patch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    payload = {'schema_version': 1, 'actor_user_id': 7, 'adapter': 'arranger'}
    payload.update(patch)
    jid = 'malformed-' + str(len(list(tmp_path.iterdir()))) + str(abs(hash(str(patch))))
    queue.start('p', 'arranger', lambda _: None, job_id=jid, payload=payload, defer_spawn=True)
    assert queue._claim(jid) is False
    assert queue.get(jid)['state'] == 'blocked'
    with pytest.raises(ValueError):
        ai_metering_bridge._identity(jid)


def test_valid_durable_actor_can_claim_without_billing(tmp_path, monkeypatch):
    from app import ai_billing
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(ai_billing, 'user_billing_enabled', lambda uid: False)
    monkeypatch.setattr(ai_billing, 'existing_inference_ledger_job', lambda *args: None)
    queue.start('p', 'arranger', lambda _: None, job_id='valid-audio',
                payload={'schema_version':1, 'actor_user_id':7, 'adapter':'arranger'}, defer_spawn=True)
    assert queue._claim('valid-audio') is True
