"""Durable ingestion must distinguish conflicting replays from server failures."""
import pytest
from fastapi import HTTPException
from app import main


@pytest.mark.parametrize('endpoint,adapter', [
    (main.ai_arranger_start_generation, 'arranger'),
    (main.ai_remix_start_generation, 'remix'),
])
def test_conflicting_replay_is_http_409(monkeypatch, endpoint, adapter):
    class Request:
        headers = {'Idempotency-Key': 'same-request'}
    monkeypatch.setattr(main, '_project_for_actor', lambda *args: object())
    monkeypatch.setattr(main, '_actor', lambda *args: {'id': 12})
    monkeypatch.setattr(main, 'configured_worker', lambda: object())
    monkeypatch.setattr(main, '_durable_generation_executor', lambda *args: lambda *args: None)
    def reject(*args, **kwargs):
        assert kwargs['defer_spawn'] is True
        assert kwargs['payload']['adapter'] == adapter
        raise ValueError('Conflicting replay of AI job identifier')
    monkeypatch.setattr(main.ai_arranger_runtime, 'start', reject)
    body_type = main.RearrangeRequest if adapter == 'arranger' else main.RemixRequest
    with pytest.raises(HTTPException) as exc:
        endpoint('p', Request(), body_type.model_construct())
    assert exc.value.status_code == 409


def test_no_implicit_charge_on_nonbillable_replay(tmp_path, monkeypatch):
    from app import ai_arranger_runtime as queue
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    payload = {'schema_version': 1, 'adapter': 'remix', 'actor_user_id': 12}
    _, saved = queue.start('p', 'remix', lambda *_: None, payload=payload,
                           idempotency_key='request', defer_spawn=True)
    accepted, replay = queue.start('p', 'remix', lambda *_: None, payload=payload,
                                   idempotency_key='request', defer_spawn=True)
    assert not accepted and replay['job_id'] == saved['job_id']
    with pytest.raises(ValueError, match='Conflicting replay'):
        queue.start('p', 'remix', lambda *_: None, payload={**payload, 'actor_user_id': 13},
                    idempotency_key='request', defer_spawn=True)
