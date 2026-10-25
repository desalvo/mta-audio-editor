import json
import pytest

from app.service_regime import (Regime, RegimeError, RegimeState,
                                read_regime, write_initial_noncommercial, plan_transition)

def test_missing_defaults_nc(tmp_path):
    assert read_regime(tmp_path/'mode.json').regime == Regime.NON_COMMERCIAL

def test_initialization_is_preserving(tmp_path):
    path = tmp_path/'mode.json'
    assert write_initial_noncommercial(path).revision == 0
    original = path.read_bytes()
    assert write_initial_noncommercial(path).regime == Regime.NON_COMMERCIAL
    assert path.read_bytes() == original

def test_legacy_commercial_not_overwritten(tmp_path):
    path = tmp_path/'mode.json'
    path.write_text(json.dumps({'regime':'COMMERCIAL','revision':3}))
    assert write_initial_noncommercial(path) == RegimeState(Regime.COMMERCIAL,3)

@pytest.mark.parametrize('data', ['not json','[]','{}', '{"regime":"INVALID","revision":0}', '{"regime":"COMMERCIAL","revision":true}'])
def test_invalid_records_fail_closed(tmp_path,data):
    path=tmp_path/'mode.json'; path.write_text(data)
    with pytest.raises(RegimeError): read_regime(path)

def test_symlink_refused(tmp_path):
    path=tmp_path/'mode.json';path.symlink_to(tmp_path/'missing')
    with pytest.raises(RegimeError): read_regime(path)

def test_transition_plan_blocks_financial_ambiguity():
    plan=plan_transition(RegimeState(Regime.COMMERCIAL),Regime.NON_COMMERCIAL,
                         subscriptions=2,credit_balances=1,active_jobs=1)
    assert plan['ready'] is False
    assert set(plan['blockers'])=={'subscriptions','credit_balances','active_jobs'}
    assert plan['mutates_usage_ledger'] is False

def test_transition_plan_has_no_side_effects():
    state=RegimeState(Regime.NON_COMMERCIAL)
    plan=plan_transition(state,Regime.COMMERCIAL)
    assert plan['ready'] and plan['requires_explicit_confirmation']
    assert state.regime==Regime.NON_COMMERCIAL
