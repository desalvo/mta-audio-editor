
import base64
import hmac
import os
from fastapi import Request
from fastapi.responses import JSONResponse

from .auth import session_user


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, "true" if default else "false").lower() in {"1", "true", "yes", "on"}


def auth_enabled() -> bool:
    return not _bool("MTA_ALLOW_INSECURE_NO_AUTH", False)


def check_basic_auth(request: Request) -> bool:
    if not auth_enabled():
        return True
    if session_user(request) is not None:
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
    return JSONResponse({"detail": "Authentication required"}, status_code=401)
