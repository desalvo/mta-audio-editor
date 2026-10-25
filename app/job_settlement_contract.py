"""Freeze which accounting contract a newly admitted AI ledger job must settle.

A metered non-commercial invoice is not a credit-wallet subscription contract.
Legacy jobs without this admission snapshot retain the conservative old check.
"""
from .regime_operation_fence import FenceBlocked


def snapshot(c,job_id,*,resource_required):
    if not c.in_transaction:raise FenceBlocked('Accounting snapshot requires admission transaction')
    c.execute('''CREATE TABLE IF NOT EXISTS ai_job_settlement_requirements(
      job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,
      resource_contract_required INTEGER NOT NULL CHECK(resource_contract_required IN (0,1)))''')
    c.execute('INSERT INTO ai_job_settlement_requirements VALUES(?,?)',(job_id,int(resource_required)))


def verify_settled(c,job_id,*,billable):
    if not billable:return
    has_contracts=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='resource_job_contracts'").fetchone()
    contract=c.execute('SELECT settled FROM resource_job_contracts WHERE job_id=?',(job_id,)).fetchone() if has_contracts else None
    if contract is not None:
        if contract[0]!=1:raise FenceBlocked('Billable worker accounting is not settled')
        return
    has_snapshot=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_job_settlement_requirements'").fetchone()
    required=c.execute('SELECT resource_contract_required FROM ai_job_settlement_requirements WHERE job_id=?',(job_id,)).fetchone() if has_snapshot else None
    if required is None or required[0]!=0:raise FenceBlocked('Billable worker accounting settlement cannot be verified')
