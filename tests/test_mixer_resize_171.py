from pathlib import Path

from app.models import Project


def test_project_persists_mixer_height():
    p = Project(id="p", title="Mixer")
    assert p.mixer_height_px == 262
    p2 = Project.model_validate({**p.model_dump(), "mixer_height_px": 420})
    assert p2.mixer_height_px == 420


def test_mixer_has_resizer_and_native_height_guard():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    assert 'id="mixerResizer"' in js
    assert "function bindMixerResizer()" in js
    assert "current.mixer_height_px" in js
    assert "--mixer-height" in css
    assert "body.native-single-user .main-area" in css
    assert "overflow-y:auto!important" in css
