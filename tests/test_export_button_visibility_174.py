from pathlib import Path


def test_export_dialog_buttons_keep_text_visible():
    css = Path('app/static/app.css').read_text(encoding='utf-8')
    assert '0.2.0-r175: export controls must never clip or hide their labels.' in css
    assert '.export-dialog .format-option' in css
    assert 'white-space:normal!important' in css
    assert 'overflow:visible!important' in css
    assert '.export-dialog-tools .utility-btn' in css
    assert '-webkit-text-fill-color:#eef8ff!important' in css


def test_export_page_still_exposes_named_actions():
    js = Path('app/static/app.js').read_text(encoding='utf-8')
    for label in ('MTA format analysis', 'Render &amp; Preview Master', 'MP4 Karaoke'):
        assert label in js
