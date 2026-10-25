"""Domain-level commercial entry points must reject direct NC calls.

These tests run without initializing any database or issuing network requests.
"""
import pytest
from app import auth
from app.resource_accounts import assign
from app.resource_access import grant_credits
from app.resource_entitlements import extend_storage
from app.service_regime import RegimeError

@pytest.mark.parametrize('entry,args', [
    (extend_storage, (1, 1, 'eightchars')),
    (grant_credits, (1, 10, 1000, 'testing', 1, 'eightchars')),
])
def test_commercial_domain_cannot_bypass_nc_mode(entry, args, monkeypatch, tmp_path):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    with pytest.raises(RegimeError, match='NON_COMMERCIAL'):
        entry(*args)
    assert not (tmp_path / 'auth.sqlite3').exists()


def test_direct_self_service_assignment_blocked_in_nc(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    with pytest.raises(RegimeError, match='NON_COMMERCIAL'):
        assign(1, {'plan':'week'}, 1, self_service=True, expected_price=100)
    assert not (tmp_path / 'auth.sqlite3').exists()
