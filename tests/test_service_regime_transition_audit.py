"""Read-only migration readiness must never quietly discard monetary history."""
import json
import sqlite3
from app.service_regime import Regime, audit_transition_database


def test_legacy_state_is_not_assumed_clean(tmp_path):
    con = sqlite3.connect(':memory:')
    path = tmp_path / 'service-regime.json'
    state = audit_transition_database(con, Regime.COMMERCIAL, path=path)
    assert not state['ready']
    assert not state['transition_enabled']
    assert state['counts']['subscriptions'] is None
    assert not path.exists()


def test_outstanding_money_and_jobs_are_blockers(tmp_path):
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE resource_memberships (plan TEXT)')
    con.execute('INSERT INTO resource_memberships VALUES (?)', ('month',))
    con.execute('CREATE TABLE resource_credits (delta_micro INTEGER)')
    con.execute('INSERT INTO resource_credits VALUES (20000)')
    con.execute('CREATE TABLE ai_compute_jobs (status TEXT)')
    con.execute('INSERT INTO ai_compute_jobs VALUES (?)', ('running',))
    state = audit_transition_database(con, Regime.COMMERCIAL,
                                      path=tmp_path / 'service-regime.json')
    assert {'subscriptions', 'credit_movements', 'active_jobs'} <= set(state['blockers'])
    assert state['counts']['active_jobs'] == 1
    assert con.execute('SELECT delta_micro FROM resource_credits').fetchone()[0] == 20000


def test_current_regime_is_still_readable(tmp_path):
    path = tmp_path / 'service-regime.json'
    path.write_text(json.dumps({'regime': 'COMMERCIAL', 'revision': 4}))
    state = audit_transition_database(sqlite3.connect(':memory:'), Regime.COMMERCIAL, path=path)
    assert state['ready'] and not state['transition_enabled']
    assert state['revision'] == 4
