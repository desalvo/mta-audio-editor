from pathlib import Path

CSS = Path("app/static/app.css").read_text(encoding="utf-8")
JS = Path("app/static/app.js").read_text(encoding="utf-8")


def test_inspector_header_is_sticky_and_body_scrolls():
    assert ".inspector{position:relative;z-index:30" in CSS
    assert ".inspector-tabs{position:sticky;top:0;z-index:40" in CSS
    assert ".inspector-body{flex:1 1 auto;min-height:0;overflow-y:auto" in CSS
    assert "overflow:hidden!important;display:flex;flex-direction:column" in CSS


def test_inspector_header_contains_close_and_tabs():
    block = JS[JS.index("function inspectorHtml()") : JS.index("function closeInspectorPanel") ]
    for label in ["Inspector", "Stems", "Metadata", "inspector-close"]:
        assert label in block


def test_revision_metadata_is_consistent():
    rev = Path("REVISION").read_text().strip()
    assert rev == "193"
    assert f"versionCode = 20{rev}" in Path("mobile/android/app/build.gradle.kts").read_text()
    assert f"<string>20{rev}</string>" in Path("mobile/ios/MTAEditorMobile/Info.plist").read_text()
