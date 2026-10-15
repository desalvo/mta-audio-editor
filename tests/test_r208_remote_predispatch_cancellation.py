"""A durable cancellation claimed before dispatch must not invoke a model."""
import base64

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from app import ai_billing_routes as routes
from app import ai_request_dedup as dedup


class Req:
    def __init__(self, key='a'*20):
        self.headers = {'authorization':'Bearer token', 'content-type':'audio/wav',
                        'content-length':'4', 'x-mta-ai-idempotency-key':key,
                        'x-mta-ai-options':base64.urlsafe_b64encode(b'{}').decode().rstrip('=')}
    async def stream(self):
        yield b'RIFF'


@pytest.mark.asyncio
async def test_cancel_after_admission_prevents_dispatch(monkeypatch):
    from app import ai_worker_registry, ai_metering_agent
    worker = Mock()
    monkeypatch.setattr(routes.ai_access, 'authenticate', lambda _: {'user_id':5, 'id':7})
    monkeypatch.setattr(ai_worker_registry, 'resolve_worker', lambda _: object())
    monkeypatch.setattr(dedup, 'admit', lambda *args: None)
    monkeypatch.setattr(dedup, 'is_cancelled', lambda *args: True)
    monkeypatch.setattr(ai_metering_agent, 'execute_registered_worker', worker)
    with pytest.raises(HTTPException) as exc:
        await routes.execute_remote_ai_audio_job('whisper', Req())
    assert exc.value.status_code == 409
    worker.assert_not_called()


@pytest.mark.asyncio
async def test_ordinary_admitted_job_still_dispatches(monkeypatch):
    from app import ai_worker_registry, ai_metering_agent
    monkeypatch.setattr(routes.ai_access, 'authenticate', lambda _: {'user_id':5, 'id':7})
    monkeypatch.setattr(ai_worker_registry, 'resolve_worker', lambda _: object())
    monkeypatch.setattr(dedup, 'admit', lambda *args: None)
    monkeypatch.setattr(dedup, 'is_cancelled', lambda *args: False)
    called = Mock(side_effect=RuntimeError('worker-called'))
    monkeypatch.setattr(ai_metering_agent, 'execute_registered_worker', called)
    with pytest.raises(RuntimeError, match='worker-called'):
        await routes.execute_remote_ai_audio_job('whisper', Req())
    called.assert_called_once()
