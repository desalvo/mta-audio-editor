import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _request(cookie: str = "", user_agent: str = "pytest-agent"):
    headers = [(b"user-agent", user_agent.encode())]
    if cookie:
        headers.append((b"cookie", f"mta_session={cookie}".encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def _bootstrap(auth, tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MTA_ALLOW_INSECURE_NO_AUTH", raising=False)
    monkeypatch.setenv("MTA_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("MTA_ADMIN_PASSWORD", "administrator-password")
    monkeypatch.setenv("MTA_ADMIN_EMAIL", "admin@example.test")
    auth.init_auth_db()
    return auth.find_user("admin")


def _active_user(auth, admin, username, email):
    user, token = auth.register_user(username, email, username.title(), "very-secure-password")
    assert auth.confirm_email(token)
    return auth.update_user_admin(user["id"], admin["id"], active=True)


def test_authentication_session_profile_and_password_paths(tmp_path, monkeypatch):
    import app.auth as auth

    admin = _bootstrap(auth, tmp_path, monkeypatch)

    # Invalid credentials, pending email and pending approval are distinct paths.
    assert auth.authenticate("missing", "bad")[0] is None
    user, token = auth.register_user("alice", "alice@example.test", "Alice", "very-secure-password")
    assert auth.authenticate("alice", "very-secure-password")[0] is None
    assert auth.confirm_email("not-a-real-token") is False
    assert auth.confirm_email(token) is True
    assert auth.authenticate("alice", "very-secure-password")[0] is None

    active = auth.update_user_admin(user["id"], admin["id"], active=True)
    row, error = auth.authenticate("alice", "very-secure-password")
    assert not error and row["id"] == active["id"]

    # Session creation/lookup/delete and require_* helpers.
    req = _request()
    session = auth.create_session(active["id"], req)
    session_req = _request(session)
    assert auth.session_user(session_req)["id"] == active["id"]
    assert auth.require_user(session_req)["id"] == active["id"]
    with pytest.raises(HTTPException) as exc:
        auth.require_admin(session_req)
    assert exc.value.status_code == 403
    auth.delete_session(None)
    auth.delete_session(session)
    assert auth.session_user(session_req) is None
    with pytest.raises(HTTPException) as exc:
        auth.require_user(session_req)
    assert exc.value.status_code == 401

    # Profile update error and success branches.
    with pytest.raises(ValueError):
        auth.update_profile(999999, display_name="No One")
    with pytest.raises(ValueError):
        auth.update_profile(active["id"], email="not-an-email")
    updated, no_token = auth.update_profile(active["id"], display_name="Alice Updated")
    assert updated["display_name"] == "Alice Updated"
    assert no_token is None

    # Duplicate email collision.
    other = _active_user(auth, admin, "other", "other@example.test")
    with pytest.raises(ValueError):
        auth.update_profile(active["id"], email=other["email"])

    # Password change invalid/current and valid/new.
    with pytest.raises(ValueError):
        auth.change_password(active["id"], "wrong", "new-secure-password")
    session2 = auth.create_session(active["id"], req)
    auth.change_password(active["id"], "very-secure-password", "new-secure-password")
    assert auth.session_user(_request(session2)) is None
    assert auth.authenticate("alice", "new-secure-password")[0] is not None


def test_totp_enable_disable_and_failure_paths(tmp_path, monkeypatch):
    import app.auth as auth

    admin = _bootstrap(auth, tmp_path, monkeypatch)
    user = _active_user(auth, admin, "totpuser", "totp@example.test")

    assert auth.verify_totp("JBSWY3DPEHPK3PXP", "12") is False
    with pytest.raises(ValueError):
        auth.enable_totp(user["id"], "000000")

    secret, uri = auth.begin_totp(user["id"])
    assert "otpauth://totp/" in uri
    with pytest.raises(ValueError):
        auth.enable_totp(user["id"], "000000")

    code = auth._totp(secret, int(time.time()) // 30)
    auth.enable_totp(user["id"], code)
    assert auth.get_user(user["id"])["totp_enabled"]

    with pytest.raises(ValueError):
        auth.disable_totp(user["id"], "wrong-password", code)
    with pytest.raises(ValueError):
        auth.disable_totp(user["id"], "very-secure-password", "000000")
    auth.disable_totp(user["id"], "very-secure-password", code)
    assert not auth.get_user(user["id"])["totp_enabled"]


def test_admin_role_delete_and_last_admin_guards(tmp_path, monkeypatch):
    import app.auth as auth

    admin = _bootstrap(auth, tmp_path, monkeypatch)
    user = _active_user(auth, admin, "member", "member@example.test")

    with pytest.raises(ValueError):
        auth.update_user_admin(999999, admin["id"], active=True)
    with pytest.raises(ValueError):
        auth.update_user_admin(user["id"], admin["id"], role="invalid")
    with pytest.raises(ValueError):
        auth.update_user_admin(admin["id"], admin["id"], active=False)
    with pytest.raises(ValueError):
        auth.update_user_admin(admin["id"], admin["id"], role="user")
    with pytest.raises(ValueError):
        auth.delete_user_admin(admin["id"], admin["id"])
    with pytest.raises(ValueError):
        auth.delete_user_admin(999999, admin["id"])

    promoted = auth.update_user_admin(user["id"], admin["id"], role="admin")
    assert promoted["role"] == "admin"
    # With two admins, the promoted account can be demoted by the other admin.
    demoted = auth.update_user_admin(user["id"], admin["id"], role="user")
    assert demoted["role"] == "user"

    # A normal member can be deleted.
    auth.delete_user_admin(user["id"], admin["id"])
    assert auth.get_user(user["id"]) is None


class _FakeSMTP:
    def __init__(self, quit_raises=False):
        self.logged = None
        self.noops = 0
        self.messages = []
        self.quit_raises = quit_raises

    def login(self, username, password):
        self.logged = (username, password)

    def noop(self):
        self.noops += 1
        return 250, b"ok"

    def send_message(self, msg):
        self.messages.append(msg)

    def quit(self):
        if self.quit_raises:
            raise RuntimeError("quit failed")
        return 221, b"bye"


def test_smtp_full_test_send_and_validation_paths(tmp_path, monkeypatch):
    import app.auth as auth

    _bootstrap(auth, tmp_path, monkeypatch)

    with pytest.raises(ValueError):
        auth.save_smtp_config({"security": "bad"})
    with pytest.raises(ValueError):
        auth.save_smtp_config({"host": "smtp.example.test", "security": "starttls", "from_email": "bad"})

    saved = auth.save_smtp_config({
        "host": "smtp.example.test",
        "port": 587,
        "security": "starttls",
        "username": "mailer",
        "password": "smtp-secret",
        "from_email": "sender@example.test",
        "from_name": "MTA Test",
    })
    assert saved["password_set"] is True
    assert auth.get_smtp_config(include_password=True)["password"] == "smtp-secret"

    fake = _FakeSMTP()
    monkeypatch.setattr(auth, "_smtp_client", lambda cfg: fake)
    auth.test_smtp_config({"password": "override-secret"})
    assert fake.logged == ("mailer", "override-secret")
    assert fake.noops == 1

    auth.send_mail([], "Ignored", "No recipients")
    auth.send_mail(["one@example.test"], "Subject", "Plain", "<b>HTML</b>")
    assert len(fake.messages) == 1
    assert fake.messages[0]["Subject"] == "Subject"

    # The quit failure is intentionally non-fatal and covered by logging.
    fake2 = _FakeSMTP(quit_raises=True)
    monkeypatch.setattr(auth, "_smtp_client", lambda cfg: fake2)
    auth.test_smtp_config({})
    auth.send_mail(["two@example.test"], "Subject 2", "Plain 2")

    # No SMTP host configured.
    auth.save_smtp_config({
        "host": "", "security": "none", "username": "", "password": "",
        "from_email": "", "from_name": "MTA Audio Editor",
    })
    with pytest.raises(ValueError):
        auth.test_smtp_config({})
    with pytest.raises(RuntimeError):
        auth.send_mail(["x@example.test"], "x", "x")


def test_resend_profile_email_and_password_reset_flows(tmp_path, monkeypatch):
    import app.auth as auth

    admin = _bootstrap(auth, tmp_path, monkeypatch)
    sent = []
    monkeypatch.setattr(
        auth,
        "send_mail",
        lambda recipients, subject, plain, html_body=None: sent.append((recipients, subject, plain, html_body)),
    )

    user, token = auth.register_user("resetme", "reset@example.test", "Reset Me", "very-secure-password", "https://mta.test")
    assert sent and any("verify-email" in item[2] for item in sent)
    auth.resend_verification("missing", "https://mta.test")
    auth.resend_verification("resetme", "https://mta.test")
    assert len(sent) >= 2
    assert auth.confirm_email(token) is False  # resend invalidated the first token

    # Confirm the most recently generated token by requesting one internally.
    token2 = auth._create_email_token(user["id"])
    assert auth.confirm_email(token2)
    auth.resend_verification("resetme", "https://mta.test")  # no-op once confirmed
    auth.update_user_admin(user["id"], admin["id"], active=True)

    changed, verify_token = auth.update_profile(
        user["id"], email="reset-new@example.test", base_url="https://mta.test"
    )
    assert changed["email"] == "reset-new@example.test"
    assert changed["active"] is False
    assert verify_token
    assert auth.confirm_email(verify_token)
    auth.update_user_admin(user["id"], admin["id"], active=True)

    auth.request_password_reset("missing", "https://mta.test")
    auth.request_password_reset("resetme", "https://mta.test")
    assert "reset-password" in sent[-1][2]

    reset_token = auth._create_email_token(user["id"], "password-reset")
    assert auth.reset_password("bad-token", "brand-new-password") is False
    assert auth.reset_password(reset_token, "brand-new-password") is True
    assert auth.authenticate("resetme", "brand-new-password")[0] is not None
