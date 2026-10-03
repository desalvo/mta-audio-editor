from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = (ROOT / "app/models.py").read_text(encoding="utf-8")
CODEC = (ROOT / "app/codec.py").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

def test_mta16_corpus_profile_exists():
    assert "mlive_mta16_default" in MODELS
    assert 'MTA16_DEFAULT_LAYOUT = {"click": 1, "melody": 9}' in CODEC

def test_mta16_auto_uses_corpus_profile():
    assert 'return "mlive_mta16_default"' in CODEC

def test_mta16_export_preserves_physical_melody_slot():
    assert "force_mta16_roles" in CODEC
    assert "max_slot = max(max_slot, 9)" in CODEC
    assert 'slot_number == 9' in CODEC
    assert '"melody"' in CODEC

def test_export_plan_exposes_default_roles_without_forcing_manual_mapping():
    assert '"mta16_default_roles": {"click": 1, "melody": 9}' in MAIN
    assert '"requires_explicit_click_mapping": False' in MAIN

def test_ui_explains_corpus_default():
    assert "MTA16 M-Live · default corpus (Click 1, Melody 9)" in JS
    assert "Default MTA16:" in JS
