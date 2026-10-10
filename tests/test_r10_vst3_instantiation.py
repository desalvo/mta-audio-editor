"""r10: explicit opt-in instance diagnostic safety checks."""
import json
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from native.vst3_probe.probe import probe_plugin

def test_instance_request_opt_in(tmp_path):
    plug = tmp_path / 'test.vst3'; plug.write_bytes(b'test')
    exe = tmp_path / 'probe'; exe.write_bytes(b'test')
    cid = 'abcdef0123456789abcdef0123456789'
    payload = {'factory_export':True,'classes':[],'instance_found':True,'instance_created':True}
    with patch('native.vst3_probe.probe.validate_plugin_path',return_value=plug), patch('native.vst3_probe.probe.resolve_module_binary',return_value=plug), patch('native.vst3_probe.probe.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(payload),stderr='')) as run:
        result=probe_plugin(str(plug),str(exe),instantiate_cid=cid.upper())
    assert run.call_args.args[0][-2:] == ['--instantiate',cid]
    assert result['instance_created'] is True
    assert result['native_host_ready'] is False

def test_invalid_cid_rejected_before_execution(tmp_path):
    plug=tmp_path/'test.vst3';plug.write_bytes(b'test')
    exe=tmp_path/'probe';exe.write_bytes(b'test')
    with patch('native.vst3_probe.probe.validate_plugin_path',return_value=plug), patch('native.vst3_probe.probe.resolve_module_binary',return_value=plug), patch('native.vst3_probe.probe.subprocess.run') as run:
        with pytest.raises(ValueError): probe_plugin(str(plug),str(exe),instantiate_cid='../../bad')
        run.assert_not_called()
