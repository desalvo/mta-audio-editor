"""Remote inference must not skip active-regime rights checks."""
from unittest.mock import Mock
import pytest
from app import model_license_policy as licenses, service_regime, studio_compute


def test_remote_commercial_denied_even_if_known_local_model(monkeypatch):
    monkeypatch.setattr(service_regime, 'current_regime', lambda: service_regime.Regime.COMMERCIAL)
    monkeypatch.setattr(licenses, 'overrides', lambda: {})
    monkeypatch.setattr(licenses, 'commercial_service_enabled', lambda: True)
    with pytest.raises(licenses.LicenseDenied, match='attestation'):
        licenses.authorize_remote_execution('audio-to-midi-basic-pitch', {})


def test_remote_denied_before_transport(monkeypatch):
    from app import native_ai_routing
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.setattr(native_ai_routing, 'is_remote', lambda kind: True)
    monkeypatch.setattr(licenses, 'authorize_remote_execution', Mock(side_effect=licenses.LicenseDenied('blocked')))
    remote = Mock()
    monkeypatch.setattr(studio_compute, 'remote_compute', remote)
    with pytest.raises(licenses.LicenseDenied, match='blocked'):
        studio_compute.compute(0, 'audio-to-midi-basic-pitch', {})
    remote.assert_not_called()


def test_remote_noncommercial_still_evaluates_model(monkeypatch):
    monkeypatch.setattr(service_regime, 'current_regime', lambda: service_regime.Regime.NON_COMMERCIAL)
    monkeypatch.setattr(licenses, 'overrides', lambda: {})
    monkeypatch.setattr(licenses, 'commercial_service_enabled', lambda: True)
    assert licenses.authorize_remote_execution('audio-to-midi-basic-pitch', {}).model_id == 'basic-pitch'
    with pytest.raises(licenses.LicenseDenied):
        licenses.authorize_remote_execution('markers', {'engine': 'madmom'})


@pytest.mark.parametrize('entry',['native-routing','native-arranger','durable-executor','studio-direct','durable-bridge'])
def test_every_remote_entry_rejects_before_source_or_transport(monkeypatch,entry):
    if entry in ('native-routing','native-arranger','studio-direct'):
        monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    from app import native_ai_routing,native_ai_account,ai_durable_remote_executor,ai_metering_bridge
    from pathlib import Path
    gate=Mock(side_effect=licenses.LicenseDenied('blocked by rights gate'))
    monkeypatch.setattr(licenses,'authorize_remote_execution',gate)
    if entry=='native-routing':call=lambda:native_ai_routing.infer('whisper',Path('/missing.wav'))
    elif entry=='native-arranger':call=lambda:native_ai_account.execute_arranger({},None,None)
    elif entry=='durable-executor':
        monkeypatch.setattr(ai_durable_remote_executor,'configured_remote',lambda:('https://example.test','worker','test-token'))
        call=lambda:ai_durable_remote_executor.execute('job',{},None,None)
    elif entry=='studio-direct':call=lambda:studio_compute.remote_compute('vocal-harmony',{})
    else:
        monkeypatch.setattr(ai_metering_bridge,'_identity',lambda _: (1,'arranger'))
        call=lambda:ai_metering_bridge.infer_durable_remote('job',base_url='https://example.test',token='test',wav=b'',worker_id='node')
    with pytest.raises(licenses.LicenseDenied,match='rights gate'):call()
    gate.assert_called_once()
