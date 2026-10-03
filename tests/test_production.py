import base64
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.models import Clip, Track

WRITE_HEADERS = {"X-MTA-Request": "1"}


def test_storage_roundtrip(tmp_path, monkeypatch):
    import app.storage as s
    monkeypatch.setattr(s, "ROOT", tmp_path.resolve())
    p = s.create_project("Demo", "MTA16")
    assert s.load_project(p.id).title == "Demo"
    p.artist = "Artist"
    s.save_project(p)
    assert s.list_projects()[0].artist == "Artist"
    with pytest.raises(ValueError):
        s.pdir("../../etc")
    s.delete_project(p.id)
    assert s.list_projects() == []


def test_security_auth(tmp_path, monkeypatch):
    import app.security as sec
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "secret")
    scope = {"type": "http", "headers": [(b"authorization", b"Basic " + base64.b64encode(b"admin:secret"))]}
    from starlette.requests import Request
    assert sec.check_basic_auth(Request(scope))
    scope_bad = {"type": "http", "headers": [(b"authorization", b"Basic " + base64.b64encode(b"admin:no"))]}
    assert not sec.check_basic_auth(Request(scope_bad))
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    assert sec.check_basic_auth(Request({"type": "http", "headers": []}))


def test_main_project_crud_and_public_docs(tmp_path, monkeypatch):
    import app.storage as storage
    import app.main as main
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setattr(main, "ROOT", tmp_path.resolve(), raising=False)
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    client = TestClient(main.app, headers={"X-MTA-Request": "1"})
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/about").json()["license"] == "EUPL-1.2"
    assert client.get("/docs/user").status_code == 200
    assert client.get("/docs/user/en").status_code == 200
    r = client.post("/api/projects", params={"title": "One", "target": "MTA8"}, headers=WRITE_HEADERS)
    assert r.status_code == 200
    pid = r.json()["id"]
    assert client.get(f"/api/projects/{pid}").status_code == 200
    data = client.get(f"/api/projects/{pid}").json(); data["artist"] = "X"
    assert client.put(f"/api/projects/{pid}", json=data, headers=WRITE_HEADERS).json()["artist"] == "X"
    assert len(client.get("/api/projects").json()) == 1
    assert client.delete(f"/api/projects/{pid}", headers=WRITE_HEADERS).status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_main_requires_auth(tmp_path, monkeypatch):
    import app.main as main
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "secret")
    c = TestClient(main.app, headers={"X-MTA-Request": "1"})
    assert c.get("/api/projects").status_code == 401
    token = base64.b64encode(b"admin:secret").decode()
    assert c.get("/api/projects", headers={"Authorization": f"Basic {token}"}).status_code == 200


def test_codec_import_and_metadata(tmp_path, monkeypatch):
    import app.codec as codec
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setattr(codec, "pdir", storage.pdir)
    p = storage.create_project("Imported")
    src = storage.pdir(p.id) / "source.mta"; src.write_bytes(b"x")
    info = {"streams": [
        {"index": 0, "codec_type": "audio", "tags": {"title": "Drums", "MTA_TYPE": "drums"}},
        {"index": 1, "codec_type": "attachment", "tags": {"filename": "meta.bin"}},
    ]}
    monkeypatch.setattr(codec, "ffprobe", lambda path: info)
    monkeypatch.setattr(codec, "media_duration_ms", lambda path: 1234)
    def fake_run(cmd):
        if "-dump_attachment:t:0" in cmd:
            Path(cmd[cmd.index("-dump_attachment:t:0") + 1]).write_bytes(b"meta")
        elif "-map" in cmd:
            Path(cmd[-1]).write_bytes(b"audio")
        return ""
    monkeypatch.setattr(codec, "run", fake_run)
    out = codec.import_mta(src, p)
    assert out.tracks[0].name == "Drums"
    assert out.preserved_attachments == ["meta.bin"]
    meta = codec._metadata_attachment(out)
    assert json.loads(meta.read_text())["schema"] == "mta-audio-editor/v3"


