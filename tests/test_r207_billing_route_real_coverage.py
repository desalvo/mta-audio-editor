"""Exercise administrative billing HTTP behavior, including denial and CSV serialization."""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest
from app import ai_billing_routes as routes


@pytest.fixture
def billing_client(monkeypatch):
    web = FastAPI()
    web.include_router(routes.router)
    monkeypatch.setattr(routes, 'require_admin', lambda request: None)
    return TestClient(web)


def test_admin_guard_and_error_mapping(monkeypatch, billing_client):
    monkeypatch.setattr(routes, 'require_admin', lambda request: (_ for _ in ()).throw(HTTPException(403)))
    assert billing_client.get('/api/admin/ai-billing/prices').status_code == 403
    monkeypatch.setattr(routes, 'require_admin', lambda request: None)
    for error in (ValueError('invalid'), TypeError('invalid'), KeyError('invalid'), OverflowError('invalid')):
        with pytest.raises(HTTPException) as exc:
            routes._error(lambda: (_ for _ in ()).throw(error))
        assert exc.value.status_code == 400


def test_billing_read_endpoints(monkeypatch, billing_client):
    b = routes.ai_billing
    monkeypatch.setattr(b, 'report', lambda *args, **kwargs: {'rows': [{'day': '2026-10-01', 'user_id': 2, 'jobs': 3, 'metered_jobs': 3, 'cost_micro': 10, 'resources': {'cpu_seconds': 3}}]})
    monkeypatch.setattr(b, 'prices', lambda: {'cpu_seconds': 100})
    monkeypatch.setattr(b, 'tariff_history', lambda: [])
    monkeypatch.setattr(b, 'reconcile_period', lambda *args: {'ok': True})
    monkeypatch.setattr(b, 'audit_closed_invoices', lambda user_id: {'ok': True})
    monkeypatch.setattr(b, 'bills', lambda user_id: [{'user_id': user_id}])
    monkeypatch.setattr(b, 'schedules', lambda: [{'cadence': 'month'}])
    monkeypatch.setattr(b, 'run_scheduled_closures', lambda: [])
    assert billing_client.get('/api/admin/ai-billing/report').json()['rows'][0]['jobs'] == 3
    assert billing_client.get('/api/admin/ai-billing/prices').json()['currency'] == 'EUR'
    assert billing_client.get('/api/admin/ai-billing/reconcile?user_id=2&start=2026-09-01&end=2026-10-01').json()['ok']
    assert billing_client.get('/api/admin/ai-billing/audit-closed').json()['ok']
    assert billing_client.get('/api/admin/ai-billing/invoices?user_id=2').json()['items'][0]['user_id'] == 2
    assert billing_client.get('/api/admin/ai-billing/schedules').json()['items'][0]['cadence'] == 'month'
    assert billing_client.post('/api/admin/ai-billing/run-schedules').json() == {'items': []}
    csv = billing_client.get('/api/admin/ai-billing/export.csv')
    assert csv.status_code == 200 and 'cpu_seconds' in csv.text and 'ai-usage.csv' in csv.headers['content-disposition']


def test_billing_write_endpoints(monkeypatch, billing_client):
    b = routes.ai_billing
    recorded = []
    monkeypatch.setattr(b, 'set_price', lambda *args, **kwargs: recorded.append(('price', args, kwargs)))
    monkeypatch.setattr(b, 'close_period', lambda *args: {'user_id': args[0]})
    monkeypatch.setattr(b, 'user_billing_enabled', lambda user_id: True)
    monkeypatch.setattr(b, 'configure_schedule', lambda *args: recorded.append(('schedule', args)))
    assert billing_client.put('/api/admin/ai-billing/prices/cpu_seconds', json={'micro_per_unit': 2, 'valid_from': '2026-10-11'}).json()['ok']
    assert billing_client.post('/api/admin/ai-billing/close', json={'user_id': 2, 'start': '2026-10-01', 'end': '2026-11-01'}).json()['user_id'] == 2
    assert billing_client.put('/api/admin/ai-billing/schedules/2', json={'cadence': 'month'}).json()['ok']
    assert [v[0] for v in recorded] == ['price', 'schedule']
    assert billing_client.put('/api/admin/ai-billing/prices/cpu_seconds', json={}).status_code == 400
    assert billing_client.post('/api/admin/ai-billing/close', json={}).status_code == 400
    assert billing_client.put('/api/admin/ai-billing/schedules/2', json={}).status_code == 400


def test_billing_energy_diagnostic_routes(monkeypatch, billing_client):
    from app import ai_gpu_energy_estimator as energy
    monkeypatch.setattr(energy, 'calibrations', lambda: [{'gpu_id': 'gpu-test', 'idle_watts': 20.0, 'full_load_watts': 100.0}])
    recorded = []
    monkeypatch.setattr(energy, 'store_calibration', lambda data: recorded.append(data))
    monkeypatch.setattr(energy, 'estimate_job_energy', lambda *args, **kwargs: {'diagnostic': True})
    assert billing_client.get('/api/admin/ai-billing/gpu-calibrations').json()['items'][0]['gpu_id'] == 'gpu-test'
    assert billing_client.put('/api/admin/ai-billing/gpu-calibrations', json={'gpu_id': 'gpu-test', 'idle_watts': 20, 'full_load_watts': 100}).json()['ok']
    assert len(recorded) == 1
    assert billing_client.post('/api/admin/ai-billing/gpu-energy-estimate', json={'gpu_id': 'missing', 'gpu_engine_seconds': 3, 'job_wall_seconds': 4}).status_code == 400
    assert billing_client.post('/api/admin/ai-billing/gpu-energy-estimate', json={'gpu_id': 'gpu-test', 'gpu_engine_seconds': 3, 'job_wall_seconds': 4}).json()['diagnostic']
