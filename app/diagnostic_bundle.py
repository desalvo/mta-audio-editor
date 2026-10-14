"""Opt-in, redacted, temporary diagnostics; never export raw journals or config."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import logging
import threading
import os
from pathlib import Path
import re
import time
import uuid
import zipfile

BASE = Path(os.environ.get("MTA_DIAGNOSTIC_DIR", "/var/lib/mta/diagnostics"))
RETENTION = 24 * 3600
_EVENT_LOCK = threading.Lock()
_HANDLER_INSTALLED = False
SECRET_KEY = re.compile(r"password|secret|token|credential|private.?key|authorization|cookie|api.?key", re.I)
SECRET_VALUE = re.compile(r"(?:bearer\s+\S+|(?:password|token|secret|api[_-]?key)\s*[:=]\s*\S+)", re.I)


def enabled():
    override = directory() / "enabled.json"
    if override.is_file() and not override.is_symlink():
        try:
            return json.loads(override.read_text()).get("enabled") is True
        except (OSError, ValueError):
            return False
    return os.environ.get("MTA_DIAGNOSTICS_ENABLED", "false").lower() in ("true", "yes", "1")


def configure(value: bool):
    if not isinstance(value, bool):
        raise ValueError("enabled must be a boolean")
    target = directory() / "enabled.json"
    tmp = target.with_suffix(".tmp-" + uuid.uuid4().hex)
    try:
        with tmp.open("x") as stream:
            os.chmod(tmp, 0o600)
            json.dump({"enabled": value}, stream)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return enabled()


def directory():
    if BASE.is_symlink():
        raise RuntimeError("Diagnostic directory may not be a symlink")
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(BASE, 0o700)
    return BASE


class SafeEvents(logging.Handler):
    """Persist event metadata, never log messages, traces, prompts, or request bodies."""
    def emit(self, record):
        if not enabled() or record.levelno < logging.WARNING:
            return
        try:
            obj = {"at": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                   "level": record.levelname, "logger": str(record.name)[:100],
                   "module": str(record.module)[:100],
                   "line": int(record.lineno),
                   "exception_type": record.exc_info[0].__name__ if record.exc_info else None}
            serialized = json.dumps(obj, separators=(",", ":")) + "\n"
            with _EVENT_LOCK:
                path = directory() / "events.jsonl"
                if path.is_symlink():
                    return
                if path.exists() and path.stat().st_size >= 2 * 1024 * 1024:
                    path.unlink()
                with path.open("a", encoding="utf-8") as fd:
                    os.chmod(path, 0o600)
                    fd.write(serialized)
        except (OSError, TypeError, ValueError):
            pass


def install_event_capture():
    global _HANDLER_INSTALLED
    if not _HANDLER_INSTALLED:
        logging.getLogger().addHandler(SafeEvents())
        _HANDLER_INSTALLED = True


def clean(now=None):
    now = now or time.time()
    files = sorted((p for p in directory().glob("mta-diagnostics-*.zip")
                    if p.is_file() and not p.is_symlink()), key=lambda p: p.stat().st_mtime, reverse=True)
    for index, f in enumerate(files):
        if index >= 12 or now - f.stat().st_mtime > RETENTION:
            f.unlink(missing_ok=True)
    events = directory() / "events.jsonl"
    if events.is_file() and not events.is_symlink() and now - events.stat().st_mtime > RETENTION:
        events.unlink(missing_ok=True)


def redact(obj, depth=0):
    if depth >= 8:
        return "[truncated]"
    if isinstance(obj, dict):
        return {str(k): "[redacted]" if SECRET_KEY.search(str(k)) else redact(v, depth+1)
                for k, v in list(obj.items())[:200]}
    if isinstance(obj, (tuple, list)):
        return [redact(v, depth+1) for v in obj[:200]]
    if isinstance(obj, str):
        return SECRET_VALUE.sub("[redacted]", obj[:300])
    if isinstance(obj, (float, int, bool)) or obj is None:
        return obj
    return "[unsupported]"


def create(status):
    if not enabled():
        raise PermissionError("Diagnostics are disabled")
    clean()
    output = directory() / ("mta-diagnostics-" + uuid.uuid4().hex + ".zip")
    data = json.dumps({"time_utc": datetime.now(timezone.utc).isoformat(),
                       "scope": "Structured diagnostics only: excludes projects, raw logs, configuration and secrets",
                       "status": redact(status)}, indent=2).encode()
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Diagnostic payload too large")
    try:
        with output.open("xb") as fp:
            os.chmod(output, 0o600)
            with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("diagnostics.json", data)
                events = directory() / "events.jsonl"
                if events.is_file() and not events.is_symlink():
                    zf.writestr("events.jsonl", events.read_bytes()[-2 * 1024 * 1024:])
                zf.writestr("README.txt", "Temporary, redacted MTA diagnostics. Expires after 24 hours.\n")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    clean()
    return output


def resolve(name):
    if not re.fullmatch(r"mta-diagnostics-[0-9a-f]{32}\.zip", name):
        raise FileNotFoundError(name)
    clean()
    result = directory() / name
    if not result.is_file() or result.is_symlink():
        raise FileNotFoundError(name)
    return result
