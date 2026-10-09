from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_insert_setup_buttons_have_explicit_style_scope():
    js = (ROOT / "app/static/app.js").read_text()
    css = (ROOT / "app/static/app.css").read_text()
    assert 'class="modal-actions insert-setup-actions"' in js
    assert "Save preset & apply" in js and ">Cancel</button>" in js
    assert ".insert-setup-actions button" in css
    assert "-webkit-text-fill-color:#f3f9ff!important" in css
    assert ".insert-setup-actions button:disabled" in css
