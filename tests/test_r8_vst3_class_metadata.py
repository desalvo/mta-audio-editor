"""r8: reject malformed VST3 class metadata returned by a third-party probe."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json

from native.vst3_probe.probe import probe_plugin


def test_probe_filters_untrusted_class_metadata(tmp_path):
    bundle = tmp_path / 'Example.vst3'
    bundle.write_bytes(b'fake')
    executable = tmp_path / 'probe'
    executable.write_bytes(b'fake')
    cid = '0123456789abcdef0123456789abcdef'
    payload = {'factory_export': True, 'factory_classes': 2, 'classes': [
        {'cid': cid, 'name': 'FX', 'category': 'Audio Module Class'},
        {'cid': '../oops', 'name': 'bad', 'category': 'Audio Module Class'},
        {'cid': cid, 'name': 'bad', 'category': None},
    ]}
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=bundle), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=bundle), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr='')):
        result = probe_plugin(str(bundle), str(executable))
    assert result['classes'] == [payload['classes'][0]]
    assert result['factory_classes'] == 2
    assert result['native_host_ready'] is False
