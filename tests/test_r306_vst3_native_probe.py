from pathlib import Path
import pytest
from native.vst3_probe.probe import resolve_module_binary, probe_plugin


def test_missing_arch_binary(tmp_path):
    bundle = tmp_path / "test.vst3"
    bundle.mkdir()
    with pytest.raises(FileNotFoundError):
        resolve_module_binary(bundle)


def test_probe_refuses_invalid_plugin(tmp_path):
    with pytest.raises(ValueError):
        probe_plugin(str(tmp_path / "anything.txt"), str(tmp_path / "missing"))


def test_probe_source_exports_symbol_without_calling_factory():
    source = Path("native/vst3_probe/main.cpp").read_text()
    assert "GetPluginFactory" in source
    assert "factory()" not in source
    assert "native_host_ready" in source
