import hashlib
import sqlite3

import pytest
from app.noncommercial_statements import export_statement_csv
from app.regime_reconciliation import combined_readiness
from app.regime_operation_fence import initialize


def test_csv_export_missing_is_rejected():
    with pytest.raises(ValueError):
        export_statement_csv(sqlite3.connect(':memory:'), start=1, end=2)


def test_combined_reconciliation_missing_fence_fails_closed():
    report = combined_readiness(sqlite3.connect(':memory:'), current='NON_COMMERCIAL', target='COMMERCIAL')
    assert 'operation_fence_missing' in report['unresolved']
    assert report['ready_for_automatic_transition'] is False


def test_combined_reconciliation_initialized_fence_remains_safe():
    con = sqlite3.connect(':memory:')
    initialize(con)
    report = combined_readiness(con, current='NON_COMMERCIAL', target='COMMERCIAL')
    assert 'entry_points_not_instrumented' in report['unresolved']
    assert report['fence']['revision'] == 0


def test_combined_reconciliation_detects_drift():
    con = sqlite3.connect(':memory:')
    initialize(con, initial_regime='COMMERCIAL')
    report = combined_readiness(con, current='NON_COMMERCIAL', target='COMMERCIAL')
    assert 'operation_fence_regime_drift' in report['unresolved']


def test_csv_export_verifies_digest_and_contents():
    from app.noncommercial_statements import _canonical
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE nc_period_statements(period_start INTEGER,period_end INTEGER,statement_json TEXT,sha256 TEXT)')
    record = {'start':1,'end':3,'statement_type':'NON_COMMERCIAL_ALLOCATION',
              'posting_enabled':False,'currency':'EUR','contribution_cents':{'42':15},
              'measured_milliseconds':{'42':200},'total_draft_cents':15}
    payload = _canonical(record)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    con.execute('INSERT INTO nc_period_statements VALUES (?,?,?,?)',(1,3,payload,digest))
    output = export_statement_csv(con,start=1,end=3)
    assert output['sha256']==digest and '42,200,15,EUR,'+digest in output['content']
    con.execute("UPDATE nc_period_statements SET statement_json='{}'")
    with pytest.raises(ValueError,match='Tampered'):
        export_statement_csv(con,start=1,end=3)
