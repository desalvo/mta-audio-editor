"""r24: isolated one-block VST3 offline processing smoke-test contract."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from native.vst3_probe.probe import probe_plugin

CID = "a" * 32
ROOT = Path(__file__).resolve().parents[1]


def test_offline_requires_explicit_cid():
    with pytest.raises(ValueError, match="CID"):
        probe_plugin("missing.vst3", "missing", offline=True)


def test_offline_isolated_and_opt_in():
    code = (ROOT / "native/vst3_probe/main.cpp").read_text()
    assert '"--offline"' in code
    assert 'if (offline && processor && processingSetupSucceeded)' in code
    assert 'component->setActive(true)' in code
    assert 'processor->setProcessing(true)' in code
    assert 'processor->process(data)' in code
    assert 'processor->setProcessing(false)' in code
    assert 'component->setActive(false)' in code
    assert 'native_host_ready' in code


def test_offline_diagnostic_result_is_validated(tmp_path):
    binary = tmp_path / "sample.vst3"
    binary.write_bytes(b"mock")
    exe = tmp_path / "probe"
    exe.write_bytes(b"mock")
    payload = {"factory_export": True, "offline_activated": True,
               "offline_process_succeeded": True, "offline_output_channels": 2,
               "offline_nonfinite_samples": 0, "offline_deactivated": True}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=binary), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=binary), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))) as run:
        result = probe_plugin(str(binary), str(exe), instantiate_cid=CID, offline=True)
    assert run.call_args.args[0][-2:] == ['--offline', CID]
    assert result['offline_process_succeeded'] is True
    assert result['offline_output_channels'] == 2
    assert result['native_host_ready'] is False


def test_bad_offline_channel_counts_rejected(tmp_path):
    binary = tmp_path / "sample.vst3"
    binary.write_bytes(b"mock")
    payload = {"factory_export": True, "offline_output_channels": 1000000,
               "offline_nonfinite_samples": -1}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=binary), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=binary), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))):
        result = probe_plugin(str(binary), str(binary), instantiate_cid=CID, offline=True)
    assert result['offline_output_channels'] is None
    assert result['offline_nonfinite_samples'] is None
