from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

def test_new_lyrics_line_uses_standard_timestamp_format():
    start = APP_JS.index("function addLyricsEditorLine()")
    body = APP_JS[start: APP_JS.index("function addChordEditorEvent()", start)]
    assert "Tempo iniziale (m:ss.mmm / mm:ss.mmm)" in body
    assert "lyricsChordsEditorPosition(Math.max(0,playCursorMs||0))" in body
    assert "parseLyricsChordsEditorPosition(raw)" in body
    assert "Tempo iniziale in secondi" not in body
    assert "Number(t)*1000" not in body
