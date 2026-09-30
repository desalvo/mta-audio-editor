import base64
import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse

PUBLIC_PREFIXES = ("/static/", "/docs/", "/api/health", "/api/about")


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


def auth_enabled() -> bool:
    return not _bool("MTA_ALLOW_INSECURE_NO_AUTH", False)


def check_basic_auth(request: Request) -> bool:
    if not auth_enabled():
        return True
    password = os.getenv("MTA_ADMIN_PASSWORD", "")
    if not password:
        return False
    username = os.getenv("MTA_ADMIN_USERNAME", "admin")
    header = request.headers.get("authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        raw = base64.b64decode(header[6:], validate=True).decode("utf-8")
        supplied_user, supplied_password = raw.split(":", 1)
    except Exception:
        return False
    return hmac.compare_digest(supplied_user, username) and hmac.compare_digest(supplied_password, password)


def auth_failure_response():
    if auth_enabled() and not os.getenv("MTA_ADMIN_PASSWORD"):
        return JSONResponse({"detail": "Server authentication is not configured"}, status_code=503)
    return JSONResponse({"detail": "Authentication required"}, status_code=401, headers={"WWW-Authenticate": 'Basic realm="MTA Audio Editor"'})
