"""Actual preflight and drain APIs; never use caller-supplied financial readiness."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import auth, regime_operator_preflight as review, service_admission as gate
from app.regime_balance_continuity import snapshot
from test_r210_admin_cutover_e2e import ready as ready, account as account, HEADERS, BASE  # noqa: F401
from test_r210_cutover_service_drain import drained as drained  # noqa: F401
from test_r210_legal_documents import cookie

PATH = BASE + '/preflight'


def get(ready, **params):
    return ready[0].get(PATH, params={'target': 'NON_COMMERCIAL', **params})


def test_actual_complete_review_has_original_preview_and_never_changes_money(ready):
    client, _, admin = ready
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE'); before = snapshot(c)
    result = get(ready)
    assert result.status_code == 200, result.text
    data = result.json()
    assert 'no-store' in result.headers['cache-control']
    assert data['schema'] == 'mta-operator-preflight-1'
    assert len(data['sections']) == 13 and len({s['id'] for s in data['sections']}) == 13
    assert not data['general_transition_authorized'] and not data['general_financial_clearance']
    assert data['maintenance_eligibility'] == 'verified_precommercial_profile'
    assert data['preview']['transition_enabled'] and data['preview']['source_revision'] == 0
    assert data['preview']['readiness']['profile'] == 'precommercial-no-payment-history-1'
    with auth.db() as c:
        c.execute('PRAGMA query_only=ON'); c.execute('BEGIN')
        changes = c.total_changes
        review.snapshot(c)
        assert c.total_changes == changes and snapshot(c) == before
    assert client.get(BASE).json()['total'] == 0


@pytest.mark.parametrize('field,value', [('target', 'unknown'), ('limit', 0), ('limit', 101), ('offset', -1)])
def test_invalid_review_input_never_opens_cutover(ready, field, value):
    assert get(ready, **{field: value}).status_code == 422
    assert ready[0].get(BASE).json()['total'] == 0


@pytest.mark.parametrize('role', ['anonymous', 'owner', 'inactive-admin'])
def test_financial_review_never_discloses_to_non_administrator(ready, role):
    from app import main
    client, uid, admin = ready
    web = TestClient(main.app)
    if role != 'anonymous': web.cookies.update(cookie(uid if role == 'owner' else admin))
    if role == 'inactive-admin':
        with auth.db() as c: c.execute('UPDATE users SET active=0 WHERE id=?', (admin,))
    result = web.get(PATH + '?target=NON_COMMERCIAL')
    assert result.status_code in (401, 403)
    assert 'sections' not in result.text


def test_unavailable_financial_family_is_isolated_private_and_not_zero(ready, monkeypatch):
    from app import payment_reconciliation
    def unavailable(*args, **kwargs): raise sqlite3.OperationalError('private credential must not be exposed')
    monkeypatch.setattr(payment_reconciliation, 'report', unavailable)
    data = get(ready).json()
    sections = {s['id']: s for s in data['sections']}
    assert sections['payment_ledger']['state'] == 'unverified'
    assert sections['payment_ledger']['counts']['pending'] is None
    assert sections['schema_coverage']['state'] == 'verified'
    assert 'private credential' not in json.dumps(data)
    assert not data['general_financial_clearance']
    assert data['preview'] is None


@pytest.mark.parametrize('damage', ['unknown-schema', 'missing-schema'])
def test_unproven_history_and_schemas_remain_visible_blockers(ready, damage):
    with auth.db() as c:
        if damage == 'unknown-schema': c.execute('CREATE TABLE unreviewed_legacy_finance(id TEXT)')
        else: c.execute('DROP TABLE credit_purchase_orders')
    data = get(ready).json()
    assert data['maintenance_eligibility'] == 'blocked' and data['preview'] is None
    family = 'schema_coverage' if damage == 'unknown-schema' else 'provider_history'
    item = next(s for s in data['sections'] if s['id'] == family)
    assert item['state'] in ('review_required', 'unverified')
    assert not data['general_transition_authorized']


def test_actual_settings_notification_default_is_not_an_economic_obligation(ready):
    from app import ai_notifications
    with auth.db() as c: ai_notifications._init(c)
    data = get(ready).json()
    assert data['maintenance_eligibility'] == 'verified_precommercial_profile'
    assert data['preview'] is not None


def test_drain_allows_exact_private_review_reads_but_no_new_financial_dispatch(drained, monkeypatch):
    client, _, _ = drained
    data = get(drained)
    assert data.status_code == 200 and data.json()['service_admission']['drained']
    for path in ('/api/admin/service-regime/payment-ledger',
                 '/api/admin/service-regime/subscription-evidence',
                 '/api/admin/service-regime/operation-fence'):
        assert client.get(path).status_code == 200
    for path in ('/api/billing/credits/checkout', '/api/billing/paypal/create',
                 '/api/admin/payment-refunds', '/api/admin/service-regime/noncommercial-statements'):
        assert not gate.continuation({'path': path, 'method': 'POST'})
        assert client.post(path, headers=HEADERS, json={}).status_code == 503
    for variable in ('ALL_PROXY', 'all_proxy', 'HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy'):
        monkeypatch.delenv(variable, raising=False)
    assert client.post('/api/admin/service-regime/reconcile-payment', headers=HEADERS,
                       json={'provider': 'stripe', 'order_id': 'missing-original'}).status_code == 422


def test_preflight_digest_is_diagnostic_and_never_a_write_permit(drained):
    client, _, _ = drained
    data = get(drained).json()
    assert len(data['review_sha256']) == 64
    forged = {'request_id': 'forged-review-request', 'target': 'NON_COMMERCIAL',
              'expected_revision': 0, 'preview_sha256': data['review_sha256'], 'confirm': True}
    assert client.post(BASE, headers=HEADERS, json=forged).status_code == 409
    assert client.get(BASE).json()['total'] == 0


def test_late_page_legacy_cases_are_all_audited_without_guessing_basis(ready):
    from test_r210_sensitive_operator_browser import legacy_orders
    legacy_orders(ready)
    data = get(ready, limit=1, offset=124).json()
    assert data['original_basis']['total'] == 125
    assert data['original_basis']['items'] == [{'order_id': 'legacy-124', 'reason': 'original_payment_basis_missing'}]
    assert data['preview'] is None and not data['original_basis']['automatic_reconstruction_allowed']
    with auth.db() as c:
        assert c.execute('SELECT COUNT(*) FROM subscription_payment_basis').fetchone()[0] == 0


def test_running_original_worker_is_pending_not_merely_consistent(ready):
    from app import ai_billing
    from app.regime_worker_claims import claim
    job = ai_billing.create_job(ready[1], 'vocal-harmony')
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE'); claim(c, job, worker_id='original-review-worker', token='original-review-token')
    data = get(ready).json()
    row = next(s for s in data['sections'] if s['id'] == 'worker_claims')
    assert row['verified'] and row['state'] == 'pending' and row['counts']['running'] == 1
    assert data['preview'] is None


@pytest.mark.parametrize('populated', [False, True])
def test_partial_optional_journal_is_never_waived_as_unused(ready, populated):
    with auth.db() as c:
        c.execute('CREATE TABLE regime_provider_inbox(id TEXT)')
        if populated: c.execute("INSERT INTO regime_provider_inbox VALUES('orphan-original-event')")
    data = get(ready).json()
    row = next(s for s in data['sections'] if s['id'] == 'provider_events')
    assert row['state'] == 'unverified' and data['preview'] is None
    if populated:
        assert next(s for s in data['sections'] if s['id'] == 'provider_history')['state'] == 'review_required'


@pytest.mark.parametrize('path,method,allowed', [
    ('/api/admin/service-regime/reconcile-payment', 'POST', True),
    ('/api/admin/service-regime/recover-checkout-reference', 'POST', True),
    ('/api/admin/service-regime/worker-processes/' + 'a'*32 + '/quiesce', 'POST', True),
    ('/api/admin/service-regime/worker-losses/' + 'a'*32 + '/resolve', 'POST', True),
    ('/api/admin/service-regime/worker-losses/' + 'a'*32 + '/recover-frozen', 'POST', True),
    ('/api/admin/service-regime/worker-losses/foreign/resolve', 'POST', False),
    ('/api/admin/service-regime/reconcile-payment/extra', 'POST', False),
    ('/api/admin/service-regime/payment-ledger', 'POST', False),
    ('/api/admin/payment-refunds/dispatch', 'POST', False),
    ('/api/admin/paypal/merchant-history', 'POST', False),
])
def test_only_exact_original_recovery_and_read_routes_bypass_new_admission(path, method, allowed):
    assert gate.continuation({'path': path, 'method': method}) is allowed
