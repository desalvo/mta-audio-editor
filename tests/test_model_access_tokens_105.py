from fastapi.testclient import TestClient


def test_scoped_model_token_allows_download_without_session(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "administrator-password")
    monkeypatch.setenv("MTA_ADMIN_EMAIL", "admin@example.test")
    import app.auth as auth
    import app.main as main
    auth.DATA_ROOT = None
    auth.init_auth_db()
    models = tmp_path / "models"
    models.mkdir()
    payload = b"coreml-secured-baseline"
    (models / "demucs-4.mlmodel").write_bytes(payload)
    monkeypatch.setattr(main, "COREML_DEMUCS_MODEL_DIR", models)

    logged = TestClient(main.app)
    r = logged.post("/login", data={"identifier": "admin", "password": "administrator-password", "totp": ""}, follow_redirects=False)
    assert r.status_code == 303
    logged.cookies.update(r.cookies)
    issued = logged.post("/api/models/token", headers={"X-MTA-Request": "1", "X-MTA-Client": "pytest"})
    assert issued.status_code == 200
    body = issued.json()
    assert body["token_type"] == "Bearer"
    assert body["scopes"] == ["models:read"]

    anonymous = TestClient(main.app)
    denied = anonymous.get("/api/mobile/demucs-coreml/bootstrap")
    assert denied.status_code == 401
    allowed = anonymous.get(
        "/api/mobile/demucs-coreml/bootstrap",
        headers={"Authorization": f"Bearer {body['token']}"},
    )
    assert allowed.status_code == 200
    assert allowed.content == payload


def test_mobile_and_native_clients_reference_scoped_model_tokens():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    ios = (root / "mobile/ios/MTAEditorMobile/MobileWebViewController.swift").read_text(encoding="utf-8")
    android = (root / "mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/DemucsModelManager.java").read_text(encoding="utf-8")
    native = (root / "native/model_manager.py").read_text(encoding="utf-8")
    assert "/api/models/token" in ios and "Bearer" in ios
    assert "/api/models/token" in android and "Bearer" in android
    assert "MTA_MODEL_ACCESS_TOKEN" in native and "Bearer" in native
