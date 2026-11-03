"""Private account messaging and delivery boundaries."""
from io import BytesIO
import shutil
import subprocess
import wave

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app import account_lifecycle, auth
from app.main import app
from test_r210_legal_documents import cookie


@pytest.fixture
def clients(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "DATA_ROOT", tmp_path)
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "direct-messaging-test-password")
    auth.init_auth_db()
    users = {}
    with auth.db() as con:
        for name in ("alice", "bob", "charlie"):
            uid = con.execute(
                """INSERT INTO users(username,email,display_name,password_hash,active,email_confirmed,role,created_at,updated_at)
                   VALUES(?,?,?,?,1,1,'user',1,1)""",
                (name, name + "@example.test", name.title(), "unused"),
            ).lastrowid
            users[name] = uid
    return {name: (uid, TestClient(app, cookies=cookie(uid), headers={"X-MTA-Request": "1"}))
            for name, uid in users.items()}


def test_direct_conversation_and_outbox(clients, monkeypatch):
    alice_id, alice = clients["alice"]
    bob_id, bob = clients["bob"]
    _, charlie = clients["charlie"]
    base = "/api/messages"
    assert TestClient(app).get(base + "/unread").status_code == 401
    assert alice.get(base + "/contacts?q=bo").json() == [{"id": bob_id, "username": "bob", "display_name": "Bob"}]
    url = f"{base}/threads/{bob_id}"
    assert TestClient(app, cookies=cookie(alice_id)).post(url, json={"text": "no CSRF marker"}).status_code == 403
    response = alice.post(url, json={"text": "<b>Test</b>"})
    assert response.status_code == 201, response.text
    mid = response.json()["id"]
    assert bob.get(base + "/unread").json() == {"unread": 1}
    assert alice.get(base + "/unread").json() == charlie.get(base + "/unread").json() == {"unread": 0}
    assert charlie.get(f"{base}/threads/{alice_id}").json()["items"] == []
    assert charlie.get(base + "/threads").json()["items"] == []
    assert bob.get(base + "/threads").json()["items"][0]["unread"] == 1
    thread = f"{base}/threads/{alice_id}"
    assert bob.get(thread).json()["items"][0]["text"] == "<b>Test</b>"
    assert bob.post(thread + "/read", json={"through": mid}).status_code == 200
    assert bob.get(base + "/unread").json() == {"unread": 0}
    sent = []
    monkeypatch.setattr(auth, "get_smtp_config", lambda: {"host": "test", "from_email": "test@example.test"})
    monkeypatch.setattr(auth, "_base_url", lambda: "https://mta.example.test")
    monkeypatch.setattr(auth, "send_mail", lambda *args, **kwargs: sent.append(args))
    account_lifecycle.send_pending()
    account_lifecycle.send_pending()
    assert len(sent) == 1
    assert sent[0][0] == ["bob@example.test"]
    assert "/account?messages=1" in sent[0][2]
    assert "<b>Test</b>" not in sent[0][2]


def test_participant_only_media(clients, tmp_path):
    _, alice = clients["alice"]
    bob_id, bob = clients["bob"]
    _, charlie = clients["charlie"]
    url = f"/api/messages/threads/{bob_id}/attachment"
    assert alice.post(url, content=b"<svg/>").status_code == 400
    image = BytesIO()
    Image.new("RGB", (4, 4)).save(image, format="PNG")
    assets = [(image.getvalue(), "image/png")]
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        audio = BytesIO()
        with wave.open(audio, "wb") as wav:
            wav.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            wav.writeframes(bytes(16000))
        assets.append((audio.getvalue(), "audio/wav"))
        video = tmp_path / "clip.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=size=32x32:rate=5:duration=1",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True, timeout=20,
        )
        assets.append((video.read_bytes(), "video/mp4"))
    for data, mime in assets:
        response = alice.post(url, content=data)
        assert response.status_code == 201, response.text
        path = f"/api/messages/attachments/{response.json()['id']}"
        assert charlie.get(path).status_code == 404
        partial = bob.get(path, headers={"Range": "bytes=1-6"})
        assert partial.status_code == 206
        assert partial.headers["content-type"] == mime
        assert partial.content == data[1:7]
        assert alice.get(path).content == data
        assert bob.get(path, headers={"Range": "bytes=999999-"}).status_code == 416
