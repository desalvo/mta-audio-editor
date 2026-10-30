"""Existing IT/EN operator panel completes an originally unknown checkout."""
# ruff: noqa: F401 -- original parametrized test and its fixtures are collected
import pytest
from test_r210_subscriptions import account as account
from test_r210_paypal import provider as provider
from test_r210_merchant_lost_creation import lost as lost
from test_r210_merchant_ledger_browser import test_actual_merchant_discovery_confirm_apply_reload as test_lost_creation_panel


@pytest.fixture
def merchant(lost):
    return lost
