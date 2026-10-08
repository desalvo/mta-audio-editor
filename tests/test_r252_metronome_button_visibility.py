from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_metronome_button_is_visible_and_accessible():
    js=(ROOT/'app/static/app.js').read_text()
    css=(ROOT/'app/static/app.css').read_text()
    assert 'class="primary metronome-generate-button"' in js
    assert 'onclick="applyMetronomeSettings()">Genera metronomo</button>' in js
    assert '.metronome-modal-actions .metronome-generate-button' in css
    assert 'color:#ffffff!important;-webkit-text-fill-color:#ffffff!important' in css
    assert 'min-width:164px' in css