def test_codec_export_builds_container(tmp_path, monkeypatch):
    import app.codec as codec
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setattr(codec, "pdir", storage.pdir)
    p = storage.create_project("Export")
    audio = storage.pdir(p.id) / "audio" / "a.wav"; audio.write_bytes(b"a")
    p.tracks = [Track(id="t", name="T", type="drums", filename="a.wav", duration_ms=1000, clips=[Clip(id="c", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)])]
    storage.save_project(p)
    monkeypatch.setattr(codec, "render_track", lambda track, source, out: Path(out).write_bytes(b"wav"))
    seen = []
    monkeypatch.setattr(codec, "run", lambda cmd: seen.append(cmd) or "")
    monkeypatch.setattr(codec, "normalize_matroska_for_mta", lambda source, target: target.write_bytes(b"normalized") or 0)
    monkeypatch.setattr(codec, "obfuscate_media_copy", lambda source, target, offset: target.write_bytes(b"mta") or target)
    monkeypatch.setattr(codec, "inspect_cluster_transport", lambda path: {"first_cluster_is_canonical": True} if path.name == "mta-layout.mka" else {"media_xor_validated": True})
    out = storage.pdir(p.id) / "x.mta8"
    assert codec.export_mta(p, out) == out
    assert any("-f" in cmd and "matroska" in cmd for cmd in seen)

def test_main_editing_routes(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    c = TestClient(main.app, headers={"X-MTA-Request": "1"})
    p = storage.create_project("Routes")
    def fake_save(pid, file):
        dst = storage.pdir(pid) / "audio" / "fake.wav"; dst.write_bytes(b"x")
        return "fake.wav", dst, 2000
    monkeypatch.setattr(main, "_save_upload", fake_save)
    r = c.post(f"/api/projects/{p.id}/tracks?name=A&type=drums&offset_ms=100&sync_mode=manual", files={"file": ("a.wav", b"x", "audio/wav")}, headers=WRITE_HEADERS)
    assert r.status_code == 200
    tid = r.json()["tracks"][0]["id"]
    assert c.post(f"/api/projects/{p.id}/tracks/{tid}/move", json={"offset_ms": 50}, headers=WRITE_HEADERS).status_code == 200
    p2 = storage.load_project(p.id)
    # add a second reference track directly
    p2.tracks.append(Track(id="ref", name="Ref", type="bass", filename="fake.wav", duration_ms=2000, clips=[Clip(id="r", source_start_ms=0, source_end_ms=2000, timeline_start_ms=0)]))
    storage.save_project(p2)
    monkeypatch.setattr(main, "auto_align_ms", lambda a, b: 75)
    assert c.post(f"/api/projects/{p.id}/tracks/{tid}/autosync?reference_track_id=ref", headers=WRITE_HEADERS).json()["delta_ms"] == 75
    assert c.post(f"/api/projects/{p.id}/delete-range", json={"start_ms": 100, "end_ms": 200, "track_ids": [tid], "ripple": True}, headers=WRITE_HEADERS).status_code == 200
    assert c.post(f"/api/projects/{p.id}/delete-range", json={"start_ms": 300, "end_ms": 400, "track_ids": None, "ripple": True}, headers=WRITE_HEADERS).status_code == 200
    assert c.post(f"/api/projects/{p.id}/tracks/{tid}/replace?sync_mode=manual&offset_ms=10", files={"file": ("b.wav", b"x", "audio/wav")}, headers=WRITE_HEADERS).status_code == 200
    def fake_export(project, out):
        out.write_bytes(b"mta"); return out
    monkeypatch.setattr(main, "export_mta", fake_export)
    assert c.get(f"/api/projects/{p.id}/export").status_code == 200


def test_main_import_route(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage
    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    c = TestClient(main.app, headers={"X-MTA-Request": "1"})
    monkeypatch.setattr(main, "import_mta", lambda src, p: p)
    r = c.post("/api/import", files={"file": ("demo.mta8", b"abc", "application/octet-stream")}, headers=WRITE_HEADERS)
    assert r.status_code == 200


def test_request_integrity_header_and_admin_docs_protection(tmp_path, monkeypatch):
    import app.main as main

    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "secret")
    client = TestClient(main.app)
    token = base64.b64encode(b"admin:secret").decode()
    auth = {"Authorization": f"Basic {token}"}
    r = client.get("/docs/admin", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
    assert client.get("/docs/admin", headers=auth).status_code == 200
    assert client.post("/api/projects", headers=auth).status_code == 403
    assert client.post("/api/projects", headers={**auth, **WRITE_HEADERS}).status_code == 200


def test_project_file_paths_are_confined(tmp_path, monkeypatch):
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    project = storage.create_project("Safe")
    audio = storage.pdir(project.id) / "audio" / "a.wav"
    audio.write_bytes(b"x")
    project.tracks = [
        Track(
            id="t1",
            name="Track",
            type="other",
            filename="../../etc/passwd",
            duration_ms=100,
            clips=[Clip(id="c1", source_start_ms=0, source_end_ms=100, timeline_start_ms=0)],
        )
    ]
    with pytest.raises(ValueError):
        storage.validate_project_files(project)
