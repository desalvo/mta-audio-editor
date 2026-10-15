"""Regression coverage for native server identity and diagnostic metadata."""
from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]

def test_release_metadata_r209():
    assert (ROOT / "VERSION").read_text().strip() == "0.3.0"
    assert (ROOT / "REVISION").read_text().strip() == "209"
    assert (ROOT / "BUILD_INFO").read_text().strip().isdigit()

def test_server_staging_preserves_identity():
    content = (ROOT / "scripts/server_packages/prepare_runtime.py").read_text()
    assert "('VERSION', 'REVISION', 'BUILD_INFO', 'RELEASE_CHANNEL')" in content
    assert "shutil.copy2(metadata, app / filename)" in content

def test_about_and_ui_include_installation_and_gpu():
    source = (ROOT / "app/main.py").read_text()
    assert '"installation": runtime_installation()' in source
    assert '"acceleration": runtime_acceleration()' in source
    ui = (ROOT / "app/static/app.js").read_text()
    assert "info.installation" in ui and "info.acceleration" in ui

def test_frontend_cache_key_matches_release():
    assert 'app.js?v=0.3.0-r209' in (ROOT / "app/templates/index.html").read_text()

def test_ai_arranger_range_inputs_are_present():
    ui = (ROOT / "app/static/app.js").read_text()
    for name in ("aiRemixScope", "aiRemixStartSec", "aiRemixEndSec"):
        assert name in ui
