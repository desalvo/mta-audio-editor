from pathlib import Path


def test_reset_endpoints_clear_content_and_analysis_metadata():
    source = Path('app/main.py').read_text(encoding='utf-8')
    assert '@app.post("/api/projects/{pid}/lyrics/reset")' in source
    assert 'project.lyrics = []' in source
    assert 'project.lyrics_engine = ""' in source
    assert 'project.lyrics_model = ""' in source
    assert '@app.post("/api/projects/{pid}/chords/reset")' in source
    assert 'project.chords = []' in source
    assert 'project.chords_engine = ""' in source
    assert 'project.chords_model = ""' in source


def test_pdf_endpoint_supports_inline_preview():
    source = Path('app/main.py').read_text(encoding='utf-8')
    assert 'preview: bool = False' in source
    assert 'Content-Disposition' in source
    assert 'inline; filename=' in source


def test_web_ui_exposes_independent_resets_and_pdf_preview():
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    assert "resetTimedData('lyrics')" in js
    assert "resetTimedData('chords')" in js
    assert 'previewProjectLyricsPdf()' in js
    assert 'Anteprima PDF · Lyrics + Chords' in js
    block = js[js.index('async function previewProjectLyricsPdf'):js.index('async function resetTimedData')]
    assert 'pdf-rendered-pages' in block
    assert '<iframe' not in block
    assert '/lyrics.pdf.preview' in block
    assert 'response.blob()' not in block
    assert 'await probe.text()' in block
    assert "querySelector('.pages')" in block
    assert "credentials:'same-origin'" in block
    assert 'pdf-sheet' not in block


def test_pdf_preview_css_is_responsive():
    css = Path('app/static/app.css').read_text(encoding='utf-8')
    assert '.pdf-preview-wrap' in css
    assert '.pdf-preview-frame' in css
    assert '72dvh' in css
