import json
import hashlib
import sqlite3
import pytest
from app.noncommercial_statements import user_statements


def _db():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE nc_period_statements(period_start INTEGER,period_end INTEGER,statement_json TEXT,sha256 TEXT)')
    record = {'start': 1, 'end': 2, 'statement_type': 'NON_COMMERCIAL_ALLOCATION',
              'posting_enabled': False, 'currency': 'EUR', 'total_draft_cents': 125,
              'contribution_cents': {'user-a': 100, 'user-b': 25},
              'measured_milliseconds': {'user-a': 800, 'user-b': 200}}
    payload = json.dumps(record)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    conn.execute('INSERT INTO nc_period_statements VALUES(?,?,?,?)', (1,2,payload,digest))
    return conn


def test_user_sees_only_own_allocation():
    conn = _db()
    data = user_statements(conn, 'user-a')
    assert len(data) == 1 and data[0]['contribution_cents'] == 100
    assert 'user-b' not in str(data)
    assert user_statements(conn, 'unknown') == []


def test_tampered_statement_fails_closed():
    conn = _db()
    conn.execute("UPDATE nc_period_statements SET statement_json='{}'")
    with pytest.raises(ValueError):
        user_statements(conn, 'user-a')


def test_invalid_statement_total_fails_closed():
    conn = _db()
    row = conn.execute('SELECT statement_json FROM nc_period_statements').fetchone()
    content = json.loads(row[0]); content['total_draft_cents'] = 999
    payload = json.dumps(content)
    conn.execute('UPDATE nc_period_statements SET statement_json=?,sha256=?',
                 (payload, hashlib.sha256(payload.encode()).hexdigest()))
    with pytest.raises(ValueError):
        user_statements(conn, 'user-a')


def test_invalid_account_id():
    with pytest.raises(ValueError):
        user_statements(_db(), '')


def test_personal_csv_contains_only_own_account():
    from app.noncommercial_statements import user_statement_csv
    result = user_statement_csv(_db(), 'user-a', start=1, end=2)
    assert result['format'] == 'csv' and result['fiscal_invoice'] is False
    assert 'user-a,800,100,EUR' in result['content']
    assert 'user-b' not in result['content']
    with pytest.raises(ValueError):
        user_statement_csv(_db(), 'user-b', start=2, end=3)


def test_personal_csv_rejects_formula_account():
    from app.noncommercial_statements import user_statement_csv
    with pytest.raises(ValueError):
        user_statement_csv(_db(), '=1+1', start=1, end=2)
