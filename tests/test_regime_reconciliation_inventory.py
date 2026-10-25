import sqlite3
from app.regime_reconciliation import inventory

def test_unknown_schema_fails_closed():
    report = inventory(sqlite3.connect(':memory:'))
    assert report['credit_movements']['state'] == 'unknown_schema'

def test_historic_credit_movements_remain_reconciliation_items():
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE resource_credits(id TEXT)')
    con.execute("INSERT INTO resource_credits VALUES ('history')")
    assert inventory(con)['credit_movements'] == {'state':'needs_reconciliation','count':1}

def test_completed_job_not_active():
    con=sqlite3.connect(':memory:')
    con.execute('CREATE TABLE ai_compute_jobs(status TEXT)')
    con.execute("INSERT INTO ai_compute_jobs VALUES ('completed')")
    assert inventory(con)['active_jobs'] == {'state':'clear','count':0}

def test_reconciliation_inventory_handles_unknown_columns():
    con=sqlite3.connect(':memory:')
    con.execute('CREATE TABLE resource_memberships(other TEXT)')
    assert inventory(con)['subscriptions']['state']=='unknown_schema'

def test_readiness_does_not_authorize_switch_even_without_open_rows():
    from app.regime_reconciliation import readiness_report
    con=sqlite3.connect(':memory:')
    report=readiness_report(con,current='NON_COMMERCIAL',target='COMMERCIAL')
    assert not report['ready_for_automatic_transition']
    assert report['unresolved']

def test_readiness_rejects_unrecognized_regime():
    import pytest
    from app.regime_reconciliation import readiness_report
    with pytest.raises(ValueError):
        readiness_report(sqlite3.connect(':memory:'),current='UNKNOWN',target='COMMERCIAL')
