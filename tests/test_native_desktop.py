from pathlib import Path

from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def test_native_single_user_mode_has_no_login_or_user_management(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_NATIVE_SINGLE_USER", "true")
    monkeypatch.setattr(main, "NATIVE_SINGLE_USER", True)

    client = TestClient(main.app, headers=WRITE)

    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["native_single_user"] is True

    projects = client.get("/api/projects")
    assert projects.status_code == 200

    login = client.get("/login", follow_redirects=False)
    assert login.status_code == 303
    assert login.headers["location"] == "/"

    assert client.get("/api/admin/users").status_code == 404
    assert client.get("/api/account").status_code == 404

    project = client.post("/api/projects?title=Native&target=MTA8").json()
    assert client.get(f"/api/projects/{project['id']}/shares").status_code == 404


def test_native_ui_hides_multiuser_controls():
    root = Path(__file__).resolve().parents[1]
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    launcher = (root / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")

    assert '__BODY_CLASS__' in html
    assert html.count("auth-managed") >= 4
    assert ".native-single-user .auth-managed" in css
    assert 'MTA_NATIVE_SINGLE_USER' in launcher
    assert '127.0.0.1' in launcher
    assert "native-windows:" in workflow
    assert "native-macos:" in workflow
    assert "native-release:" in workflow
    assert "windows-installer.iss" in workflow
    assert "hdiutil create" in workflow
