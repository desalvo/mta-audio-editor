from pathlib import Path

SRC = (Path(__file__).parents[1] / "app/static/app.js").read_text()
CSS = (Path(__file__).parents[1] / "app/static/app.css").read_text()

def test_timeline_marker_drag_commits_and_persists():
    assert 'function beginTimelineMarkerDrag(event,index)' in SRC
    assert 'onpointerdown="beginTimelineMarkerDrag(event,${index})"' in SRC
    assert 'drag.item.time_ms=drag.lastTime' in SRC
    assert "await saveMetaQuickEdit(null,'spostamento marker')" in SRC

def test_context_marker_mutations():
    assert 'function openTimelineMarkerContextMenu(event,index)' in SRC
    for a in ('add','disable','enable','delete'):
        assert f'data-action="{a}"' in SRC
    assert 'marker.disabled=true' in SRC
    assert 'marker.disabled=false' in SRC

def test_marker_handle_and_disabled_visibility():
    assert 'project-marker-handle' in SRC and 'project-marker-handle' in CSS
    assert ".filter(({m})=>!m.deleted)" in SRC
    assert '.marker-disabled' in CSS


def test_marker_line_is_vivid_and_distinct_from_tracks():
    assert '--marker-visibility-accent:#ff3f94' in CSS
    assert 'border-left:3px solid var(--marker-visibility-accent)' in CSS
    assert 'background:#f72585' in CSS
    assert '.project-marker-line.dragging' in CSS
