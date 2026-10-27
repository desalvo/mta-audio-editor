"""Exact financial-row conservation across internal cutover commit/finalize.

This never certifies liabilities, full entry coverage or permission to switch.
Existing provider/worker readiness gates remain mandatory and blocked.
"""
import hashlib
import json
import math
import sqlite3

from .regime_operation_fence import FenceBlocked

# Fixed SQL only. Include both terms used by _balance, period/contract state,
# and immutable NC statements. Optional historical statements may be absent.
QUERIES=(
 ('ai_compute_jobs','SELECT rowid,* FROM ai_compute_jobs ORDER BY rowid',True),
 ('resource_credits','SELECT rowid,* FROM resource_credits ORDER BY rowid',True),
 ('resource_job_contracts','SELECT rowid,* FROM resource_job_contracts ORDER BY rowid',True),
 ('resource_periods','SELECT rowid,* FROM resource_periods ORDER BY rowid',True),
 ('resource_memberships','SELECT rowid,* FROM resource_memberships ORDER BY rowid',True),
 ('resource_job_budgets','SELECT rowid,* FROM resource_job_budgets ORDER BY rowid',True),
 ('resource_spending_pools','SELECT rowid,* FROM resource_spending_pools ORDER BY rowid',True),
 ('resource_plan_charges','SELECT rowid,* FROM resource_plan_charges ORDER BY rowid',True),
 ('resource_storage_debits','SELECT rowid,* FROM resource_storage_debits ORDER BY rowid',True),
 ('resource_contract_amendments','SELECT rowid,* FROM resource_contract_amendments ORDER BY rowid',True),
 ('resource_contract_terminations','SELECT rowid,* FROM resource_contract_terminations ORDER BY rowid',True),
 ('resource_plans','SELECT rowid,* FROM resource_plans ORDER BY rowid',True),
 ('resource_next_plans','SELECT rowid,* FROM resource_next_plans ORDER BY rowid',True),
 ('resource_user_policy','SELECT rowid,* FROM resource_user_policy ORDER BY rowid',True),
 ('resource_policy_events','SELECT rowid,* FROM resource_policy_events ORDER BY rowid',True),
 ('resource_storage_unlocks','SELECT rowid,* FROM resource_storage_unlocks ORDER BY rowid',True),
 ('nc_period_statements','SELECT rowid,* FROM nc_period_statements ORDER BY rowid',False),
)


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def cell(value):
    if value is None:return ['null']
    if type(value) is int:return ['integer',str(value)]
    if type(value) is float and math.isfinite(value):return ['real',value.hex()]
    if isinstance(value,str):return ['text',value]
    if isinstance(value,bytes):return ['blob',value.hex()]
    raise FenceBlocked('Unverifiable financial value')


def snapshot(connection):
    if not connection.in_transaction:raise FenceBlocked('Financial snapshot requires a write transaction')
    result={}
    for name,query,required in QUERIES:
        schema=connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone()
        if not schema:
            if required:raise FenceBlocked('Financial schema unavailable: '+name)
            result[name]={'present':False};continue
        digest=hashlib.sha256();cursor=connection.execute(query)
        digest.update(encode([column[0] for column in cursor.description]).encode())
        count=0
        for row in cursor:
            raw=encode([cell(value) for value in row]).encode()
            digest.update(len(raw).to_bytes(8,'big'));digest.update(raw);count+=1
        result[name]={'present':True,'schema_sha256':hashlib.sha256(schema[0].encode()).hexdigest(),
                      'rows':count,'rows_sha256':digest.hexdigest()}
    return {'schema':'mta-balance-continuity-1','tables':result}


def _initialize(connection):
    connection.execute('''CREATE TABLE IF NOT EXISTS regime_balance_continuity(
        transition_id TEXT PRIMARY KEY,snapshot_json TEXT NOT NULL,snapshot_sha256 TEXT NOT NULL)''')
    connection.execute('''CREATE TRIGGER IF NOT EXISTS regime_balance_continuity_update
        BEFORE UPDATE ON regime_balance_continuity BEGIN SELECT RAISE(ABORT,'Immutable financial continuity'); END''')
    connection.execute('''CREATE TRIGGER IF NOT EXISTS regime_balance_continuity_delete
        BEFORE DELETE ON regime_balance_continuity BEGIN SELECT RAISE(ABORT,'Immutable financial continuity'); END''')


def verify(connection,transition_id):
    try:row=connection.execute('SELECT snapshot_json,snapshot_sha256 FROM regime_balance_continuity WHERE transition_id=?',(transition_id,)).fetchone()
    except sqlite3.DatabaseError as exc:
        raise FenceBlocked('Original financial continuity receipt unavailable') from exc
    if not row or hashlib.sha256(row[0].encode()).hexdigest()!=row[1]:
        raise FenceBlocked('Original financial continuity receipt missing or changed')
    if encode(snapshot(connection))!=row[0]:raise FenceBlocked('Financial balances or periods changed during cutover')
    return {'verified':True,'snapshot_sha256':row[1],'financial_records_mutated':False}


def commit_preserving_balances(connection,*,transition_id,expected_revision,readiness_check):
    """Internal DB half only; caller owns BEGIN IMMEDIATE and rollback on error."""
    before=encode(snapshot(connection));_initialize(connection)
    from .regime_cutover_atomic import commit_reserved_database_cutover
    result=commit_reserved_database_cutover(connection,transition_id=transition_id,
        expected_revision=expected_revision,readiness_check=readiness_check)
    if encode(snapshot(connection))!=before:raise FenceBlocked('Financial mutation during cutover refused')
    connection.execute('INSERT INTO regime_balance_continuity VALUES(?,?,?)',
                       (transition_id,before,hashlib.sha256(before.encode()).hexdigest()))
    return result|verify(connection,transition_id)


def finalize_preserving_balances(connection,*,mirror_path,transition_id,readiness_check):
    verify(connection,transition_id)
    from .regime_cutover_finalize import finalize_cutover
    result=finalize_cutover(connection,mirror_path=mirror_path,transition_id=transition_id,
                            readiness_check=readiness_check)
    return result|verify(connection,transition_id)
