"""Exact, deliberately restricted maintenance eligibility for a local authority.

Unknown/provider/worker histories are refusals, not empty balances. This profile
can carry operator-issued credits, free subscription periods and verified NC
statements. It cannot certify a merchant account or adopt a historical worker.
The broad online/distributed reconciliation diagnostic remains separate.
"""
from contextlib import closing
import hashlib
import json
import os
import sqlite3

from . import resource_accounts
from .regime_balance_continuity import snapshot, encode
from .regime_operation_fence import FenceBlocked
from .regime_service_lease import enabled

LOCAL_TABLES = frozenset('''resource_config resource_plans resource_memberships
 resource_cancellations resource_periods resource_credits resource_storage_samples
 resource_storage_unlocks resource_notices resource_user_policy resource_policy_events
 resource_trial_uses resource_next_plans resource_quota_events resource_storage_debits
 resource_credit_service_events resource_contract_amendments resource_contract_terminations
 resource_plan_charges resource_spending_pools'''.split())
REQUIRED = frozenset('''credit_payment_config credit_purchase_orders credit_payment_events
 paypal_config paypal_orders paypal_captures paypal_refunds paypal_events
 payment_reconciliation_events payment_reconciliation_positions
 payment_reconciliation_movements payment_reconciliation_disputes
 payment_reconciliation_objects account_lifecycle account_purge_jobs'''.split())
PREFIXES = ('resource_', 'paypal_', 'credit_payment_', 'credit_purchase_',
            'payment_', 'subscription_', 'nc_contribution_', 'operator_refund',
            'worker_', 'ai_',
            'regime_provider_', 'regime_financial_', 'regime_payment_')
CONFIGS = frozenset({'credit_payment_config', 'paypal_config', 'nc_contribution_settings'})
REVIEWED_JOB_TABLES = frozenset('''ai_compute_jobs ai_job_hardware_snapshots
 ai_job_license_snapshots ai_job_settlement_requirements ai_job_billing_exemptions ai_compute_job_diagnostics
 resource_job_contracts resource_job_budgets resource_job_modes'''.split())


# Fixed, source-reviewed SQL only. New financial schemas require an explicit review.
_KNOWN_SCHEMAS = frozenset('regime_reservation_aborts account_action_confirmations account_archives account_audit account_email_mfa account_enroll_attempts account_identity_reservations account_lifecycle account_mail_outbox account_purge_jobs account_retention_config account_sandboxes ai_access_tokens ai_billing_periods ai_billing_schedules ai_compute_job_diagnostics ai_compute_jobs ai_device_requests ai_gpu_diagnostics ai_gpu_energy_calibrations ai_gpu_evidence_claims ai_gpu_slot_leases ai_gpu_slot_quotes ai_job_billing_exemptions ai_job_disposition_audit ai_job_dispositions ai_job_hardware_snapshots ai_job_license_snapshots ai_job_settlement_requirements ai_mail_config ai_mail_events ai_mail_preferences ai_metering_evidence ai_persistent_storage_samples ai_pull_acknowledgements ai_pull_deferred_admissions ai_pull_model_requirements ai_pull_nodes ai_pull_operator_audit ai_pull_publication_intents ai_pull_state ai_pull_tasks ai_remote_job_bindings ai_request_dedup ai_resource_price_history ai_resource_prices ai_trusted_estimate_evidence ai_usage_events ai_user_billing_settings ai_verified_gpu_evidence application_preferences checkout_terminal_receipts credit_payment_config credit_payment_events credit_purchase_orders deliveries editor_layout_preferences email_tokens job_ui_state job_ui_viewers jobs legal_instance_config legal_instance_history model_access_tokens nc_contribution_events nc_contribution_intents nc_contribution_settings nc_period_statements oauth_nonces operator_refund_audit operator_refunds payment_reconciliation_disputes payment_reconciliation_events payment_reconciliation_movements payment_reconciliation_objects payment_reconciliation_positions paypal_captures paypal_config paypal_events paypal_financial_holds paypal_merchant_history paypal_orders paypal_refunds paypal_subscription_reversals planning_jobs publications regime_admin_cutover_events regime_admin_cutovers regime_balance_continuity regime_cutover_commits regime_cutover_finalizations regime_fence_operations regime_fence_state regime_financial_evidence regime_payment_outbox regime_provider_inbox regime_transition_journal regime_worker_claims resource_cancellations resource_config resource_contract_amendments resource_contract_terminations resource_credit_service_events resource_credits resource_job_budgets resource_job_contracts resource_job_modes resource_memberships resource_next_plans resource_notices resource_periods resource_plan_charges resource_plans resource_policy_events resource_quota_events resource_spending_pools resource_storage_debits resource_storage_samples resource_storage_unlocks resource_trial_uses resource_user_policy sessions settings smtp_config social_identities social_login_settings social_totp_challenges sqlite_sequence subscription_payment_basis subscription_repayment_allocations subscription_repayment_targets terminal_receipts users worker_cgroup_receipts worker_cgroup_scopes worker_loss_resolutions'.split())

