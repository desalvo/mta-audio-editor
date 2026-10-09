from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_bpm_modes_contract():
    js = (ROOT / "app/static/app.js").read_text()
    assert "function setManualProjectBpm" in js
    assert "function resetProjectBpm" in js
    assert "function openBpmContextMenu" in js
    assert "setManualProjectBpm(bpm);" in js
    assert "current.base_bpm=bpm;" in js
    assert "current.original_bpm=projectOriginalBpm()" in js
    assert "function setProjectBpm(v)" in js
    assert "current.bpm=n;" in js

def test_bpm_menu_and_model():
    html = (ROOT / "app/templates/index.html").read_text()
    model = (ROOT / "app/models.py").read_text()
    assert 'oncontextmenu="return openBpmContextMenu(event)"' in html
    assert "original_bpm: float | None" in model
