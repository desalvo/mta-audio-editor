from unittest.mock import Mock

import pytest

from app import model_license_policy as rights,service_regime,ai_remote_client as remote,ace_step_http_worker as ace
from test_r210_remote_transport_rights import gateway_client


@pytest.mark.parametrize('regime',list(service_regime.Regime))
@pytest.mark.parametrize('entry',['client','gateway','ace-request','ace-run'])
def test_production_profile_blocks_every_generic_transport_before_network(monkeypatch,tmp_path,regime,entry):
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION','verified-pull-v1')
    monkeypatch.setattr(service_regime,'current_regime',lambda:regime)
    monkeypatch.setenv('MTA_ACE_STEP_URL','https://worker.example.test:443')
    monkeypatch.setenv('MTA_ACE_STEP_TRUSTED_HOST','worker.example.test')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN','test-only-worker-token')
    network=Mock(side_effect=AssertionError('No inference transport allowed'))
    monkeypatch.setattr(remote,'https_urlopen',network);monkeypatch.setattr(ace,'build_opener',network)
    if entry=='gateway':
        client,sent=gateway_client(monkeypatch)
        assert client.post('/api/ai-gateway/release_task',headers={'authorization':'Bearer valid'},content=b'{}').status_code==403
        assert not sent
    elif entry=='client':
        with pytest.raises(rights.LicenseDenied):remote.infer_audio('https://mta.example.test','test','audio-to-midi-basic-pitch',b'')
    elif entry=='ace-request':
        with pytest.raises(rights.LicenseDenied):ace._request('https://worker.example.test:443/release_task',b'{}')
    else:
        plan=tmp_path/'plan.json';plan.write_text('{"model_id":"ace-step-1.5"}')
        with pytest.raises(rights.LicenseDenied):ace._run(plan,tmp_path/'missing.wav')
    network.assert_not_called()
