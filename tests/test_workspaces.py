import io
import zipfile

from fastapi.testclient import TestClient


WRITE = {"X-MTA-Request": "1"}


def _create_active_user(auth, username: str, email: str, admin_id: int):
    user, token = auth.register_user(username, email, username.title(), "very-secure-password")
    assert auth.confirm_email(token)
    active = auth.update_user_admin(user["id"], admin_id, active=True)
    assert active["active"]
    return active


def _login(app, username: str):
    client = TestClient(app, headers=WRITE)
    r = client.post(
        "/login",
        data={"identifier": username, "password": "very-secure-password", "totp": ""},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return client


def test_dedicated_workspaces_sharing_archives_and_admin_dump(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "administrator-password")
    monkeypatch.setenv("MTA_ADMIN_EMAIL", "admin@example.test")

    import app.auth as auth
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    auth.init_auth_db()
    admin = auth.find_user("admin")
    user1 = _create_active_user(auth, "alice", "alice@example.test", admin["id"])
    user2 = _create_active_user(auth, "bob", "bob@example.test", admin["id"])

    alice = _login(main.app, "alice")
    bob = _login(main.app, "bob")

    r = alice.post("/api/projects?title=Alice%20Project&target=MTA8")
    assert r.status_code == 200
    project = r.json()
    pid = project["id"]
    assert project["owner_user_id"] == user1["id"]

    # Dedicated workspace: another user cannot see/open the project until shared.
    assert all(p["id"] != pid for p in bob.get("/api/projects").json())
    assert bob.get(f"/api/projects/{pid}").status_code == 404

    share = alice.post(f"/api/projects/{pid}/shares", json={"identifier": "bob"})
    assert share.status_code == 200
    assert bob.get(f"/api/projects/{pid}").status_code == 200
    assert any(p["id"] == pid for p in bob.get("/api/projects").json())

    # Shared collaborators can edit, but cannot delete or manage the share list.
    edited = bob.get(f"/api/projects/{pid}").json()
    edited["artist"] = "Shared Edit"
    assert bob.put(f"/api/projects/{pid}", json=edited).status_code == 200
    assert bob.delete(f"/api/projects/{pid}").status_code == 404
    assert bob.post(f"/api/projects/{pid}/shares", json={"identifier": "alice"}).status_code == 404

    # File management and preservation of originals.
    uploaded = alice.post(
        f"/api/projects/{pid}/files/upload",
        files={"file": ("original-session.txt", b"original payload", "text/plain")},
    )
    assert uploaded.status_code == 200
    files = alice.get(f"/api/projects/{pid}/files").json()
    assert any(x["category"] == "original" and x["name"] == "original-session.txt" for x in files)

    # Complete project archive includes the project and all original files.
    archive = alice.get(f"/api/projects/{pid}/archive")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        names = set(z.namelist())
        assert "project/project.json" in names
        assert "project/originals/original-session.txt" in names
        assert z.read("project/originals/original-session.txt") == b"original payload"

    # Importing a complete project creates an independent project owned by importer.
    imported = bob.post(
        "/api/project-archives/import",
        files={"file": ("alice-project.maeproj", archive.content, "application/zip")},
    )
    assert imported.status_code == 200
    imported_project = imported.json()
    assert imported_project["id"] != pid
    assert imported_project["owner_user_id"] == user2["id"]
    assert imported_project["shared_with_user_ids"] == []
    imported_files = bob.get(f"/api/projects/{imported_project['id']}/files").json()
    assert any(x["name"] == "original-session.txt" for x in imported_files)

    # Administrator can dump every user's projects and originals in one archive.
    admin_client = TestClient(main.app, headers=WRITE)
    lr = admin_client.post(
        "/login",
        data={"identifier": "admin", "password": "administrator-password", "totp": ""},
        follow_redirects=False,
    )
    assert lr.status_code == 303
    dump = admin_client.get("/api/admin/projects-dump")
    assert dump.status_code == 200
    with zipfile.ZipFile(io.BytesIO(dump.content)) as z:
        names = z.namelist()
        assert any(
            name.startswith(f"users/{user1['id']}-alice/projects/") and name.endswith("/originals/original-session.txt")
            for name in names
        )
        assert any(
            name.startswith(f"users/{user2['id']}-bob/projects/") and name.endswith("/originals/original-session.txt")
            for name in names
        )
