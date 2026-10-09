from pathlib import Path


def test_timeline_tools_update_buttons_without_render():
    source = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text()
    block = source.split("function setTimelineTool(tool){", 1)[1].split("function copyTimelineSelection", 1)[0]
    assert "refreshTimelineToolControls();" in block
    assert "render();" not in block


def test_track_selection_updates_dom_without_render():
    source = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text()
    block = source.split("function selectTrack(id,event=null){", 1)[1].split("function trackAudibleNow", 1)[0]
    assert "classList.toggle('edit-selected'" in block
    assert "updateSel();" in block
    assert "render();" not in block
