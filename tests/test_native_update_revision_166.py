from native import update_manager as updater


def test_early_manifest_combines_version_and_revision(monkeypatch):
    release = {
        "name": "MTA Audio Editor Early Release",
        "tag_name": "early-main",
        "html_url": "https://github.com/desalvo/mta-audio-editor/releases/tag/early-main",
        "assets": [
            {
                "id": 1,
                "name": "early-update.json",
                "browser_download_url": "https://example.invalid/early-update.json",
            },
            {
                "id": 10,
                "name": "MTA-Audio-Editor-0.2.0-r165-Windows-x64-Setup.exe",
                "browser_download_url": "https://example.invalid/r165.exe",
                "created_at": "2026-10-06T11:00:00Z",
            },
            {
                "id": 11,
                "name": "MTA-Audio-Editor-0.2.0-r166-Windows-x64-Setup.exe",
                "browser_download_url": "https://example.invalid/r166.exe",
                "created_at": "2026-10-06T12:00:00Z",
            },
        ],
    }
    manifest = {"channel": "early", "version": "0.2.0", "revision": "166"}

    def fake_get_json(url):
        if url.endswith("early-update.json"):
            return manifest
        return release

    monkeypatch.setattr(updater, "_get_json", fake_get_json)
    monkeypatch.setattr(updater.os, "name", "nt")

    info = updater.check_for_update("0.2.0-r165", "early")
    assert info["latest_version"] == "0.2.0-r166"
    assert info["available"] is True
    assert info["asset_name"].endswith("0.2.0-r166-Windows-x64-Setup.exe")


def test_early_asset_fallback_finds_newest_revision(monkeypatch):
    release = {
        "name": "MTA Audio Editor Early Release",
        "tag_name": "early-main",
        "assets": [
            {"id": 1, "name": "MTA-Audio-Editor-0.2.0-r164-macOS-arm64.dmg", "created_at": "2026-10-06T10:00:00Z"},
            {"id": 2, "name": "MTA-Audio-Editor-0.2.0-r166-macOS-arm64.dmg", "created_at": "2026-10-06T12:00:00Z"},
        ],
    }
    monkeypatch.setattr(updater, "_get_json", lambda _url: release)
    monkeypatch.setattr(updater, "sys_platform", lambda: "darwin")
    monkeypatch.setattr(updater.platform, "machine", lambda: "arm64")

    info = updater.check_for_update("0.2.0-r165", "early")
    assert info["latest_version"] == "0.2.0-r166"
    assert info["available"] is True
    assert info["asset_name"].endswith("0.2.0-r166-macOS-arm64.dmg")


def test_release_revision_comparison_is_not_collapsed():
    assert updater.is_newer("0.2.0-r166", "0.2.0-r165")
    assert not updater.is_newer("0.2.0-r165", "0.2.0-r165")
    assert not updater.is_newer("0.2.0-r164", "0.2.0-r165")
    assert updater.is_newer("0.3.0-r1", "0.2.0-r999")
