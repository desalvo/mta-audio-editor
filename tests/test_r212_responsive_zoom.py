from pathlib import Path


def test_zoom_controls_include_steps_reset_and_presets():
    html = Path("app/templates/index.html").read_text()
    assert 'onclick="stepZoom(-1)"' in html
    assert 'onclick="stepZoom(1)"' in html
    assert 'ondblclick="resetZoomDefault(event)"' in html
    assert 'id="zoomPreset"' in html
    for value in ("pct:100", "seconds:5", "beats:1", "bars:1", "bars:4", "fit"):
        assert f'value="{value}"' in html


def test_zoom_drag_uses_coarse_preview_then_commits_one_render():
    js = Path("app/static/app.js").read_text()
    assert "function beginZoomPreview()" in js
    assert "function previewZoom(v,presetValue=null)" in js
    assert "function commitZoom(v,presetValue=null)" in js
    assert "l.style.transform=`scaleX(${scale})`" in js
    assert "ruler.style.transform=`scaleX(${scale})`" in js
    preview = js.split("function previewZoom(v,presetValue=null)", 1)[1].split("function commitZoom", 1)[0]
    assert "render()" not in preview
    commit = js.split("function commitZoom(v,presetValue=null)", 1)[1].split("function setZoom", 1)[0]
    assert "render()" in commit


def test_musical_zoom_presets_follow_bpm_and_time_signature():
    js = Path("app/static/app.js").read_text()
    assert "const bpm=Math.max(1,Number(current?.bpm||120)),quarter=60/bpm" in js
    assert "barSeconds=quarter*num*4/den" in js
    assert "zoomForVisibleSeconds(quarter*n)" in js
    assert "zoomForVisibleSeconds(barSeconds*n)" in js


def test_zoom_range_supports_deep_musical_zoom():
    model = Path("app/models.py").read_text()
    html = Path("app/templates/index.html").read_text()
    assert "timeline_zoom_px_per_sec: int = Field(default=70, ge=25, le=1200)" in model
    assert 'id="topZoom" type="range" min="25" max="1200"' in html


def test_r212_mobile_build_numbers_match_revision():
    rev = int(Path("REVISION").read_text().strip())
    assert rev >= 212
    assert f"versionCode = {20000 + rev}" in Path("mobile/android/app/build.gradle.kts").read_text()
    assert f"<key>CFBundleVersion</key><string>{20000 + rev}</string>" in Path("mobile/ios/MTAEditorMobile/Info.plist").read_text()
