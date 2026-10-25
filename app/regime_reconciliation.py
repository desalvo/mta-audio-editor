"""Fail-closed reconciliation inventory for service-regime switching.

This is a read-only inventory. A historical financial row is not a zero balance;
reconciliation needs an independently verified settlement before any switch.
"""
from __future__ import annotations

import sqlite3

# Names and query predicates are fixed source literals, not user supplied SQL.
_INVENTORY = {
    'active_jobs': ('ai_compute_jobs', "SELECT COUNT(*) FROM ai_compute_jobs WHERE status NOT IN ('done','completed','success','succeeded','failed','cancelled','canceled','refunded')"),
    'unsettled_jobs': ('resource_job_contracts', 'SELECT COUNT(*) FROM resource_job_contracts WHERE settled=0'),
    'subscriptions': ('resource_memberships', "SELECT COUNT(*) FROM resource_memberships WHERE plan IS NOT NULL AND plan != ''"),
    'credit_movements': ('resource_credits', 'SELECT COUNT(*) FROM resource_credits WHERE 1=1'),
    'pending_stripe_orders': ('credit_purchase_orders', "SELECT COUNT(*) FROM credit_purchase_orders WHERE status NOT IN ('refunded','cancelled','canceled','failed')"),
    'pending_paypal_orders': ('paypal_orders', "SELECT COUNT(*) FROM paypal_orders WHERE status NOT IN ('refunded','cancelled','canceled','failed')"),
    'subscription_charges': ('resource_plan_charges', 'SELECT COUNT(*) FROM resource_plan_charges WHERE 1=1'),
    'storage_unlocks': ('resource_storage_unlocks', 'SELECT COUNT(*) FROM resource_storage_unlocks WHERE 1=1'),
    'spending_pools': ('resource_spending_pools', 'SELECT COUNT(*) FROM resource_spending_pools WHERE 1=1'),
}

def inventory(connection: sqlite3.Connection) -> dict:
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    result = {}
    for name, (table, query) in _INVENTORY.items():
        if table not in tables:
            result[name] = {'state': 'unknown_schema', 'count': None}
            continue
        try:
            n = connection.execute(query).fetchone()[0]
        except sqlite3.DatabaseError:
            result[name] = {'state': 'unknown_schema', 'count': None}
            continue
        # Historic movements must be preserved, but are not necessarily unsettled.
        state = 'needs_reconciliation' if n else 'clear'
        result[name] = {'state': state, 'count': n}
    return result

def readiness_report(connection: sqlite3.Connection, *, current: str, target: str) -> dict:
    """Conservative machine-readable operator checklist, without mutating money."""
    if current not in ('NON_COMMERCIAL', 'COMMERCIAL') or target not in ('NON_COMMERCIAL', 'COMMERCIAL'):
        raise ValueError('Unknown regime')
    details = inventory(connection)
    unresolved = sorted(name for name, item in details.items() if item['state'] != 'clear')
    return {'current': current, 'target': target, 'inventory': details,
            'unresolved': unresolved, 'ready_for_automatic_transition': False,
            'reason': 'Atomic payment/webhook reconciliation and service-wide job fencing are not implemented',
            'preserves_historical_records': True}