_ROW_QUERIES = {
    'ai_access_tokens': 'SELECT 1 FROM "ai_access_tokens" LIMIT 1',
    'ai_billing_periods': 'SELECT 1 FROM "ai_billing_periods" LIMIT 1',
    'ai_billing_schedules': 'SELECT 1 FROM "ai_billing_schedules" LIMIT 1',
    'ai_compute_job_diagnostics': 'SELECT 1 FROM "ai_compute_job_diagnostics" LIMIT 1',
    'ai_compute_jobs': 'SELECT 1 FROM "ai_compute_jobs" LIMIT 1',
    'ai_device_requests': 'SELECT 1 FROM "ai_device_requests" LIMIT 1',
    'ai_gpu_diagnostics': 'SELECT 1 FROM "ai_gpu_diagnostics" LIMIT 1',
    'ai_gpu_energy_calibrations': 'SELECT 1 FROM "ai_gpu_energy_calibrations" LIMIT 1',
    'ai_gpu_evidence_claims': 'SELECT 1 FROM "ai_gpu_evidence_claims" LIMIT 1',
    'ai_gpu_slot_leases': 'SELECT 1 FROM "ai_gpu_slot_leases" LIMIT 1',
    'ai_gpu_slot_quotes': 'SELECT 1 FROM "ai_gpu_slot_quotes" LIMIT 1',
    'ai_job_billing_exemptions': 'SELECT 1 FROM "ai_job_billing_exemptions" LIMIT 1',
    'ai_job_disposition_audit': 'SELECT 1 FROM "ai_job_disposition_audit" LIMIT 1',
    'ai_job_dispositions': 'SELECT 1 FROM "ai_job_dispositions" LIMIT 1',
    'ai_job_hardware_snapshots': 'SELECT 1 FROM "ai_job_hardware_snapshots" LIMIT 1',
    'ai_job_license_snapshots': 'SELECT 1 FROM "ai_job_license_snapshots" LIMIT 1',
    'ai_job_settlement_requirements': 'SELECT 1 FROM "ai_job_settlement_requirements" LIMIT 1',
    'ai_mail_config': 'SELECT 1 FROM "ai_mail_config" LIMIT 1',
    'ai_mail_events': 'SELECT 1 FROM "ai_mail_events" LIMIT 1',
    'ai_mail_preferences': 'SELECT 1 FROM "ai_mail_preferences" LIMIT 1',
    'ai_metering_evidence': 'SELECT 1 FROM "ai_metering_evidence" LIMIT 1',
    'ai_persistent_storage_samples': 'SELECT 1 FROM "ai_persistent_storage_samples" LIMIT 1',
    'ai_pull_acknowledgements': 'SELECT 1 FROM "ai_pull_acknowledgements" LIMIT 1',
    'ai_pull_deferred_admissions': 'SELECT 1 FROM "ai_pull_deferred_admissions" LIMIT 1',
    'ai_pull_model_requirements': 'SELECT 1 FROM "ai_pull_model_requirements" LIMIT 1',
    'ai_pull_nodes': 'SELECT 1 FROM "ai_pull_nodes" LIMIT 1',
    'ai_pull_operator_audit': 'SELECT 1 FROM "ai_pull_operator_audit" LIMIT 1',
    'ai_pull_publication_intents': 'SELECT 1 FROM "ai_pull_publication_intents" LIMIT 1',
    'ai_pull_state': 'SELECT 1 FROM "ai_pull_state" LIMIT 1',
    'ai_pull_tasks': 'SELECT 1 FROM "ai_pull_tasks" LIMIT 1',
    'ai_remote_job_bindings': 'SELECT 1 FROM "ai_remote_job_bindings" LIMIT 1',
    'ai_request_dedup': 'SELECT 1 FROM "ai_request_dedup" LIMIT 1',
    'ai_resource_price_history': 'SELECT 1 FROM "ai_resource_price_history" LIMIT 1',
    'ai_resource_prices': 'SELECT 1 FROM "ai_resource_prices" LIMIT 1',
    'ai_trusted_estimate_evidence': 'SELECT 1 FROM "ai_trusted_estimate_evidence" LIMIT 1',
    'ai_usage_events': 'SELECT 1 FROM "ai_usage_events" LIMIT 1',
    'ai_user_billing_settings': 'SELECT 1 FROM "ai_user_billing_settings" LIMIT 1',
    'ai_verified_gpu_evidence': 'SELECT 1 FROM "ai_verified_gpu_evidence" LIMIT 1',
    'credit_payment_config': 'SELECT 1 FROM "credit_payment_config" LIMIT 1',
    'credit_payment_events': 'SELECT 1 FROM "credit_payment_events" LIMIT 1',
    'credit_purchase_orders': 'SELECT 1 FROM "credit_purchase_orders" LIMIT 1',
    'nc_contribution_events': 'SELECT 1 FROM "nc_contribution_events" LIMIT 1',
    'nc_contribution_intents': 'SELECT 1 FROM "nc_contribution_intents" LIMIT 1',
    'nc_contribution_settings': 'SELECT 1 FROM "nc_contribution_settings" LIMIT 1',
    'operator_refund_audit': 'SELECT 1 FROM "operator_refund_audit" LIMIT 1',
    'operator_refunds': 'SELECT 1 FROM "operator_refunds" LIMIT 1',
    'payment_reconciliation_disputes': 'SELECT 1 FROM "payment_reconciliation_disputes" LIMIT 1',
    'payment_reconciliation_events': 'SELECT 1 FROM "payment_reconciliation_events" LIMIT 1',
    'payment_reconciliation_movements': 'SELECT 1 FROM "payment_reconciliation_movements" LIMIT 1',
    'payment_reconciliation_objects': 'SELECT 1 FROM "payment_reconciliation_objects" LIMIT 1',
    'payment_reconciliation_positions': 'SELECT 1 FROM "payment_reconciliation_positions" LIMIT 1',
    'paypal_captures': 'SELECT 1 FROM "paypal_captures" LIMIT 1',
    'paypal_config': 'SELECT 1 FROM "paypal_config" LIMIT 1',
    'paypal_events': 'SELECT 1 FROM "paypal_events" LIMIT 1',
    'paypal_financial_holds': 'SELECT 1 FROM "paypal_financial_holds" LIMIT 1',
    'paypal_merchant_history': 'SELECT 1 FROM "paypal_merchant_history" LIMIT 1',
    'paypal_orders': 'SELECT 1 FROM "paypal_orders" LIMIT 1',
    'paypal_refunds': 'SELECT 1 FROM "paypal_refunds" LIMIT 1',
    'paypal_subscription_reversals': 'SELECT 1 FROM "paypal_subscription_reversals" LIMIT 1',
    'regime_financial_evidence': 'SELECT 1 FROM "regime_financial_evidence" LIMIT 1',
    'regime_payment_outbox': 'SELECT 1 FROM "regime_payment_outbox" LIMIT 1',
    'regime_provider_inbox': 'SELECT 1 FROM "regime_provider_inbox" LIMIT 1',
    'resource_cancellations': 'SELECT 1 FROM "resource_cancellations" LIMIT 1',
    'resource_config': 'SELECT 1 FROM "resource_config" LIMIT 1',
    'resource_contract_amendments': 'SELECT 1 FROM "resource_contract_amendments" LIMIT 1',
    'resource_contract_terminations': 'SELECT 1 FROM "resource_contract_terminations" LIMIT 1',
    'resource_credit_service_events': 'SELECT 1 FROM "resource_credit_service_events" LIMIT 1',
    'resource_credits': 'SELECT 1 FROM "resource_credits" LIMIT 1',
    'resource_job_budgets': 'SELECT 1 FROM "resource_job_budgets" LIMIT 1',
    'resource_job_contracts': 'SELECT 1 FROM "resource_job_contracts" LIMIT 1',
    'resource_job_modes': 'SELECT 1 FROM "resource_job_modes" LIMIT 1',
    'resource_memberships': 'SELECT 1 FROM "resource_memberships" LIMIT 1',
    'resource_next_plans': 'SELECT 1 FROM "resource_next_plans" LIMIT 1',
    'resource_notices': 'SELECT 1 FROM "resource_notices" LIMIT 1',
    'resource_periods': 'SELECT 1 FROM "resource_periods" LIMIT 1',
    'resource_plan_charges': 'SELECT 1 FROM "resource_plan_charges" LIMIT 1',
    'resource_plans': 'SELECT 1 FROM "resource_plans" LIMIT 1',
    'resource_policy_events': 'SELECT 1 FROM "resource_policy_events" LIMIT 1',
    'resource_quota_events': 'SELECT 1 FROM "resource_quota_events" LIMIT 1',
    'resource_spending_pools': 'SELECT 1 FROM "resource_spending_pools" LIMIT 1',
    'resource_storage_debits': 'SELECT 1 FROM "resource_storage_debits" LIMIT 1',
    'resource_storage_samples': 'SELECT 1 FROM "resource_storage_samples" LIMIT 1',
    'resource_storage_unlocks': 'SELECT 1 FROM "resource_storage_unlocks" LIMIT 1',
    'resource_trial_uses': 'SELECT 1 FROM "resource_trial_uses" LIMIT 1',
    'resource_user_policy': 'SELECT 1 FROM "resource_user_policy" LIMIT 1',
    'subscription_payment_basis': 'SELECT 1 FROM "subscription_payment_basis" LIMIT 1',
    'subscription_repayment_allocations': 'SELECT 1 FROM "subscription_repayment_allocations" LIMIT 1',
    'subscription_repayment_targets': 'SELECT 1 FROM "subscription_repayment_targets" LIMIT 1',
    'worker_cgroup_receipts': 'SELECT 1 FROM "worker_cgroup_receipts" LIMIT 1',
    'worker_cgroup_scopes': 'SELECT 1 FROM "worker_cgroup_scopes" LIMIT 1',
    'worker_loss_resolutions': 'SELECT 1 FROM "worker_loss_resolutions" LIMIT 1',
}

