from pathlib import Path

CSS = Path("app/static/app.css").read_text(encoding="utf-8")


def test_plugins_inspector_stacks_above_project_clip_browser():
    assert ".clip-browser{position:relative;z-index:10}" in CSS
    assert ".editor-grid{position:relative;z-index:30" in CSS
    assert ".inspector{position:relative;z-index:100" in CSS
    assert ".inspector-tabs{position:sticky;top:0;z-index:120" in CSS


def test_plugins_close_control_stays_in_visible_header():
    assert ".inspector-close{position:relative;right:auto;z-index:125" in CSS
    assert "min-width:34px!important" in CSS
    assert "align-self:stretch" in CSS
