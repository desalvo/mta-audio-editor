from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text()

def test_dynamic_localization_observer():
    assert "function ensureLiveLocalization()" in JS
    assert "localizationObserver.observe(document.body" in JS
    assert "ensureLiveLocalization()" in JS

def test_english_native_dialogs_and_menus():
    for italian, english in [("Cerca dati brano online", "Search song information online"), ("Successivi", "Next"), ("Separa più cantanti", "Separate multiple singers"), ("Estrai marker", "Extract markers")]:
        assert f"['{italian}','{english}']" in JS
