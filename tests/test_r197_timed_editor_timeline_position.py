from pathlib import Path

APP_JS = Path('app/static/app.js').read_text()
APP_CSS = Path('app/static/app.css').read_text()


def test_timed_editors_follow_current_timeline_position():
    assert 'function focusTimedEditorAtTimeline()' in APP_JS
    assert 'Number(playCursorMs||0)' in APP_JS
    assert "document.querySelectorAll('#timedEditorRows .timed-editor-row')" in APP_JS
    assert "parseTimedEditorTime(row.querySelector('.timed-start')?.value)" in APP_JS
    assert "scrollIntoView({block:'center',inline:'nearest'})" in APP_JS
    assert 'requestAnimationFrame(focusTimedEditorAtTimeline)' in APP_JS


def test_timed_editor_current_row_is_visually_marked():
    assert "best.classList.add('timed-current-row')" in APP_JS
    assert '.timed-editor-row.timed-current-row' in APP_CSS


def test_timed_editor_navigation_does_not_move_transport():
    body = APP_JS.split('function focusTimedEditorAtTimeline()', 1)[1].split('function editTimed(kind)', 1)[0]
    assert 'playCursorMs=' not in body
    assert '.currentTime=' not in body
