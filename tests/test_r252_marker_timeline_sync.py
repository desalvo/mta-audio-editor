from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT/'app/static/app.js').read_text()
CSS = (ROOT/'app/static/app.css').read_text()

def test_marker_doubleclick_edit_and_save():
    assert 'ondblclick="return beginTimelineMarkerInlineEdit(event,${index})"' in JS
    assert 'function beginTimelineMarkerInlineEdit(event,index)' in JS
    assert "marker.label=label" in JS
    assert "await saveMetaQuickEdit(null,'modifica nome marker')" in JS

def test_marker_playback_and_scrolling():
    assert "['lyrics','chords','markers']" in JS
    assert "marker-playback-active" in JS
    assert "marker-playback-exact" in JS
    assert "metaPlaybackScrollIndex={lyrics:-1,chords:-1,markers:-1}" in JS

def test_exact_alignment_and_wider_timestamps():
    assert '.timeline-chord-marker{transform:none}' in CSS
    assert '.project-marker-line::before' in CSS
    assert 'left:8px' in CSS
    assert 'meta-inline-time' in JS and 'min-width:145px' in CSS

def test_revision_metadata():
    revision=(ROOT/'REVISION').read_text().strip()
    assert revision.isdecimal()
    assert f'MTA_REVISION", "\\"{revision}\\"' in (ROOT/'mobile/android/app/build.gradle.kts').read_text()
