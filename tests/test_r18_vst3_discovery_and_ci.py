"""Guard mobile revision metadata and isolated VST3 discovery behavior."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import vst3_host


def test_mobile_revisions_match_release_metadata():
    root = Path(__file__).resolve().parents[1]
    revision = int((root / "REVISION").read_text().strip())
    android = (root / "mobile/android/app/build.gradle.kts").read_text()
    ios = (root / "mobile/ios/MTAEditorMobile/Info.plist").read_text()
    assert f"versionCode = {30000 + revision}" in android
    assert f'buildConfigField("String", "MTA_REVISION", "\\\"{revision}\\\"")' in android
    assert f"<key>MTAEditorRevision</key><string>{revision}</string>" in ios
    assert f"<key>CFBundleVersion</key><string>{30000 + revision}</string>" in ios


def test_vst3_path_validation_rejects_non_plugins_and_missing_files(tmp_path):
    with pytest.raises(ValueError, match="missing or invalid"):
        vst3_host.validate_plugin_path("")
    with pytest.raises(ValueError, match="missing or invalid"):
        vst3_host.validate_plugin_path("bad.dll")
    with pytest.raises(FileNotFoundError, match="not installed"):
        vst3_host.validate_plugin_path(str(tmp_path / "missing.vst3"))


def test_vst3_path_validation_rejects_outside_root(tmp_path):
    plugin = tmp_path / "outside.vst3"
    plugin.touch()
    with patch.object(vst3_host, "vst3_roots", return_value=[tmp_path / "elsewhere"]):
        with pytest.raises(ValueError, match="outside configured"):
            vst3_host.validate_plugin_path(str(plugin))


def test_vst3_path_validation_allows_configured_root(tmp_path):
    plugin = tmp_path / "example.vst3"
    plugin.touch()
    with patch.object(vst3_host, "vst3_roots", return_value=[tmp_path]):
        assert vst3_host.validate_plugin_path(str(plugin)) == plugin.resolve()


def test_vst3_discovery_is_sorted_and_deduplicated(tmp_path):
    (tmp_path / "Zulu.vst3").touch()
    (tmp_path / "alpha.vst3").touch()
    with patch.object(vst3_host, "vst3_roots", return_value=[tmp_path, tmp_path]):
        plugins = vst3_host.discover_plugins()
    assert [entry["name"] for entry in plugins] == ["alpha", "Zulu"]
    assert all(Path(entry["path"]).is_absolute() for entry in plugins)


def test_vst3_runtime_availability_uses_optional_import():
    with patch.object(vst3_host.importlib.util, "find_spec", return_value=None):
        assert vst3_host.runtime_available() is False
    with patch.object(vst3_host.importlib.util, "find_spec", return_value=object()):
        assert vst3_host.runtime_available() is True


def test_vst3_inspect_parameters_omits_missing_values(monkeypatch, tmp_path):
    import sys
    plugin = SimpleNamespace(parameters={
        "dry": SimpleNamespace(raw_value=0.25),
        "missing": SimpleNamespace(raw_value=None),
    })
    monkeypatch.setitem(sys.modules, "pedalboard", SimpleNamespace(load_plugin=lambda _: plugin))
    assert vst3_host.inspect_parameters(tmp_path / "mock.vst3") == [{"name": "dry", "value": 0.25}]


def test_vst3_discovery_skips_symlinks_leaving_configured_root(tmp_path):
    root = tmp_path / "plugins"
    root.mkdir()
    outside = tmp_path / "outside.vst3"
    outside.touch()
    (root / "link.vst3").symlink_to(outside)
    with patch.object(vst3_host, "vst3_roots", return_value=[root]):
        assert vst3_host.discover_plugins() == []
