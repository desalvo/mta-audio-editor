from pathlib import Path
from PIL import Image


def test_native_icon_uses_graphic_mark_without_product_wordmark():
    root = Path(__file__).resolve().parents[1]
    icons = root / "native" / "icons"
    source = (icons / "mta-audio-editor-mark.svg").read_text(encoding="utf-8")

    assert "MTA Audio Editor</text>" not in source
    assert "Multitrack Audio Workstation" not in source
    assert "<text" not in source
    assert "waveform" in source.lower()

    png = Image.open(icons / "mta-audio-editor-1024.png")
    assert png.size == (1024, 1024)
    assert png.mode in {"RGBA", "LA", "P"}


def test_native_builds_reference_graphic_only_icon_assets():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "native" / "mta_audio_editor_native.spec").read_text(encoding="utf-8")
    installer = (root / "native" / "windows-installer.iss").read_text(encoding="utf-8")

    assert "mta-audio-editor.ico" in spec
    assert "mta-audio-editor.icns" in spec
    assert r"SetupIconFile=icons\mta-audio-editor.ico" in installer