_ORPHAN_QUERIES = {
    'ai_compute_job_diagnostics': 'SELECT 1 FROM ai_compute_job_diagnostics j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
    'ai_job_hardware_snapshots': 'SELECT 1 FROM "ai_job_hardware_snapshots" j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
    'ai_job_license_snapshots': 'SELECT 1 FROM "ai_job_license_snapshots" j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
    'ai_job_settlement_requirements': 'SELECT 1 FROM "ai_job_settlement_requirements" j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
    'ai_job_billing_exemptions': 'SELECT 1 FROM "ai_job_billing_exemptions" j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
    'resource_job_contracts': 'SELECT 1 FROM "resource_job_contracts" j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
    'resource_job_budgets': 'SELECT 1 FROM "resource_job_budgets" j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
    'resource_job_modes': 'SELECT 1 FROM "resource_job_modes" j LEFT JOIN ai_compute_jobs c ON c.id=j.job_id WHERE c.id IS NULL LIMIT 1',
}


def _settled_jobs(con, tables):
    jobs = con.execute('SELECT id,user_id,status,billable,queue_job_id,resource_source,usage_json FROM ai_compute_jobs').fetchall()
    from .regime_worker_claims import audit_claim_integrity
    from .worker_cgroup_recovery import require_quiescent
    from .job_settlement_contract import verify_settled
    claims = audit_claim_integrity(con) if jobs or 'regime_worker_claims' in tables else {'safe': True}
    if not claims.get('safe'):
        raise FenceBlocked('Worker claim history is not completely reconciled')
    result = {}
    for job, uid, status, billable, queued, source, usage in jobs:
        receipt = con.execute('''SELECT f.status,c.state FROM regime_fence_operations f
            JOIN regime_worker_claims c ON c.operation_id=f.operation_id
            WHERE f.operation_id=?''', ('job:ledger:' + job,)).fetchone()
        if (status not in {'done', 'failed', 'cancelled'} or tuple(receipt or ()) != ('closed', 'finished')
                or not queued or source != 'worker'):
            raise FenceBlocked('Historical or uncertain worker execution requires reconciliation')
        verify_settled(con, job, billable=billable)
        require_quiescent(con, job)
        from .ai_billing import _validate_usage
        _validate_usage(json.loads(usage))
        if queued in result:
            raise FenceBlocked('Ambiguous queue-to-ledger history')
        result[queued] = {'actor': uid, 'terminal': 'completed' if status == 'done' else status}
    for name in REVIEWED_JOB_TABLES - {'ai_compute_jobs'}:
        if name not in tables:
            continue
        if con.execute(_ORPHAN_QUERIES[name]).fetchone():
            raise FenceBlocked('Orphan historical accounting row')
    return result


