from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

SONIC_OUTPUT_ID = "vamp:nnls-chroma:chordino:simplechord"
SIMPLE_HOST_OUTPUT_ID = "nnls-chroma:chordino:simplechord"


def _configured_host() -> str | None:
    configured = os.getenv("MTA_CHORDINO_HOST", "").strip() or os.getenv("MTA_SONIC_ANNOTATOR", "").strip()
    if configured and Path(configured).is_file():
        return configured
    return None


def chordino_host_path() -> str | None:
    return (
        _configured_host()
        or shutil.which("sonic-annotator")
        or shutil.which("sonic-annotator.exe")
        or shutil.which("vamp-simple-host")
        or shutil.which("vamp-simple-host.exe")
    )


def host_kind(path: str | None = None) -> str | None:
    value = Path(path or chordino_host_path() or "").name.lower()
    if value.startswith("sonic-annotator"):
        return "sonic-annotator"
    if value.startswith("vamp-simple-host"):
        return "vamp-simple-host"
    return None


def configure_chordino_environment(*, bundle_root: Path | None = None) -> None:
    if bundle_root is not None:
        bindir = bundle_root / "bin"
        vampdir = bundle_root / "vamp"
        if bindir.is_dir():
            os.environ["PATH"] = str(bindir) + os.pathsep + os.environ.get("PATH", "")
            for name in ("sonic-annotator.exe", "sonic-annotator", "vamp-simple-host.exe", "vamp-simple-host"):
                candidate = bindir / name
                if candidate.is_file():
                    os.environ.setdefault("MTA_CHORDINO_HOST", str(candidate))
                    break
        if vampdir.is_dir():
            current = os.environ.get("VAMP_PATH", "")
            value = str(vampdir) + (os.pathsep + current if current else "")
            os.environ["VAMP_PATH"] = value
            os.environ.setdefault("MTA_VAMP_PATH", value)
    explicit = os.getenv("MTA_VAMP_PATH", "").strip()
    if explicit:
        os.environ["VAMP_PATH"] = explicit


@lru_cache(maxsize=1)
def chordino_status() -> dict:
    host = chordino_host_path()
    kind = host_kind(host)
    if not host or not kind:
        return {"available": False, "host": None, "host_kind": None, "plugin": False, "reason": "vamp-host-missing"}
    env = os.environ.copy()
    explicit = os.getenv("MTA_VAMP_PATH", "").strip()
    if explicit:
        env["VAMP_PATH"] = explicit
    command = [host, "-l"] if kind == "sonic-annotator" else [host, "--list-ids"]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False, env=env)
    except (OSError, subprocess.SubprocessError):
        return {"available": False, "host": host, "host_kind": kind, "plugin": False, "reason": "vamp-host-failed"}
    listing = (proc.stdout or "") + "\n" + (proc.stderr or "")
    plugin = "nnls-chroma:chordino" in listing
    return {
        "available": bool(proc.returncode == 0 and plugin),
        "host": host,
        "host_kind": kind,
        "plugin": plugin,
        "reason": None if proc.returncode == 0 and plugin else "chordino-plugin-missing",
        "vamp_path": os.getenv("VAMP_PATH", ""),
    }


def clear_chordino_probe_cache() -> None:
    chordino_status.cache_clear()
