"""Regime-appropriate model admission must be enforced server-side."""
from unittest.mock import patch
import pytest
from app import model_license_policy as policy
from app.service_regime import Regime
from model_rights_fixtures import synthetic_review


@pytest.mark.parametrize('regime,mode,allowed', [
    (Regime.NON_COMMERCIAL, 'free_only', True),
    (Regime.COMMERCIAL, 'free_only', False),
    (Regime.COMMERCIAL, 'cost_recovery', True),
    (Regime.NON_COMMERCIAL, 'cost_recovery', True),
])
def test_regime_admission_prevents_commercial_use_of_free_only(regime, mode, allowed):
    with patch.object(policy, 'overrides', return_value={'custom-test': synthetic_review(mode)}), \
         patch.object(policy, 'commercial_service_enabled', return_value=True), \
         patch('app.service_regime.current_regime', return_value=regime):
        if allowed:
            assert policy.evaluate_model('custom-test').mode == mode
        else:
            with pytest.raises(policy.LicenseDenied, match='commercial service'):
                policy.evaluate_model('custom-test')


def test_unreviewed_never_becomes_available_by_regime():
    for regime in Regime:
        with patch.object(policy, 'overrides', return_value={}), \
             patch('app.service_regime.current_regime', return_value=regime):
            with pytest.raises(policy.LicenseDenied):
                policy.evaluate_model('unknown-checkpoint-xyz')
