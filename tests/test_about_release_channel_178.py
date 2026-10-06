from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_about_exposes_build_release_channel(monkeypatch):
    from fastapi.testclient import TestClient
    import app.main as main
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    payload = TestClient(main.app, headers={"X-MTA-Request": "1"}).get("/api/about").json()
    assert payload["release_channel"] in {"early", "stable"}

def test_early_source_package_identifies_revision():
    assert (ROOT / "RELEASE_CHANNEL").read_text(encoding="utf-8").strip() == "early"
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "const revisionLabel=channel==='early'?`r${info.revision||''}`:'stable'" in js
    assert "String(info.release_channel||'stable')" in js

def test_platform_revision_metadata_matches_revision():
    rev = (ROOT / "REVISION").read_text(encoding="utf-8").strip()
    android = (ROOT / "mobile/android/app/build.gradle.kts").read_text(encoding="utf-8")
    ios = (ROOT / "mobile/ios/MTAEditorMobile/Info.plist").read_text(encoding="utf-8")
    assert f'MTA_REVISION", "\\\"{rev}\\\"' in android
    assert f"<key>MTAEditorRevision</key><string>{rev}</string>" in ios
