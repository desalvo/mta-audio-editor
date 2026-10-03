from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MOBILE_URL = "https://mta-audio-editor.apps.desalvo.eu"


def test_bilingual_manual_sources_and_pdfs_exist():
    for rel in (
        "app/docs/user.html",
        "app/docs/user-en.html",
        "app/docs/admin.html",
        "app/docs/admin-en.html",
        "app/docs/MTA-Audio-Editor-User-Manual-IT.pdf",
        "app/docs/MTA-Audio-Editor-User-Manual-EN.pdf",
        "app/docs/MTA-Audio-Editor-Administrator-Manual-IT.pdf",
        "app/docs/MTA-Audio-Editor-Administrator-Manual-EN.pdf",
    ):
        p = ROOT / rel
        assert p.is_file() and p.stat().st_size > 1000


def test_manual_covers_include_photo_logo_plate_and_platforms():
    for rel in ("app/docs/user.html", "app/docs/user-en.html", "app/docs/admin.html", "app/docs/admin-en.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "cover-daw-studio.png" in text
        assert "/static/logo.svg" in text
        assert "__VERSION__" in text and "__BUILD__" in text
        assert "Windows" in text and "macOS Apple Silicon" in text
        assert "Android" in text and "iOS / iPadOS" in text


def test_user_manual_is_comprehensive_and_visual():
    for rel in ("app/docs/user.html", "app/docs/user-en.html"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert text.count("<h2") >= 23
        for asset in (
            "daw-overview.png", "transport.png", "timeline.png", "mixer.png",
            "export-panel.png", "project-lifecycle.png", "playback-sync.png",
            "mobile-connection.png", "mta-profiles.png",
        ):
            assert asset in text


def test_mobile_default_service_is_hidden_from_user_docs():
    for rel in (
        "app/docs/user.html", "app/docs/user-en.html",
        "docs/MOBILE_APPS.md", "docs/MOBILE_APPS_IT.md", "docs/MOBILE_APPS_EN.md",
    ):
        assert DEFAULT_MOBILE_URL not in (ROOT / rel).read_text(encoding="utf-8")


def test_mta_spec_has_bilingual_detailed_descriptions_without_reverse_engineering_label():
    for rel in ("docs/MTA_FORMAT_FINAL_SPEC_IT.md", "docs/MTA_FORMAT_FINAL_SPEC_EN.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        low = text.lower()
        assert "reverse engineering" not in low
        assert "ingegneria inversa" not in low
        for marker in ("984", "SimpleBlock", "MIDITK", "NoteOn", "PreCntUSec", "Click", "Melody"):
            assert marker in text
