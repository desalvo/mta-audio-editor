from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text()

def test_caption_double_click_is_directly_editable():
    assert 'class="project-marker-caption" ondblclick="return beginTimelineMarkerInlineEdit(event,${index})"' in JS
    assert "target?.matches?.('.project-marker-caption')" in JS

def test_marker_drag_does_not_destroy_double_click_target():
    assert "if(event.target?.closest?.('.project-marker-caption, .timeline-marker-inline'))return;" in JS
    assert "if(!drag.moved||drag.startTime===drag.lastTime){return;}" in JS


def test_mixer_has_no_dead_master_preview_tab():
    assert '<button class="dock-tab">Master / Preview</button>' not in JS
    assert '${masterChannelHtml()}' in JS
