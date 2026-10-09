from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/templates/index.html").read_text()
JS = (ROOT / "app/static/app.js").read_text()
CSS = (ROOT / "app/static/app.css").read_text()

def test_compact_header_and_sidebar_branding():
    assert 'class="project-name-block"' not in HTML
    assert 'class="sidebar-brand"' in HTML
    assert '.topbar .transport{display:flex;flex-wrap:nowrap' in CSS

def test_mixer_insert_button_uses_channel_specific_manager():
    assert 'channel-insert-action' in JS
    assert 'openMixerInsertManager(\'${t.id}\')' in JS
    assert 'openMixerInsertManager(\'master\')' in JS
