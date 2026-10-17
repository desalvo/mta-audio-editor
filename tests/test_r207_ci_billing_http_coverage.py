"""End-to-end API regression checks for closed billing and token administration.

All accounting operations are replaced by deterministic isolated doubles; these
checks exercise the HTTP/validation/auth adapters without using a live worker.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import ai_billing_routes as billing, ai_token_routes as tokens


@pytest.fixture
def client(monkeypatch):
    api = FastAPI()
    api.include_router(billing.router)
    api.include_router(tokens.router)
    monkeypatch.setattr(billing, 'require_admin', lambda request: {'id': 1})
    monkeypatch.setattr(tokens, 'require_admin', lambda request: {'id': 1})
    monkeypatch.setattr(tokens, 'require_user', lambda request: {'id': 7})
    monkeypatch.setattr(billing.ai_billing, 'report', lambda *a, **k: {
        'rows': [{'day': '2026-10-01', 'user_id': 7, 'jobs': 2, 'metered_jobs': 2,
                  'cost_micro': 31, 'resources': {'cpu': 3}}], 'total_micro': 31})
    monkeypatch.setattr(billing.ai_billing, 'reconcile_period', lambda *a: {'ok': True})
    monkeypatch.setattr(billing.ai_billing, 'prices', lambda: {'cpu': 10})
    monkeypatch.setattr(billing.ai_billing, 'tariff_history', lambda: [])
    monkeypatch.setattr(billing.ai_billing, 'set_price', lambda *a, **k: None)
    monkeypatch.setattr(billing.ai_billing, 'user_billing_enabled', lambda user_id: user_id == 7)
    monkeypatch.setattr(billing.ai_billing, 'close_period', lambda *a: {'id': 3, 'total_micro': 31})
    monkeypatch.setattr(billing.ai_billing, 'audit_closed_invoices', lambda *a: {'issues': []})
    monkeypatch.setattr(billing.ai_billing, 'bills', lambda *a: [{'id': 3}])
    monkeypatch.setattr(billing.ai_billing, 'configure_schedule', lambda *a: None)
    monkeypatch.setattr(billing.ai_billing, 'schedules', lambda: [{'user_id': 7}])
    monkeypatch.setattr(billing.ai_billing, 'run_scheduled_closures', lambda: [{'id': 3}])
    monkeypatch.setattr(tokens.ai_access, 'list_tokens', lambda: [
        {'id': 4, 'user_id': 7, 'label': 'client', 'revoked_at': None}])
    monkeypatch.setattr(tokens.ai_access, 'issue', lambda *a: {'id': 5, 'token': 'only-once'})
    monkeypatch.setattr(tokens.ai_access, 'revoke', lambda *a: True)
    monkeypatch.setattr(tokens.ai_access, 'rotate', lambda *a: {'id': 5, 'token': 'only-once'})
    monkeypatch.setattr(tokens.ai_access, 'summary', lambda *a: [{'user_id': 7}])
    return TestClient(api)


@pytest.mark.parametrize(('method', 'path', 'payload', 'expected'), [
    ('get', '/api/admin/ai-billing/report?user_id=7', None, 200),
    ('get', '/api/admin/ai-billing/reconcile?user_id=7&start=2026-10-01&end=2026-11-01', None, 200),
    ('get', '/api/admin/ai-billing/prices', None, 200),
    ('put', '/api/admin/ai-billing/prices/cpu', {'micro_per_unit': 10}, 200),
    ('post', '/api/admin/ai-billing/close', {'user_id': 7, 'start': '2026-10-01', 'end': '2026-11-01'}, 200),
    ('get', '/api/admin/ai-billing/audit-closed?user_id=7', None, 200),
    ('get', '/api/admin/ai-billing/invoices?user_id=7', None, 200),
    ('put', '/api/admin/ai-billing/schedules/7', {'cadence': 'month'}, 200),
    ('get', '/api/admin/ai-billing/schedules', None, 200),
    ('post', '/api/admin/ai-billing/run-schedules', None, 200),
    ('get', '/api/admin/ai-billing/export.csv', None, 200),
    ('get', '/admin/ai-billing', None, 200),
    ('get', '/api/admin/ai-tokens', None, 200),
    ('post', '/api/admin/ai-tokens', {'user_id': 7}, 200),
    ('delete', '/api/admin/ai-tokens/4', None, 200),
    ('post', '/api/admin/ai-tokens/4/rotate', None, 200),
    ('get', '/api/admin/ai-usage', None, 200),
    ('get', '/api/account/ai-usage', None, 200),
    ('get', '/admin/ai-tokens', None, 200),
])
def test_admin_billing_and_tokens_http(client, method, path, payload, expected):
    response = getattr(client, method)(path, **({'json': payload} if payload is not None else {}))
    assert response.status_code == expected, response.text
    if path.endswith('export.csv'):
        assert '2026-10-01' in response.text


def test_billing_rejects_invalid_tariff_payload(client):
    assert client.put('/api/admin/ai-billing/prices/cpu', json={}).status_code == 400


def test_revoke_unknown_token(client, monkeypatch):
    monkeypatch.setattr(tokens.ai_access, 'revoke', lambda *_: False)
    assert client.delete('/api/admin/ai-tokens/4').status_code == 404


def test_rotate_revoked_token(client, monkeypatch):
    monkeypatch.setattr(tokens.ai_access, 'list_tokens', lambda: [])
    assert client.post('/api/admin/ai-tokens/4/rotate').status_code == 404


def test_admin_guard_denies_anonymous(client, monkeypatch):
    from fastapi import HTTPException
    def deny(_):
        raise HTTPException(403, 'admin required')
    monkeypatch.setattr(billing, 'require_admin', deny)
    assert client.get('/api/admin/ai-billing/invoices').status_code == 403
    assert client.post('/api/admin/ai-billing/close', json={}).status_code == 403


def test_scheduler_success_and_fail_closed(monkeypatch, capsys):
    from app import ai_billing_scheduler as sched
    from app import ai_storage_sampler
    monkeypatch.setattr(ai_storage_sampler, 'sample_all', lambda: {'sampled': 2})
    monkeypatch.setattr(sched, 'run_scheduled_closures', lambda: [{'id': 1}])
    assert sched.main() == 0
    assert 'sampled' in capsys.readouterr().out
    monkeypatch.setattr(sched, 'run_scheduled_closures', lambda: [{'error': 'locked'}])
    assert sched.main() == 1