def _external_queue(jobs):
    from . import ai_arranger_runtime as queue
    checks = (
        (queue._ROOT / 'jobs.sqlite3', None),
        (queue._ROOT / 'billing-outbox.sqlite3', 'SELECT COUNT(*) FROM deliveries'),
        (queue._ROOT / 'publication/outbox.sqlite3', 'SELECT COUNT(*) FROM publications'),
    )
    result = []
    for path, sql in checks:
        if not path.exists() and not path.is_symlink():
            if sql is None and jobs:
                raise FenceBlocked('Original execution journal is missing')
            result.append({'journal': path.name, 'present': False})
            continue
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise FenceBlocked('Unsafe execution journal')
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=0)) as con:
            if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise FenceBlocked('Execution history requires full worker reconciliation')
            count = 0
            if sql is None:
                observed = set()
                for key, actor, state in con.execute('SELECT job_id,actor_user_id,state FROM jobs'):
                    if key not in jobs or jobs[key] != {'actor': actor, 'terminal': state}:
                        raise FenceBlocked('Queue contains pending, legacy or unbound work')
                    receipt = con.execute('SELECT state FROM terminal_receipts WHERE job_id=?', (key,)).fetchone()
                    if not receipt or receipt[0] != state:
                        raise FenceBlocked('Original terminal queue receipt missing')
                    observed.add(key)
                    count += 1
                if observed != set(jobs):
                    raise FenceBlocked('Original execution queue history incomplete')
            elif con.execute(sql).fetchone()[0]:
                raise FenceBlocked('Deferred publication or billing history requires full reconciliation')
        result.append({'journal': path.name, 'present': True, 'rows': count})
    return result


