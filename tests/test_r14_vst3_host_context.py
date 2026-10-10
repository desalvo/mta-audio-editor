"""r14 host context contract and Python sanitization."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
from native.vst3_probe.probe import probe_plugin


def test_lifecycle_host_context_is_explicit(tmp_path):
    plugin = tmp_path / 'sample.vst3'; plugin.write_bytes(b'x')
    exe = tmp_path / 'probe'; exe.write_bytes(b'x')
    payload = {'factory_export': True, 'host_context_provided': True, 'instance_initialized': True}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plugin), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=plugin), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stderr='', stdout=json.dumps(payload))):
        assert probe_plugin(str(plugin), str(exe), instantiate_cid='a'*32, lifecycle=True)['host_context_provided'] is True
        assert probe_plugin(str(plugin), str(exe), instantiate_cid='a'*32)['host_context_provided'] is False


def test_host_context_is_not_realtime_enabled():
    code = Path('native/vst3_probe/main.cpp').read_text()
    assert 'class DiagnosticHost' in code
    assert 'component->initialize(&host)' in code
    assert 'native_host_ready' in code and 'false' in code
    assert 'component->process(' not in code
