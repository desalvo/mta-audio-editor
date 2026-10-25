"""Enroll metered AI jobs in the same SQLite transaction as their ledger row.

This protects the billing ledger, not independent schedulers or external workers.
Those still require their own admission integration before enabling transitions.
"""
from __future__ import annotations

from . import auth
from .regime_operation_fence import FenceBlocked, admit, initialize, settle
from .service_regime import read_regime


def enroll_metered_job(connection, ledger_id: str) -> dict:
    """Require BEGIN IMMEDIATE and a matching persisted regime revision."""
    if not connection.in_transaction:
        raise FenceBlocked('Metered job admission requires transaction')
    configured = read_regime(auth.data_root() / 'service-regime.json')
    initialize(connection, initial_regime=configured.regime.value)
    state = connection.execute(
        'SELECT regime,revision FROM regime_fence_state WHERE singleton=1'
    ).fetchone()
    if tuple(state) != (configured.regime.value, configured.revision):
        raise FenceBlocked('Metered job regime revision mismatch')
    return admit(connection, f'job:ledger:{ledger_id}', 'job')


def settle_metered_job(connection, ledger_id: str) -> None:
    """Settle enrolled ledger job in the same transaction as final metering."""
    from .worker_cgroup_recovery import require_quiescent
    require_quiescent(connection, ledger_id)
    if not connection.in_transaction:
        raise FenceBlocked('Metered job settlement requires transaction')
    op_id = f'job:ledger:{ledger_id}'
    table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='regime_fence_operations'").fetchone()
    if table is None:
        return
    exists = connection.execute('SELECT 1 FROM regime_fence_operations WHERE operation_id=?', (op_id,)).fetchone()
    if exists is not None:
        # Never settle a ledger obligation while another process still owns
        # its execution. Historic jobs without claims remain compatible.
        claims_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='regime_worker_claims'"
        ).fetchone()
        if claims_table:
            claim_row = connection.execute(
                'SELECT state,regime,revision FROM regime_worker_claims WHERE operation_id=?',
                (op_id,)
            ).fetchone()
            if claim_row is not None:
                fence = connection.execute(
                    'SELECT regime,revision,kind,status FROM regime_fence_operations WHERE operation_id=?',
                    (op_id,)
                ).fetchone()
                if claim_row[0] != 'finished':
                    raise FenceBlocked('Cannot settle ledger job with an active worker claim')
                # Internal settlement still needs the original receipt to
                # belong to the current epoch; a released claim alone is not
                # permission to close an old open fence after epoch drift.
                from .regime_worker_claims import verify_owner
                owner = connection.execute(
                    'SELECT worker_id,claim_token FROM regime_worker_claims WHERE operation_id=?',
                    (op_id,)).fetchone()
                verify_owner(connection, op_id, worker_id=owner[0], token=owner[1], allow_finished=True)
                if (fence is None or fence[2] != 'job'
                        or fence[3] != 'open' or tuple(claim_row[1:]) != tuple(fence[:2])):
                    raise FenceBlocked('Worker claim has not completed consistently with the original fence')
                # A finished claim alone is never evidence that its metered job
                # completed.  Refuse a forged or prematurely released claim.
                try:
                    ledger = connection.execute(
                        'SELECT status,billable FROM ai_compute_jobs WHERE id=?', (ledger_id,)
                    ).fetchone()
                except Exception as exc:
                    raise FenceBlocked('Worker ledger cannot be verified') from exc
                if ledger is None or ledger[0] not in (
                    'done', 'completed', 'success', 'succeeded', 'failed', 'cancelled', 'canceled', 'refunded'
                ):
                    raise FenceBlocked('Cannot settle a running or unknown worker ledger')
                from .job_settlement_contract import verify_settled
                verify_settled(connection,ledger_id,billable=ledger[1])
        settle(connection, op_id)
