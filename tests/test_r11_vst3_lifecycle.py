"""r11 isolated VST3 lifecycle API and opt-in safety regression tests."""
import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from native.vst3_probe.probe import probe_plugin


def test_lifecycle_opt_in_and_status(tmp_path):
    plug = tmp_path / 'plugin.vst3'; plug.write_bytes(b'x')
    exe = tmp_path / 'probe'; exe.write_bytes(b'x')
    cid = 'a' * 32
    payload = {'factory_export': True, 'classes': [], 'instance_created': True,
               'instance_initialized': True, 'instance_terminated': True}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plug), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=plug), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr='')) as run:
        result = probe_plugin(str(plug), str(exe), instantiate_cid=cid, lifecycle=True)
    assert run.call_args.args[0][-2:] == ['--lifecycle', cid]
    assert result['instance_initialized'] and result['instance_terminated']
    assert result['native_host_ready'] is False


def test_lifecycle_requires_cid(tmp_path):
    with pytest.raises(ValueError, match='CID'):
        probe_plugin(str(tmp_path), str(tmp_path), lifecycle=True)


def test_creation_cannot_claim_lifecycle(tmp_path):
    plug = tmp_path / 'plugin.vst3'; plug.write_bytes(b'x')
    exe = tmp_path / 'probe'; exe.write_bytes(b'x')
    payload = {'factory_export': True, 'classes': [], 'instance_initialized': True,
               'instance_terminated': True}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plug), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=plug), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr='')):
        result = probe_plugin(str(plug), str(exe), instantiate_cid='a' * 32)
    assert not result['instance_initialized'] and not result['instance_terminated']
