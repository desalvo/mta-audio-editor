"""Render the actual editor CSS so toolbar/browser never push lanes to the bottom."""
from pathlib import Path
import pytest

weasyprint = pytest.importorskip('weasyprint')


@pytest.mark.parametrize('collapsed', [True, False])
def test_three_editor_rows_anchor_tracks_below_browser(collapsed):
    css = (Path(__file__).resolve().parents[1] / 'app/static/app.css').read_text()
    html = '''<div class="editor-content" id="editor" style="height:600px;width:1100px">
<div class="editor-toolbar" id="toolbar" style="height:52px">Toolbar</div>
<section class="clip-browser CLASS" id="clips">Clip browser</section>
<div class="editor-grid" id="grid"><div class="track-column"><div class="track-column-head">Tracks</div><div class="track-head" id="track">Track 1</div></div><div class="track-resizer"></div><div class="timeline-pane"><div class="ruler">Ruler</div><div class="lanes"><div class="lane" id="lane">Audio</div></div></div></div></div>'''.replace('CLASS', 'collapsed' if collapsed else '')
    extra = '@page{size:1200px 900px;margin:0} body{margin:0} .editor-toolbar{min-height:52px}'
    doc = weasyprint.HTML(string=html, media_type='screen').render(stylesheets=[
        weasyprint.CSS(string=css), weasyprint.CSS(string=extra)])
    boxes = {}
    for box in doc.pages[0]._page_box.descendants():
        if box.element is not None and box.element.get('id') not in boxes:
            boxes[box.element.get('id')] = box
    assert boxes['grid'].position_y < 200
    assert boxes['grid'].height > 400
    assert boxes['track'].position_y == boxes['lane'].position_y
    if collapsed:
        assert boxes['grid'].position_y == pytest.approx(82, abs=1)
