"""Private complete operator review; observations never clear financial liabilities.

Every family is audited independently over the original database snapshot. Page
limits affect displayed cases, never verification totals. The only executable
preview is obtained from the existing authoritative cutover service afterwards.
"""
import hashlib
import sqlite3

from . import auth
from .regime_balance_continuity import encode
from .regime_operation_fence import FenceBlocked
from .service_regime import Regime, read_regime


def _run(call):
    try:
        value = call()
        if not isinstance(value, dict):
            raise ValueError('Invalid audit result')
        return value
    except (FenceBlocked, sqlite3.DatabaseError, ValueError, TypeError, KeyError, OSError):
        return {'verified': False, 'pending': None, 'issues': ['audit_unavailable']}


def _section(name, data, *, counts=(), money=(), action='review', family='finance'):
    verified = data.get('verified', data.get('safe', False)) is True
    result = {'id': name, 'family': family, 'verified': verified, 'action': action,
              'counts': {}, 'amounts_micro': {}, 'issues': []}
    for key in counts:
        value = data.get(key)
        result['counts'][key] = value if type(value) is int and value >= 0 else None
    for key in money:
        value = data.get(key)
        result['amounts_micro'][key] = str(value) if type(value) is int and value >= 0 else None
    result['issues'] = [value for value in data.get('issues', [])
                        if isinstance(value, str) and len(value) <= 160][:100]
    values = [*result['counts'].values(), *result['amounts_micro'].values()]
    result['state'] = ('unverified' if not verified or any(v is None for v in values)
                       else 'pending' if any(int(v) for v in values) else 'verified')
    return result


def _claims(c):
    from .regime_worker_claims import audit_claim_integrity, inspect_claims
    integrity = audit_claim_integrity(c)
    state = inspect_claims(c)
    return {**state, 'verified': state['verified'] and integrity['safe']}


def snapshot(c, *, limit=50, offset=0):
    """Read only. No provider request, migration, dispatch, settlement or waiver."""
    from . import payment_reconciliation as payments, regime_outbox_review as outbox
    from . import regime_inbox_coverage as inbox, regime_financial_evidence as observations
    from . import subscription_basis_audit as basis, operator_refunds as refunds
    from . import worker_cgroup_recovery as processes, worker_loss_resolution as losses
    from . import noncommercial_contributions as nc, ai_pull_coordinator as pull
    from .regime_local_readiness import _KNOWN_SCHEMAS
    from .commercial_launch import TABLE
    if not c.in_transaction:
        raise FenceBlocked('Original transactional operator review required')
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ledger = _run(lambda: payments.report(c, limit=limit, offset=offset))
    original = ledger.get('subscription_original_basis_review')
    if not isinstance(original, dict):
        original = _run(lambda: basis.review(c, limit=limit, offset=offset))
    checkout = _run(lambda: outbox.audit_checkout_integrity(c))
    events = _run(lambda: inbox.audit_provider_inbox(c))
    sections = [
        _section('payment_ledger', ledger, counts=('pending', 'active_disputes'),
                 money=('subscription_reversal_due_micro', 'subscription_repayment_refund_due_micro', 'subscription_risk_micro'), action='reconcile_payment'),
        _section('checkout_dispatches', checkout, counts=('outstanding_dispatches',), action='recover_checkout'),
        _section('provider_events', events, counts=('pending',), action='reconcile_payment'),
        _section('financial_observations', _run(lambda: observations.audit_observations(c)), action='review_evidence'),
        _section('original_subscription_basis', original, counts=('total',), action='original_basis'),
        _section('operator_refunds', _run(lambda: refunds.audit(c)), counts=('pending',), action='refunds'),
        _section('worker_claims', _run(lambda: _claims(c)), counts=('running',), family='work', action='worker_recovery'),
        _section('pull_execution', _run(lambda: pull.inspect_state(c)), counts=('pending',), family='work', action='worker_recovery'),
        _section('worker_quiescence', _run(lambda: processes.report(c)), counts=('pending',), family='work', action='worker_recovery'),
        _section('operator_losses', _run(lambda: losses.audit(c)), family='work', action='worker_recovery'),
    ]
    collection = _run(lambda: nc.audit(c))
    contribution = _section('nc_collection', collection, counts=('pending',), action='nc_collection')
    cents = collection.get('refund_due_cents')
    contribution['refund_due_cents'] = str(cents) if type(cents) is int and cents >= 0 else None
    if cents is None or type(cents) is not int or cents < 0:
        contribution['state'] = 'unverified'
    elif cents:
        contribution['state'] = 'pending'
    sections.append(contribution)
    unknown = sorted(tables - (_KNOWN_SCHEMAS | {TABLE}))
    sections.append({'id': 'schema_coverage', 'family': 'finance', 'verified': not unknown,
                     'state': 'unverified' if unknown else 'verified', 'action': 'schema_review',
                     'counts': {'unknown_schemas': len(unknown)}, 'amounts_micro': {}, 'issues': unknown})
    # Complete merchant history is still unimplemented. Neither a balanced local
    # wallet nor a bounded reporting window may silently certify that history.
    provider = _run(lambda: _provider_history(c))
    sections.append({'id': 'provider_history', 'family': 'finance',
                     'verified': provider.get('verified') is True,
                     'state': 'review_required' if provider.get('history_or_configuration') else
                              'verified' if provider.get('verified') else 'unverified',
                     'action': 'merchant_history', 'counts': {'records': provider.get('records')},
                     'amounts_micro': {}, 'issues': ['complete_provider_history_not_certified']
                     if provider.get('history_or_configuration') else [],
                     'coverage': 'local_schema_absence_only' if provider.get('verified') and not provider.get('history_or_configuration') else 'not_certified'})
    # An unused optional journal is distinct from an unavailable populated
    # journal. Prove absence across original books and original fence kinds;
    # never replace an audit error on an existing/partial journal with zero.
    if provider.get('verified') and not provider.get('history_or_configuration'):
        operations = dict(c.execute('SELECT kind,COUNT(*) FROM regime_fence_operations GROUP BY kind'))
        unused = {
            'checkout_dispatches': 'regime_payment_outbox' not in tables and not operations.get('checkout', 0),
            'provider_events': 'regime_provider_inbox' not in tables and not operations.get('webhook', 0),
            'financial_observations': 'regime_financial_evidence' not in tables and not operations.get('checkout', 0),
            'worker_claims': 'regime_worker_claims' not in tables and not operations.get('job', 0)
                and not c.execute('SELECT 1 FROM ai_compute_jobs LIMIT 1').fetchone()
                and not c.execute('SELECT 1 FROM resource_job_contracts LIMIT 1').fetchone(),
        }
        for section in sections:
            if unused.get(section['id']):
                section.update(verified=True, state='not_used', issues=[],
                               counts={key: 0 for key in section['counts']},
                               basis='no_original_records_in_reviewed_schemas')
    return {'sections': sections, 'original_basis': {
        'items': original.get('items', []), 'total': original.get('total'),
        'checked': original.get('checked'), 'limit': limit, 'offset': offset,
        'automatic_reconstruction_allowed': False},
        'general_financial_clearance': False, 'historical_records_preserved': True}


