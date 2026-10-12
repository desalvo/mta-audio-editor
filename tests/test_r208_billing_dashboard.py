"""Billing UI regression: admin-only render, safe controls and per-user opt-in."""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app import ai_billing_routes as routes


def test_billing_dashboard_admin_guard_and_controls(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    monkeypatch.setattr(routes, 'require_admin', lambda request: (_ for _ in ()).throw(HTTPException(403)))
    assert TestClient(app).get('/admin/ai-billing').status_code == 403
    monkeypatch.setattr(routes, 'require_admin', lambda request: None)
    response = TestClient(app).get('/admin/ai-billing')
    assert response.status_code == 200
    for marker in ('enablebilling', 'closebill', 'reconcile', 'gpu-host-agent',
                   'gpu-slots/preview', 'refreshusers', 'suggested-prices'):
        assert marker in response.text
    assert 'solo gli utenti abilitati possono avere periodi fatturati' in response.text