def audit(con):
    """Caller holds exclusive service lease and BEGIN IMMEDIATE; no writes/IO to providers."""
    if not con.in_transaction:
        raise FenceBlocked('Transactional maintenance audit required')
    if not enabled() or os.getenv('MTA_NATIVE_SINGLE_USER', '').lower() in {'1', 'true', 'yes', 'on'}:
        raise FenceBlocked('Local-authority cutover is not enabled for this installation')
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if tables - _KNOWN_SCHEMAS:
        raise FenceBlocked('Unreviewed database schema prevents financial cutover')
    if not REQUIRED <= tables:
        raise FenceBlocked('Required financial schemas unavailable; provision and review them before cutover')
    if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
        raise FenceBlocked('Accounting database integrity failed')
    if con.execute('SELECT 1 FROM account_purge_jobs LIMIT 1').fetchone() or con.execute(
            "SELECT 1 FROM account_lifecycle WHERE state IN ('deleting','erasing') LIMIT 1").fetchone():
        raise FenceBlocked('Account erasure must complete before financial cutover')
    if not con.execute('''SELECT 1 FROM users u LEFT JOIN account_lifecycle l ON l.user_id=u.id
            WHERE u.role='admin' AND u.active=1 AND u.email_confirmed=1
            AND u.password_hash LIKE 'pbkdf2_sha256$%'
            AND (coalesce(l.second_factor_required,0)=0 OR (l.mfa_method='totp' AND u.totp_enabled=1)) LIMIT 1''').fetchone():
        raise FenceBlocked('Recovery requires an existing administrator with password or local TOTP authentication')
    stripe = con.execute('SELECT secret_key,webhook_secret FROM credit_payment_config WHERE id=1').fetchone()
    paypal = con.execute('SELECT enabled,client_id,client_secret,webhook_id FROM paypal_config WHERE id=1').fetchone()
    if stripe is None or paypal is None or any(stripe) or any(paypal):
        raise FenceBlocked('Configured providers require full authenticated financial reconciliation')
    if 'nc_contribution_settings' in tables:
        row = con.execute('SELECT enabled FROM nc_contribution_settings WHERE singleton=1').fetchone()
        if row is None or row[0]:
            raise FenceBlocked('Disable voluntary collection and reconcile its complete history first')
    jobs = _settled_jobs(con, tables)
    # Every row in every other financial/execution journal is an explicit
    # blocker, including unknown/new tables. Do not whitelist by terminal label.
    for name in sorted(tables):
        if name in LOCAL_TABLES or name in CONFIGS or name in REVIEWED_JOB_TABLES or name in {'ai_resource_prices', 'ai_resource_price_history'}:
            continue
        if name.startswith(PREFIXES):
            if name not in _ROW_QUERIES or con.execute(_ROW_QUERIES[name]).fetchone():
                raise FenceBlocked('Full financial/worker reconciliation required: ' + name)
    if con.execute("SELECT 1 FROM regime_fence_operations WHERE status!='closed' LIMIT 1").fetchone():
        raise FenceBlocked('Unsettled operations prevent cutover')
    if con.execute('''SELECT 1 FROM regime_fence_operations f LEFT JOIN ai_compute_jobs j
            ON f.operation_id='job:ledger:' || j.id WHERE f.kind!='job' OR j.id IS NULL LIMIT 1''').fetchone():
        raise FenceBlocked('Historical checkout or orphan operation requires full reconciliation')
    # Zero-value operator audit rows and positive, explicitly issued grants are
    # carried intact. Imported provider credits/refund adjustments never qualify.
    for identifier, uid, amount, actor, reason in con.execute(
            'SELECT id,user_id,delta_micro,actor_id,reason FROM resource_credits'):
        admin = con.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1", (actor,)).fetchone()
        if (type(amount) is not int or amount < 0 or not admin or
                (amount and not identifier.startswith('grant:')) or
                not con.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone()):
            raise FenceBlocked('Original credit basis requires independent reconciliation')
    if con.execute('SELECT 1 FROM resource_plans WHERE price_micro!=0 LIMIT 1').fetchone():
        raise FenceBlocked('Priced subscription plans require full financial cutover')
    if con.execute('SELECT 1 FROM resource_plan_charges WHERE amount_micro!=0 LIMIT 1').fetchone():
        raise FenceBlocked('Subscription obligations require full financial cutover')
    if con.execute('''SELECT 1 FROM resource_contract_terminations WHERE
            original_fee_micro!=0 OR final_fee_micro!=0 OR refund_due_micro!=0 LIMIT 1''').fetchone():
        raise FenceBlocked('Contract termination obligations require full financial cutover')
    for raw, in con.execute('SELECT limits FROM resource_next_plans'):
        limits = json.loads(raw)
        if not isinstance(limits, dict) or limits.get('price_micro', 0) != 0:
            raise FenceBlocked('Future subscription obligations require full financial cutover')
    for start, end, raw in con.execute('SELECT start,end,limits FROM resource_periods'):
        limits = json.loads(raw)
        if (type(start) is not int or type(end) is not int or end <= start or
                not isinstance(limits, dict) or limits.get('_price_micro', 0) != 0):
            raise FenceBlocked('Subscription period basis cannot be verified')
    if con.execute('SELECT 1 FROM resource_storage_debits WHERE cost_micro<0 LIMIT 1').fetchone():
        raise FenceBlocked('Invalid storage obligation')
    for uid, in con.execute('SELECT id FROM users'):
        if resource_accounts._balance(con, uid) < 0:
            raise FenceBlocked('Outstanding account debt prevents cutover')
    from .noncommercial_statements import list_statements
    statements = list_statements(con)
    queue = _external_queue(jobs)
    financial = snapshot(con)
    return {'profile': 'local-authority-no-provider-history-1',
            'financial_snapshot_sha256': hashlib.sha256(encode(financial).encode()).hexdigest(),
            'statement_hashes': [row['sha256'] for row in statements],
            'execution_journals': queue, 'provider_history': 'absent_in_verified_schemas',
            'outstanding_obligations': 0, 'preserves_historical_records': True}