def _provider_history(c):
    # Fixed queries only; no dynamic names or credential values leave this scope.
    stripe = c.execute('SELECT secret_key,webhook_secret FROM credit_payment_config WHERE id=1').fetchone()
    paypal = c.execute('SELECT enabled,client_id,client_secret,webhook_id FROM paypal_config WHERE id=1').fetchone()
    records = c.execute('''SELECT (SELECT COUNT(*) FROM credit_purchase_orders)+(SELECT COUNT(*) FROM credit_payment_events)
        +(SELECT COUNT(*) FROM paypal_orders)+(SELECT COUNT(*) FROM paypal_captures)+(SELECT COUNT(*) FROM paypal_refunds)
        +(SELECT COUNT(*) FROM paypal_events)+(SELECT COUNT(*) FROM payment_reconciliation_events)
        +(SELECT COUNT(*) FROM payment_reconciliation_positions)+(SELECT COUNT(*) FROM payment_reconciliation_movements)
        +(SELECT COUNT(*) FROM payment_reconciliation_disputes)+(SELECT COUNT(*) FROM payment_reconciliation_objects)''').fetchone()[0]
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    journals = {
        'regime_payment_outbox': 'SELECT COUNT(*) FROM regime_payment_outbox',
        'regime_provider_inbox': 'SELECT COUNT(*) FROM regime_provider_inbox',
        'regime_financial_evidence': 'SELECT COUNT(*) FROM regime_financial_evidence',
        'checkout_terminal_receipts': 'SELECT COUNT(*) FROM checkout_terminal_receipts',
        'operator_refunds': 'SELECT COUNT(*) FROM operator_refunds',
        'paypal_financial_holds': 'SELECT COUNT(*) FROM paypal_financial_holds',
        'subscription_payment_basis': 'SELECT COUNT(*) FROM subscription_payment_basis',
        'subscription_repayment_allocations': 'SELECT COUNT(*) FROM subscription_repayment_allocations',
        'paypal_merchant_history': 'SELECT COUNT(*) FROM paypal_merchant_history',
        'regime_commercial_origin': 'SELECT COUNT(*) FROM regime_commercial_origin',
    }
    for table, query in journals.items():
        if table in tables:
            records += c.execute(query).fetchone()[0]
    if stripe is None or paypal is None:
        return {'verified': False, 'records': records, 'history_or_configuration': True}
    return {'verified': True, 'records': records, 'history_or_configuration': bool(records),
            'configured':bool(any(stripe) or any(paypal))}


def read(*, actor, target, limit=50, offset=0):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError('Invalid operator review page')
    destination = Regime(target).value
    from . import service_admission as admission, regime_admin_cutover as cutover
    from .regime_service_lease import enabled
    with admission.control(), auth.db() as c:
        cutover._actor(c, actor)
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        state = read_regime(auth.data_root() / 'service-regime.json')
        result = snapshot(c, limit=limit, offset=offset)
    service = _run(lambda: admission.inspect(actor=actor))
    projected = {key: service.get(key) for key in ('enabled', 'phase', 'generation', 'drain_id',
                                                  'drained', 'active_count', 'build_matches')}
    preview = None
    try:
        if any(section['state'] not in ('verified', 'not_used') for section in result['sections']):
            raise FenceBlocked('Operator review requires original evidence')
        preview = cutover.preview(target=destination, actor=actor)
        eligibility = 'verified_precommercial_profile'
    except (FenceBlocked, sqlite3.DatabaseError, ValueError, TypeError, OSError):
        eligibility = 'mode_disabled' if not enabled() else 'same_regime' if destination == state.regime.value else 'blocked'
    body = {**result, 'schema': 'mta-operator-preflight-1', 'source': state.regime.value,
            'target': destination, 'source_revision': state.revision, 'service_admission': projected,
            'maintenance_eligibility': eligibility, 'preview': preview,
            'general_transition_authorized': False, 'release_candidate': False,
            'financial_model':{'id':'precommercial-no-payment-history-1','legacy_migration_supported':False,
                               'switching_after_checkout_started':False}}
    return {**body, 'review_sha256': hashlib.sha256(encode(body).encode()).hexdigest()}