def combined_readiness(connection: sqlite3.Connection, *, current: str, target: str) -> dict:
    """Reconcile legacy financial inventory with the persistent operation fence.

    Never treat a missing fence or unsynchronized regime as a clean database.
    This diagnostic is read-only and deliberately cannot authorize switching.
    """
    from .regime_operation_fence import inspect, audit_unfenced_metered_jobs, FenceBlocked
    base = readiness_report(connection, current=current, target=target)
    try:
        fence = inspect(connection)
    except (FenceBlocked, sqlite3.DatabaseError):
        fence = None
    from .regime_outbox_review import audit_checkout_integrity
    try:
        checkout_integrity = audit_checkout_integrity(connection)
    except (FenceBlocked, sqlite3.DatabaseError):
        checkout_integrity = {'verified': False, 'inconsistencies': {'schema_unavailable': 1},
                              'outstanding_dispatches': None, 'transition_safe': False}
    from .regime_inbox_coverage import audit_provider_inbox
    inbox_coverage = audit_provider_inbox(connection)
    metered_coverage = audit_unfenced_metered_jobs(connection)
    from .regime_worker_claims import inspect_claims, audit_claim_integrity
    worker_claims = inspect_claims(connection)
    claim_integrity = audit_claim_integrity(connection)
    from .ai_pull_coordinator import inspect_state as inspect_pull_state
    pull_execution = inspect_pull_state(connection)
    from .regime_financial_evidence import audit_observations
    financial_evidence = audit_observations(connection)
    from .payment_reconciliation import report as payment_report
    try:
        payment_events=payment_report(connection)
    except sqlite3.DatabaseError:
        payment_events={'verified':False,'pending':None,'issues':['schema_unavailable'],'transition_safe':False}
    reasons = list(base['unresolved'])
    if not pull_execution['verified']:
        reasons.append('pull_execution_integrity_unverified')
    if pull_execution['pending'] is None or pull_execution['pending']:
        reasons.append('pull_execution_pending')
    from .operator_refunds import audit as refund_audit
    operator_refunds=refund_audit(connection)
    if not operator_refunds['verified']:reasons.append('operator_refund_journal_unverifiable')
    if operator_refunds['pending'] is None or operator_refunds['pending']:reasons.append('operator_refunds_pending')
    from .worker_loss_resolution import audit as loss_audit
    operator_losses=loss_audit(connection)
    if not operator_losses['verified']:reasons.append('operator_loss_journal_unverifiable')
    from .worker_cgroup_recovery import report as worker_process_report
    worker_processes=worker_process_report(connection)
    if not worker_processes['verified']:reasons.append('worker_process_journal_unverifiable')
    if worker_processes['pending'] is None or worker_processes['pending']:reasons.append('worker_process_quiescence_pending')
    from .noncommercial_contributions import audit as nc_audit
    nc_collection=nc_audit(connection)
    if not nc_collection['verified']:reasons.append('nc_collection_unverifiable')
    if nc_collection['pending'] is None or nc_collection['pending']:reasons.append('nc_contributions_pending')
    if nc_collection['refund_due_cents'] is None or nc_collection['refund_due_cents']:reasons.append('nc_contribution_refunds_outstanding')
    if not payment_events['verified']:
        reasons.append('payment_ledger_unverifiable')
    if payment_events['pending'] is None or payment_events['pending']:
        reasons.append('authenticated_payment_events_pending')
    if payment_events.get('subscription_reversal_due_micro',0) or payment_events.get('subscription_risk_micro',0):
        reasons.append('subscription_reversals_outstanding')
    if payment_events.get('subscription_repayment_refund_due_micro',0):
        reasons.append('subscription_repayment_refunds_outstanding')
    if payment_events.get('active_disputes',0):
        reasons.append('provider_disputes_active')
    if not financial_evidence['verified']:
        reasons.append('financial_evidence_unverifiable')
    if not inbox_coverage['verified']:
        reasons.append('provider_inbox_unverifiable')
    if inbox_coverage['pending'] is None or inbox_coverage['pending']:
        reasons.append('provider_events_pending')
    if not checkout_integrity['verified']:
        reasons.append('checkout_outbox_integrity_failed')
    if checkout_integrity['outstanding_dispatches'] is None or checkout_integrity['outstanding_dispatches']:
        reasons.append('checkout_dispatches_require_reconciliation')
    if not claim_integrity['safe']:
        reasons.append('worker_claim_integrity_unverified')
    if not worker_claims['verified']:
        reasons.append('worker_claims_schema_unavailable')
    elif worker_claims['running']:
        reasons.append('worker_claims_running')
    if not metered_coverage['verified']:
        reasons.append('metered_job_coverage_unverifiable')
    elif metered_coverage['unfenced_count']:
        reasons.append('active_metered_jobs_not_fenced')
    if fence is None:
        reasons.append('operation_fence_missing')
    else:
        if fence['regime'] != current:
            reasons.append('operation_fence_regime_drift')
        if fence['transitioning']:
            reasons.append('transition_already_pending')
        if any(fence['open_by_kind'].values()):
            reasons.append('operations_pending')
        if not fence['all_entry_points_instrumented']:
            reasons.append('entry_points_not_instrumented')
    return {**base, 'fence': fence, 'metered_job_coverage': metered_coverage, 'worker_claims': worker_claims, 'worker_claim_integrity': claim_integrity, 'checkout_integrity': checkout_integrity, 'provider_inbox_coverage': inbox_coverage, 'financial_evidence': financial_evidence, 'payment_event_reconciliation':payment_events,
            'pull_execution':pull_execution,'noncommercial_collection':nc_collection,'operator_refunds':operator_refunds,'worker_processes':worker_processes,'operator_losses':operator_losses,'unresolved': sorted(set(reasons)),
            'ready_for_automatic_transition': False}
