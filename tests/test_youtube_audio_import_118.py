from pathlib import Path

import pytest


def test_youtube_url_validator_accepts_single_video_urls():
    from app.main import _validated_youtube_url

    assert _validated_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert _validated_youtube_url("https://youtu.be/dQw4w9WgXcQ")
    assert _validated_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")


def test_youtube_url_validator_rejects_non_youtube_and_playlist_only():
    from app.main import _validated_youtube_url

    with pytest.raises(ValueError):
        _validated_youtube_url("https://example.com/watch?v=dQw4w9WgXcQ")
    with pytest.raises(ValueError):
        _validated_youtube_url("https://www.youtube.com/playlist?list=PL123456789")
    with pytest.raises(ValueError):
        _validated_youtube_url("http://www.youtube.com/watch?v=dQw4w9WgXcQ")


def test_youtube_import_ui_and_dependency_are_present():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8")
    assert "Import YouTube" in html
    assert "openYoutubeImport" in js
    assert "/youtube-import-jobs" in js
    assert "confirm_rights:true" in js
    assert "yt-dlp==2026.8.19" in requirements
