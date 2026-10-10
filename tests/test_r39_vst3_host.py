"""Functional regression for VST3 discovery, parameter and entrypoint failures."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app import vst3_host


def test_custom_directory_discovery_and_validation(tmp_path, monkeypatch):
    root = tmp_path / "plugins"
    root.mkdir()
    bundle = root / "Example.vst3"
    bundle.mkdir()
    monkeypatch.setenv("MTA_VST3_PATHS", str(root))
    assert any(p["path"] == str(bundle) for p in vst3_host.discover_plugins())
    assert vst3_host.validate_plugin_path(str(bundle)) == bundle
    with pytest.raises(ValueError, match="invalid"):
        vst3_host.validate_plugin_path("bad.dll")
    with pytest.raises(FileNotFoundError):
        vst3_host.validate_plugin_path(str(root / "missing.vst3"))
    outside = tmp_path / "outside.vst3"
    outside.mkdir()
    with pytest.raises(ValueError, match="outside"):
        vst3_host.validate_plugin_path(str(outside))


def test_parameters_validation_and_assignment():
    param = SimpleNamespace(raw_value=0.2)
    plugin = SimpleNamespace(parameters={"gain": param})
    vst3_host.apply_parameters(plugin, {"gain": 0.75})
    assert param.raw_value == 0.75
    with pytest.raises(ValueError, match="unavailable"):
        vst3_host.apply_parameters(plugin, {"missing": 0.2})
    with pytest.raises(ValueError, match="outside"):
        vst3_host.apply_parameters(plugin, {"gain": -0.1})
    with pytest.raises(ValueError, match="outside"):
        vst3_host.apply_parameters(plugin, {"gain": 1.1})


def test_inspect_parameters_with_mock_plugin(monkeypatch):
    import sys
    fake = SimpleNamespace(load_plugin=lambda _: SimpleNamespace(parameters={
        "gain": SimpleNamespace(raw_value=0.3), "skip": SimpleNamespace(raw_value=None)}))
    monkeypatch.setitem(sys.modules, "pedalboard", fake)
    assert vst3_host.inspect_parameters(Path("demo.vst3")) == [{"name": "gain", "value": 0.3}]


def test_cli_inspection_and_missing_arguments(capsys):
    with patch("sys.argv", ["vst3_host", "--inspect-plugin", "fake.vst3"]), \
         patch.object(vst3_host, "validate_plugin_path", return_value=Path("fake.vst3")), \
         patch.object(vst3_host, "inspect_parameters", return_value=[{"name": "gain", "value": 0.2}]):
        assert vst3_host.main() == 0
    assert json.loads(capsys.readouterr().out)["parameters"][0]["name"] == "gain"
    with patch("sys.argv", ["vst3_host"]), pytest.raises(SystemExit) as err:
        vst3_host.main()
    assert err.value.code == 2


def test_runtime_missing_dependency(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "pedalboard", None)
    with pytest.raises(RuntimeError, match="requirements-vst3"):
        vst3_host.process_audio(Path("x.wav"), Path("y.wav"), Path("fake.vst3"))
