"""r255: avoid destructive event re-render and ship the vocal separator in native builds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_meta_panel_single_click_does_not_replace_double_click_target():
    js = (ROOT / 'app/static/app.js').read_text()
    body = js.split('function metaEventClick(event,kind,index)', 1)[1].split('\n}', 1)[0]
    assert 'refreshMetaPanels()' not in body
    assert 'classList.toggle' in body
    assert 'ondblclick="return beginMetaInlineEdit' in js


def test_rebuilt_meta_list_restores_scroll():
    js = (ROOT / 'app/static/app.js').read_text()
    body = js.split('function refreshMetaPanels(){', 1)[1].split('\n}', 1)[0]
    assert 'scrollTop' in body
    assert 'scrolls[i]' in body


def test_pdf_offsets_lyrics_for_chords_anchored_at_line_start():
    source = (ROOT / 'app/music_text.py').read_text()
    assert 'pre_line_chords = sorted(' in source
    assert 'lyric_margin = section_margin + chord_lead_width' in source
    assert 'wrap_text(lyric.text,"lyrics",lyric_width)' in source
    assert 'c.drawString(lyric_margin,y,safe(part))' in source


def test_native_macos_bundles_and_checks_audio_separator_runtime():
    spec = (ROOT / 'native/mta_audio_editor_native.spec').read_text()
    ci = (ROOT / '.github/workflows/ci-cd.yml').read_text()
    req = (ROOT / 'requirements-stems.txt').read_text()
    assert '"audio_separator"' in spec
    assert '"onnxruntime"' in spec
    assert 'from audio_separator.separator import Separator' in ci
    assert 'import onnxruntime' in ci
    assert 'audio-separator[cpu]' in req
