from pathlib import Path


def test_lyrics_exports_are_rendered_only_when_lyrics_exist():
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert "const hasLyrics=!!(current.lyrics||[]).length" in js
    assert "mixerMetaTab==='lyrics'&&hasLyrics" in js
    assert "TXT Lyrics" in js
    assert "Anteprima PDF ${hasChords?'Lyrics + Chords':'Lyrics'}" in js
    assert "Scarica PDF ${hasChords?'Lyrics + Chords':'Lyrics'}" in js


def test_lyrics_plus_chords_exports_require_chords():
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert "hasChords?`<button class=\"tool\" onclick=\"downloadProjectLyrics(true)\">TXT Lyrics + Chords</button>" in js
    assert "ChordPro Lyrics + Chords" in js
    assert "if(withChords&&!(current.chords||[]).some(ch=>!ch.excluded))" in js
    assert "if(!(current.chords||[]).some(ch=>!ch.excluded))return toast('Il progetto non contiene chords attivi')" in js


def test_pdf_preview_title_matches_available_content():
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert "title=hasChords?'Anteprima PDF · Lyrics + Chords':'Anteprima PDF · Lyrics'" in js
