"""r16: limit untrusted diagnostics and reject invalid CIDs before module load."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from native.vst3_probe.probe import probe_plugin


def test_oversized_output_is_rejected(tmp_path):
    plugin = tmp_path / 'fake.vst3'
    plugin.write_bytes(b'test')
    exe = tmp_path / 'probe'
    exe.write_bytes(b'test')
    response = SimpleNamespace(returncode=0, stderr='', stdout=' ' * 2_000_001)
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plugin), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=plugin), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=response):
        with pytest.raises(RuntimeError, match='exceeds'):
            probe_plugin(str(plugin), str(exe))


def test_invalid_root_json_is_rejected(tmp_path):
    plugin = tmp_path / 'fake.vst3'
    plugin.write_bytes(b'test')
    exe = tmp_path / 'probe'
    exe.write_bytes(b'test')
    response = SimpleNamespace(returncode=0, stderr='', stdout=json.dumps([1, 2]))
    with patch('native.vst3_probe.probe.validate_plugin_path', return_value=plugin), \
         patch('native.vst3_probe.probe.resolve_module_binary', return_value=plugin), \
         patch('native.vst3_probe.probe.subprocess.run', return_value=response):
        with pytest.raises(RuntimeError, match='non-object'):
            probe_plugin(str(plugin), str(exe))


def test_cpp_cid_validation_runs_before_module_load():
    binary = Path('native/vst3_probe/main.cpp').read_text()
    assert binary.index('if (instantiate) {\n    const std::string cid') < binary.index('LoadLibraryA(argv[1])')
    assert binary.index('if (instantiate) {\n    const std::string cid') < binary.index('dlopen(argv[1]')
