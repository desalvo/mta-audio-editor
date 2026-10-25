import sqlite3

import pytest
from app.regime_transition_plan import build_plan, verify_plan


def test_transition_plan_fails_closed_without_financial_tables(tmp_path):
    conn = sqlite3.connect(':memory:')
    config = tmp_path/'regime.json'
    plan = build_plan(conn, target='COMMERCIAL', config_path=config)
    assert plan['ready_for_transition'] is False
    assert plan['from'] == 'NON_COMMERCIAL'
    assert plan['to'] == 'COMMERCIAL'
    assert plan['unresolved']
    assert verify_plan(plan)
    assert list(conn.execute('SELECT name FROM sqlite_master')) == []


def test_transition_plan_tamper_detected(tmp_path):
    conn = sqlite3.connect(':memory:')
    plan = build_plan(conn, target='COMMERCIAL', config_path=tmp_path/'cfg')
    plan['revision'] += 1
    assert not verify_plan(plan)


def test_transition_plan_cannot_rewrite_billing(tmp_path):
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE resource_credits(id INTEGER)')
    conn.execute('INSERT INTO resource_credits VALUES(123)')
    plan = build_plan(conn, target='COMMERCIAL', config_path=tmp_path/'cfg')
    assert plan['inventory']['credit_movements']['state'] == 'needs_reconciliation'
    assert conn.execute('SELECT id FROM resource_credits').fetchall() == [(123,)]
    assert verify_plan(plan)


def test_transition_plan_rejects_unknown_target(tmp_path):
    with pytest.raises(ValueError):
        build_plan(sqlite3.connect(':memory:'), target='MAYBE', config_path=tmp_path/'cfg')
