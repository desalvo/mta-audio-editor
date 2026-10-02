from pathlib import Path
import os
import subprocess
import sys


def test_native_launcher_files_and_workflow_exist():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    launcher = (root / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    spec = (root / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    installer = (root / "native/windows-installer.iss").read_text(encoding="utf-8")

    assert "native-windows:" in workflow
    assert "native-macos:" in workflow
    assert "native-release:" in workflow
    assert "windows-latest" in workflow
    assert "macos-15-intel" in workflow
    assert "macos-15" in workflow
    assert "pyinstaller --noconfirm --clean native/mta_audio_editor_native.spec" in workflow
    assert "MTA_NATIVE_SINGLE_USER" in launcher
    assert "127.0.0.1" in launcher
    assert "collect_all" in spec
    assert "PrivilegesRequired=lowest" in installer
    assert "{localappdata}\\Programs\\MTA Audio Editor" in installer


def test_native_single_user_mode_has_no_login_or_user_management(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = r"""
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"X-MTA-Request": "1"})

session = client.get("/api/session")
assert session.status_code == 200, session.text
data = session.json()
assert data["native_single_user"] is True
assert data["username"] == "local"

about = client.get("/api/about")
assert about.status_code == 200
assert about.json()["native_single_user"] is True

assert client.get("/login", follow_redirects=False).status_code == 303
assert client.get("/account", follow_redirects=False).status_code == 303
assert client.get("/admin/users", follow_redirects=False).status_code == 303
assert client.get("/api/admin/users", follow_redirects=False).status_code == 404

created = client.post("/api/projects?title=Native%20Project&target=MTA8")
assert created.status_code == 200, created.text
pid = created.json()["id"]
assert client.get(f"/api/projects/{pid}").status_code == 200
assert client.get(f"/api/projects/{pid}/shares").status_code == 404
"""
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(root),
            "MTA_NATIVE_SINGLE_USER": "true",
            "MTA_ALLOW_INSECURE_NO_AUTH": "true",
            "MTA_DATA_DIR": str(tmp_path),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
