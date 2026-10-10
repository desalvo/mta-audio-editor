"""r15: VST3 capability diagnostics must not activate audio processing."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from native.vst3_probe.probe import probe_plugin


def test_capabilities_are_bounded(tmp_path):
    plugin = tmp_path / 'plugin.vst3'; plugin.write_bytes(b'x')
    exe = tmp_path / 'probe'; exe.write_bytes(b'x')
    data = {'factory_export': True, 'sample_size_queried': True,
            'supports_32_bit': True, 'supports_64_bit': False, 'latency_samples': 512}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plugin), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=plugin), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stderr='', stdout=json.dumps(data))):
        result = probe_plugin(str(plugin), str(exe), instantiate_cid='a' * 32, lifecycle=True)
        assert result['supports_32_bit'] is True
        assert result['supports_64_bit'] is False
        assert result['latency_samples'] == 512
        assert probe_plugin(str(plugin), str(exe))['latency_samples'] is None


def test_untrusted_latency_rejected(tmp_path):
    plugin = tmp_path / 'plugin.vst3'; plugin.write_bytes(b'x')
    exe = tmp_path / 'probe'; exe.write_bytes(b'x')
    data = {'factory_export': True, 'latency_samples': 10000001}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plugin), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=plugin), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stderr='', stdout=json.dumps(data))):
        assert probe_plugin(str(plugin), str(exe), instantiate_cid='a' * 32, lifecycle=True)['latency_samples'] is None


def test_no_realtime_calls_in_probe():
    code = Path('native/vst3_probe/main.cpp').read_text()
    assert 'canProcessSampleSize' in code
    assert 'getLatencySamples' in code
    assert 'component->process(' not in code
    assert 'processor->process(' not in code
