from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
NATIVE = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")


def test_new_project_reopens_through_canonical_open_flow():
    start = JS.index("async function createProjectFromDialog()")
    end = JS.index("async function openP", start)
    block = JS[start:end]
    assert "const createdId=created.id" in block
    assert "current=await api('/api/projects/'+createdId)" in block
    assert "focusProjectWorkspace()" in block
    assert "focusProjectWorkspace()" in block
    assert "current=created" not in block


def test_youtube_dialog_has_native_safe_clipboard_actions():
    assert "async function readSystemClipboard()" in JS
    assert "bridge?.read_clipboard?.()" in JS
    assert "pasteSystemClipboardTo('#youtubeImportUrl')" in JS
    assert "pasteSystemClipboardTo('#youtubeImportName')" in JS
    assert "Clipboard vuota o non accessibile" in JS
    assert "def read_clipboard(self) -> dict:" in NATIVE
    assert '"/usr/bin/pbpaste"' in NATIVE
    assert "OpenClipboard" in NATIVE


def test_youtube_import_dialog_is_structured_and_responsive():
    assert 'class="youtube-import-dialog"' in JS
    assert "1. Sorgente" in JS
    assert "2. Posizionamento" in JS
    assert 'class="youtube-options-grid"' in JS
    assert 'class="youtube-rights-check"' in JS
    assert ".youtube-import-section" in CSS
    assert ".youtube-input-row" in CSS
    assert "@media(max-width:650px)" in CSS
    assert "'youtube-import-modal'" in JS
