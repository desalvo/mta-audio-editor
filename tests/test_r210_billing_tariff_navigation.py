"""Subscription tariff navigation reaches the guarded, actual rate editor."""
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from app import ai_billing_routes as routes


@pytest.fixture
def client(monkeypatch):
    app=FastAPI();app.include_router(routes.router)
    monkeypatch.setattr(routes,'require_admin',lambda request:None)
    return TestClient(app)


def test_subscription_tariff_link_reaches_existing_editor(client):
    source=(Path(__file__).resolve().parents[1]/'app/static/subscriptions.js').read_text()
    destination=re.search(r'href="([^"]+)"[^>]*>[^\n]*?Configure ordinary category tariffs',source).group(1)
    response=client.get(destination)
    assert response.status_code==200
    assert destination=='/admin/ai-billing#tariffs'
    assert 'id="tariffs"' in response.text and 'id="rates"' in response.text
    assert '/api/admin/ai-billing/prices/' in response.text
    assert 'Used for consumption billing and subscription overages.' in source
    assert 'Usate per il billing a consumo e gli extra quota degli abbonamenti.' in source


def test_old_subscription_url_redirects_to_tariffs(client):
    response=client.get('/ai-billing',follow_redirects=False)
    assert response.status_code==307
    assert response.headers['location']=='/admin/ai-billing#tariffs'
    assert client.get('/ai-billing').status_code==200


@pytest.mark.parametrize('path',['/admin/ai-billing','/ai-billing'])
def test_tariff_navigation_keeps_admin_boundary(client,monkeypatch,path):
    def denied(request):raise HTTPException(403,'Administrator required')
    monkeypatch.setattr(routes,'require_admin',denied)
    response=client.get(path,follow_redirects=False)
    assert response.status_code==403
    assert 'Tariffe e profili hardware' not in response.text
