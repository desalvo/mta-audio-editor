"""Immutable non-commercial period statements. This never posts a charge.

Statements preserve the measured allocation and the administrator-declared cost
basis for independent review. They are NOT invoices or proof of actual payment.
"""
from __future__ import annotations

import hashlib
import csv
import io
import json
import sqlite3
from .noncommercial_allocation import preview_from_metered_jobs


def _canonical(record):
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def create_statement(connection: sqlite3.Connection, *, start: int, end: int,
                     documented_cost_cents: int, recovered_cents: int = 0,
                     operator_cost_exclusion_confirmed: bool = False) -> dict:
    """Create once, atomically, rejecting overlapping periods and prior reposts.

    Caller must authorize administration and enforce NON_COMMERCIAL mode.
    The transaction must be exclusive of ledger writes to prevent TOCTOU.
    """
    connection.execute('BEGIN IMMEDIATE')
    try:
        connection.execute('''CREATE TABLE IF NOT EXISTS nc_period_statements (
            period_start INTEGER NOT NULL, period_end INTEGER NOT NULL,
            statement_json TEXT NOT NULL, sha256 TEXT NOT NULL,
            PRIMARY KEY(period_start, period_end),
            CHECK(period_end > period_start))''')
        from .noncommercial_period_guard import install_closed_period_guards
        install_closed_period_guards(connection)
        existing = connection.execute('''SELECT 1 FROM nc_period_statements
            WHERE period_start < ? AND period_end > ? LIMIT 1''', (end, start)).fetchone()
        if existing:
            raise ValueError('Overlapping or previously closed period')
        draft = preview_from_metered_jobs(connection, start=start, end=end,
                documented_cost_cents=documented_cost_cents,
                recovered_cents=recovered_cents,operator_cost_exclusion_confirmed=operator_cost_exclusion_confirmed)
        # A statement is a frozen allocation, not an invoice or settlement.
        record = {**draft, 'draft': False, 'statement_type': 'NON_COMMERCIAL_ALLOCATION',
                  'posting_enabled': False, 'payments_collected': False,
                  'recoverable_amount_verified_externally': False}
        payload = _canonical(record)
        digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        connection.execute('''INSERT INTO nc_period_statements
          (period_start, period_end, statement_json, sha256) VALUES (?,?,?,?)''',
          (start, end, payload, digest))
        connection.commit()
        return {**record, 'sha256': digest}
    except BaseException:
        connection.rollback()
        raise


def list_statements(connection: sqlite3.Connection) -> list[dict]:
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nc_period_statements'").fetchone():
        return []
    result = []
    for period_start, period_end, payload, digest in connection.execute('''SELECT period_start, period_end, statement_json, sha256 FROM nc_period_statements
                                               ORDER BY period_start'''):
        if hashlib.sha256(payload.encode('utf-8')).hexdigest() != digest:
            raise ValueError('Tampered non-commercial statement')
        item = json.loads(payload)
        if (not isinstance(item, dict) or item.get('start') != period_start
                or item.get('end') != period_end
                or item.get('statement_type') != 'NON_COMMERCIAL_ALLOCATION'
                or item.get('posting_enabled') is not False):
            raise ValueError('Inconsistent non-commercial statement')
        result.append({**item, 'sha256': digest})
    return result


def export_statement(connection: sqlite3.Connection, *, start: int, end: int) -> dict:
    """Export a hash-verified frozen statement; never create an invoice or charge."""
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError('Invalid statement period')
    matches = [record for record in list_statements(connection)
               if record['start'] == start and record['end'] == end]
    if len(matches) != 1:
        raise ValueError('Statement not found or ambiguous')
    return matches[0]


def export_statement_csv(connection: sqlite3.Connection, *, start: int, end: int, language: str='en') -> dict:
    """Export a verified, non-fiscal CSV preserving the frozen statement digest."""
    record = export_statement(connection, start=start, end=end)
    shares = record.get('contribution_cents')
    usage = record.get('measured_milliseconds')
    if not isinstance(shares, dict) or not isinstance(usage, dict) or set(shares) != set(usage):
        raise ValueError('Inconsistent statement allocations')
    if any(not isinstance(k, str) or not k or type(v) is not int or v < 0
           or type(usage[k]) is not int or usage[k] < 0 for k, v in shares.items()):
        raise ValueError('Invalid statement contributions')
    if sum(shares.values()) != record.get('total_draft_cents'):
        raise ValueError('Inconsistent statement total')
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(_csv_headers(language))
    for account in sorted(shares):
        # Prevent spreadsheet formula execution when administrators open the CSV.
        if account.startswith(('=', '+', '-', '@', '\t', '\r')):
            raise ValueError('Unsafe account identifier in statement')
        writer.writerow((account, usage[account], shares[account], record['currency'], record['sha256']))
    return {'start': start, 'end': end, 'sha256': record['sha256'],
            'format': 'csv', 'fiscal_invoice': False, 'content': output.getvalue()}


def user_statements(connection: sqlite3.Connection, account_id: str) -> list[dict]:
    """Privacy-preserving user view of immutable, verified NC allocations.

    No other account identifiers, shares or usage totals are exposed. This is
    a contribution statement, not evidence of an invoice or a payment.
    """
    if not isinstance(account_id, str) or not account_id or len(account_id) > 200:
        raise ValueError('Invalid account identity')
    result = []
    for statement in list_statements(connection):
        shares = statement.get('contribution_cents')
        usage = statement.get('measured_milliseconds')
        if not isinstance(shares, dict) or not isinstance(usage, dict) or set(shares) != set(usage):
            raise ValueError('Inconsistent statement allocations')
        if any(type(v) is not int or v < 0 for v in shares.values()) or any(
            type(v) is not int or v < 0 for v in usage.values()
        ):
            raise ValueError('Invalid statement amounts')
        if sum(shares.values()) != statement.get('total_draft_cents'):
            raise ValueError('Inconsistent statement total')
        if account_id not in shares:
            continue
        result.append({
            'start': statement['start'], 'end': statement['end'],
            'account_id': account_id,
            'measured_milliseconds': usage[account_id],
            'contribution_cents': shares[account_id],
            'currency': statement['currency'], 'sha256': statement['sha256'],
            'statement_type': 'NON_COMMERCIAL_ALLOCATION',
            'fiscal_invoice': False, 'payments_collected': False,
        })
    return result


def user_statement_csv(connection: sqlite3.Connection, account_id: str, *, start: int, end: int, language: str='en') -> dict:
    """Verified one-account CSV with no cross-account details or active formulas."""
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError('Invalid statement period')
    matches = [item for item in user_statements(connection, account_id)
               if item['start'] == start and item['end'] == end]
    if len(matches) != 1:
        raise ValueError('Personal statement unavailable')
    item = matches[0]
    if account_id.startswith(('=', '+', '-', '@', '\t', '\r')):
        raise ValueError('Unsafe account identifier in export')
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(_csv_headers(language))
    writer.writerow((account_id, item['measured_milliseconds'], item['contribution_cents'],
                     item['currency'], item['sha256']))
    return {'start': start, 'end': end, 'sha256': item['sha256'],
            'format': 'csv', 'fiscal_invoice': False, 'content': output.getvalue()}


def _csv_headers(language):
    if language=='en':return ('account_id','measured_milliseconds','contribution_cents','currency','statement_sha256')
    if language=='it':return ('id_account','millisecondi_misurati','contributo_centesimi','valuta','sha256_consuntivo')
    raise ValueError('Unsupported statement export language')
