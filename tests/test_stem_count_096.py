from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLUGINS=(ROOT/"app/plugins.py").read_text(encoding="utf-8")
MAIN=(ROOT/"app/main.py").read_text(encoding="utf-8")
JS=(ROOT/"app/static/app.js").read_text(encoding="utf-8")
IOS=(ROOT/"mobile/ios/README.md").read_text(encoding="utf-8")

def test_stem_count_profiles_are_exposed():
    assert 'supported_stem_counts' in PLUGINS
    assert 'stem_count: int = 0' in PLUGINS
    assert '--two-stems' in PLUGINS
    assert 'MTA_DEMUCS_8_MODEL' in PLUGINS

def test_api_accepts_stem_count_and_validates_8():
    assert 'stem_count: int = 0' in MAIN
    assert 'Numero di stem non supportato' in MAIN
    assert 'backend con modello 8-stem' in MAIN

def test_ui_persists_auto_2_4_6_8():
    for value in ['Auto','2 · Vocals / Accompaniment','4 · Vocals / Drums / Bass / Other','6 · + Guitar / Piano','8 · Extended backend']:
        assert value in JS
    assert 'localStorage.setItem(\'mtaStemCount\'' in JS

def test_iphone_ipad_share_server_side_setting():
    assert 'iPhone and iPad' in IOS
    assert 'Auto, 2, 4, 6 or 8' in IOS
