import sqlite3
import pytest
from app.regime_operation_fence import initialize, admit, inspect, validate_receipt, FenceBlocked
from app.noncommercial_statements import create_statement, export_statement


def test_fence_receipts_and_read_only_status(tmp_path):
    p = tmp_path / 'fence.sqlite'
    with sqlite3.connect(p, isolation_level=None) as c:
        initialize(c)
        c.execute('BEGIN IMMEDIATE')
        receipt = admit(c,'paypal-order-10','checkout',required_regime='NON_COMMERCIAL')
        c.commit()
        assert inspect(c)['open_by_kind']['checkout'] == 1
        assert inspect(c)['transition_enabled'] is False
        assert validate_receipt(c, 'paypal-order-10', kind='checkout', regime='NON_COMMERCIAL', revision=0) == receipt
        with pytest.raises(FenceBlocked):
            validate_receipt(c, 'paypal-order-10',kind='checkout', regime='COMMERCIAL', revision=0)


def test_export_verified_statement_and_reject_tampering():
    c = sqlite3.connect(':memory:', isolation_level=None)
    c.execute('CREATE TABLE ai_compute_jobs (id INTEGER,user_id INTEGER,started_at INTEGER,status TEXT,usage_json TEXT,resource_source TEXT,billable INTEGER)')
    c.execute('INSERT INTO ai_compute_jobs VALUES (1,1,100,\'completed\',\'{"cpu_seconds":1,"gpu_seconds":1}\',\'gpu-agent\',1)')
    record = create_statement(c,start=100,end=200,documented_cost_cents=20)
    assert export_statement(c,start=100,end=200)['sha256'] == record['sha256']
    with pytest.raises(ValueError):
        export_statement(c,start=200,end=300)
    # Modern schema rejects tampering at the SQLite trigger boundary, rather
    # than waiting until export verification.
    with pytest.raises(sqlite3.IntegrityError,match='Immutable noncommercial statement'):
        c.execute("UPDATE nc_period_statements SET sha256='bad'")
    assert export_statement(c,start=100,end=200)['sha256'] == record['sha256']


def test_public_terms_do_not_advertise_cacheable_legal_mode(monkeypatch):
    from fastapi import Response
    from app import resource_routes, service_regime
    monkeypatch.setattr(service_regime,'current_regime',lambda: service_regime.Regime.NON_COMMERCIAL)
    response=Response()
    result=resource_routes.public_regime_terms('en',response)
    assert response.headers['cache-control']=='no-store'
    assert result['legal_review_required'] is True
    assert result['regime']=='NON_COMMERCIAL'
