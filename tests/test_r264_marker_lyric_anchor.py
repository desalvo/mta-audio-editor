from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')


def test_marker_grouping_uses_lyric_start_and_supports_manual_anchor():
    assert 'const markersFor=(li)' in JS
    assert 'lyrics.map(l=>Number(l.time_ms||0))' in JS
    assert 'm.manual_lyric_anchor' in JS
    assert 'Number(m.anchor_lyric_time_ms)===times[li]' in JS


def test_marker_drag_drop_and_reset_manual_assignment():
    assert 'function dragLyricsMarker(event,index)' in JS
    assert 'function dropLyricsMarker(event,lineIndex)' in JS
    assert 'function restoreLyricsMarkerAutomatic(index)' in JS
    assert "['marker-auto',tr('Restore automatic lyric placement','Ripristina posizione automatica')]" in JS
    assert 'updateLyricsMarkerAnchors(oldTime,newTime)' in JS
