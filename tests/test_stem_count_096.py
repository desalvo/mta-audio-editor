from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLUGINS=(ROOT/"app/plugins.py").read_text(encoding="utf-8")
MAIN=(ROOT/"app/main.py").read_text(encoding="utf-8")
JS=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
IOS=(ROOT/"mobile/ios/README.md").read_text(encoding="utf-8")

def test_stem_count_profiles_are_model_driven():
    assert 'model_profiles' in PLUGINS
    assert 'MTA_DEMUCS_MODEL_REGISTRY' in PLUGINS
    assert 'stem_count: int = 0' in PLUGINS
    assert '--two-stems' in PLUGINS
    assert 'count > 64' in PLUGINS

def test_api_accepts_incremental_model_counts():
    assert 'stem_count: int = 0' in MAIN
    assert 'cardinalità tra 2 e 64' in MAIN
    assert 'Nessun modello configurato fornisce' in MAIN
    assert '_mobile_demucs_inventory' in MAIN

def test_ui_uses_dynamic_stem_counts():
    assert 'stem.supported_stem_counts' in JS
    assert 'model_profiles' in JS
    assert 'Auto · model-driven' in JS
    assert "localStorage.setItem('mtaStemCount'" in JS

def test_mobile_docs_describe_model_driven_counts():
    assert 'model-driven' in IOS.lower()
    assert '16' in IOS
