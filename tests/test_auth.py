from fastapi.testclient import TestClient


def test_registration_requires_email_confirmation_before_activation(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "administrator-password")
    monkeypatch.setenv("MTA_ADMIN_EMAIL", "admin@example.test")
    monkeypatch.setenv("MTA_DEV_EXPOSE_EMAIL_TOKENS", "true")

    import app.auth as auth
    auth.init_auth_db()

    user, token = auth.register_user("newuser", "new@example.test", "New User", "very-secure-password")
    assert user["email_confirmed"] is False
    assert user["active"] is False

    admin = auth.find_user("admin")
    try:
        auth.update_user_admin(user["id"], admin["id"], active=True)
        assert False, "activation must fail before email confirmation"
    except ValueError:
        pass

    assert auth.confirm_email(token) is True
    activated = auth.update_user_admin(user["id"], admin["id"], active=True)
    assert activated["active"] is True
    assert activated["email_confirmed"] is True


def test_totp_roundtrip_and_qr(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "administrator-password")
    monkeypatch.setenv("MTA_ADMIN_EMAIL", "admin@example.test")
    import app.auth as auth
    auth.init_auth_db()
    admin = auth.find_user("admin")
    secret, uri = auth.begin_totp(admin["id"])
    code = auth._totp(secret, int(__import__("time").time()) // 30)
    auth.enable_totp(admin["id"], code)
    refreshed = auth.get_user(admin["id"])
    assert refreshed["totp_enabled"] == 1
    assert refreshed["totp_secret_enc"]
    assert auth.verify_totp(secret, code)
    svg = auth.totp_qr_svg(uri)
    assert b"<svg" in svg if isinstance(svg, (bytes, bytearray)) else "<svg" in svg


def test_login_page_and_session_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "administrator-password")
    monkeypatch.setenv("MTA_ADMIN_EMAIL", "admin@example.test")
    import app.main as main
    c = TestClient(main.app)
    assert c.get("/login").status_code == 200
    r = c.post("/login", data={"identifier":"admin","password":"administrator-password","totp":""}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    assert "mta_session=" in r.headers.get("set-cookie","")
    c.cookies.update(r.cookies)
    assert c.get("/api/session").json()["role"] == "admin"


def test_login_mockup_is_mobile_friendly(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    import app.main as main
    c = TestClient(main.app)
    html = c.get("/login").text
    css = c.get("/static/auth.css").text
    assert 'name="viewport"' in html
    assert "@media(max-width:850px)" in css
    assert "login-background.png" in css


def test_smtp_configuration_password_is_not_returned(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    import app.auth as auth
    auth.init_auth_db()
    cfg = auth.save_smtp_config({
        "host":"smtp.example.test","port":465,"security":"smtps",
        "username":"mailer","password":"secret-value",
        "from_email":"mta@example.test","from_name":"MTA"
    })
    assert cfg["password"] == ""
    assert cfg["password_set"] is True
    stored = auth.get_smtp_config(include_password=True)
    assert stored["password"] == "secret-value"


def test_activation_notifies_all_admins(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MTA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "administrator-password")
    monkeypatch.setenv("MTA_ADMIN_EMAIL", "admin@example.test")
    import app.auth as auth
    auth.init_auth_db()
    sent = []
    monkeypatch.setattr(auth, "send_mail", lambda recipients, subject, plain, html_body=None: sent.append((recipients,subject,plain)))
    user, token = auth.register_user("notifyme", "notify@example.test", "Notify Me", "very-secure-password")
    assert auth.confirm_email(token)
    admin = auth.find_user("admin")
    auth.update_user_admin(user["id"], admin["id"], active=True)
    assert sent
    admin_messages = [(recipients, subject, plain) for recipients, subject, plain in sent if "admin@example.test" in recipients]
    assert admin_messages
    assert "Utente attivato" in admin_messages[0][1]
    assert "notifyme" in admin_messages[0][2]


def test_registration_rejects_missing_email(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    import app.auth as auth
    auth.init_auth_db()
    try:
        auth.register_user("mailrequired", "", "Mail Required", "very-secure-password")
        assert False, "email must be mandatory"
    except ValueError:
        pass
