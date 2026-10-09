from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_project_seek_slider_and_live_update():
    html=(ROOT/'app/templates/index.html').read_text()
    js=(ROOT/'app/static/app.js').read_text()
    assert 'id="transportSeek"' in html
    assert 'oninput="seekProjectFromSlider(this.value)"' in html
    assert 'function updateTransportSeekSlider()' in js
    assert 'updateTransportSeekSlider()}' in js
    assert 'goToTimestamp(Math.round(duration*fraction))' in js

def test_metadata_hover_kept_in_viewport():
    js=(ROOT/'app/static/app.js').read_text()
    css=(ROOT/'app/static/app.css').read_text()
    assert 'row.getBoundingClientRect()' in js
    assert 'window.innerHeight-height-8' in js
    assert 'position:fixed!important' in css
