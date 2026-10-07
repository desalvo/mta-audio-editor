from pathlib import Path

JS = Path('app/static/app.js').read_text(encoding='utf-8')
CSS = Path('app/static/app.css').read_text(encoding='utf-8')


def test_exact_pdf_preview_is_injected_without_iframe():
    start = JS.index('async function previewProjectLyricsPdf')
    end = JS.index('async function resetTimedData', start)
    block = JS[start:end]
    assert "await probe.text()" in block
    assert "new DOMParser().parseFromString" in block
    assert "querySelector('.pages')" in block
    assert 'pdf-rendered-pages' in block
    assert '<iframe' not in block


def test_direct_pdf_page_styles_exist():
    assert '.pdf-rendered-pages .pdf-page img' in CSS
    assert '.pdf-rendered-pages .pdf-page figcaption' in CSS
