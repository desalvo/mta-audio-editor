"""Explicit opt-in real sandbox readback. No checkout/capture/refund requests.

Use an isolated COPY of the application's sandbox database and auth secret;
never point this test at a running server or a production data directory.
"""
import os
from pathlib import Path

import pytest
from app import auth

pytestmark=pytest.mark.skipif(
    os.getenv('MTA_TEST_PROVIDER_SANDBOX')!='1' or os.getenv('MTA_TEST_OFFLINE')=='1',
    reason='Requires explicit provider sandbox opt-in and an isolated sandbox database copy')


def sandbox_root(monkeypatch):
    path=Path(os.environ['MTA_SANDBOX_DATA_DIR']).resolve()
    assert (path/'auth.sqlite3').is_file()
    monkeypatch.setattr(auth,'DATA_ROOT',path)
    monkeypatch.setenv('MTA_DATA_DIR',str(path))


def test_real_stripe_sandbox_readback_only(monkeypatch):
    sandbox_root(monkeypatch)
    from app import payment_reconcile_service
    with auth.db() as c:
        key=auth._open(c.execute('SELECT secret_key FROM credit_payment_config WHERE id=1').fetchone()[0])
        assert key.startswith('sk_test_'), 'Only Stripe test credentials are allowed'
    result=payment_reconcile_service.reconcile_checkout('stripe',os.environ['MTA_TEST_STRIPE_SANDBOX_ORDER'])
    assert result['ledger_reconciled'] and not result['transition_authorized']


def test_real_paypal_sandbox_readback_only(monkeypatch):
    sandbox_root(monkeypatch)
    from app import paypal_payments,payment_reconcile_service
    with auth.db() as c:assert paypal_payments._keys(c)['environment']=='sandbox'
    result=payment_reconcile_service.reconcile_checkout('paypal',os.environ['MTA_TEST_PAYPAL_SANDBOX_ORDER'])
    assert result['status']=='paid' and not result['transition_authorized']
