from __future__ import annotations

import os
import shutil
import subprocess
import sys
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



def _candidate_bundle_roots(bundle_root: Path | None) -> list[Path]:
    roots: list[Path] = []

    def add(value: Path | None) -> None:
        if value is None:
            return
        try:
            value = value.resolve()
        except OSError:
            pass
        if value not in roots:
            roots.append(value)
    add(bundle_root)
    if bundle_root is not None:
        add(bundle_root.parent)
        add(bundle_root.parent / "Resources")
        add(bundle_root.parent / "Frameworks")
    try:
        exe = Path(os.environ.get("MTA_NATIVE_EXECUTABLE", "") or sys.executable).resolve()
        add(exe.parent)
        contents = exe.parent.parent
        if contents.name == "Contents":
            add(contents / "Frameworks")
            add(contents / "Resources")
            add(contents / "MacOS")
    except OSError:
        pass
    return roots


def _discover_bundled_runtime(bundle_root: Path | None) -> tuple[Path | None, list[Path]]:
    hosts = ("sonic-annotator.exe", "sonic-annotator", "vamp-simple-host.exe", "vamp-simple-host")
    host: Path | None = None
    vamp_dirs: list[Path] = []
    for root in _candidate_bundle_roots(bundle_root):
        for rel in (Path("bin"), Path("."), Path("Frameworks/bin"), Path("Resources/bin")):
            directory = root / rel
            if host is None and directory.is_dir():
                for name in hosts:
                    candidate = directory / name
                    if candidate.is_file():
                        host = candidate
                        break
        for rel in (Path("vamp"), Path("Frameworks/vamp"), Path("Resources/vamp")):
            directory = root / rel
            if directory.is_dir() and any(directory.glob("nnls-chroma.*")) and directory not in vamp_dirs:
                vamp_dirs.append(directory)
    return host, vamp_dirs

def configure_chordino_environment(*, bundle_root: Path | None = None) -> None:
    host, vamp_dirs = _discover_bundled_runtime(bundle_root)
    roots = _candidate_bundle_roots(bundle_root)
    bin_dirs: list[str] = []
    for root in roots:
        for rel in (Path("bin"), Path("Frameworks/bin"), Path("Resources/bin")):
            directory = root / rel
            if directory.is_dir():
                bin_dirs.append(str(directory))
    if bin_dirs:
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(dict.fromkeys([*bin_dirs, current_path]))
    if host is not None:
        os.environ["MTA_CHORDINO_HOST"] = str(host)
    if vamp_dirs:
        existing = [x for x in os.environ.get("VAMP_PATH", "").split(os.pathsep) if x]
        value = os.pathsep.join(dict.fromkeys([*(str(x) for x in vamp_dirs), *existing]))
        os.environ["VAMP_PATH"] = value
        os.environ["MTA_VAMP_PATH"] = value
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
    available = bool(proc.returncode == 0 and plugin)
    reason = None if available else ("vamp-host-failed" if proc.returncode != 0 else "chordino-plugin-missing")
    return {
        "available": available,
        "host": host,
        "host_kind": kind,
        "plugin": plugin,
        "reason": reason,
        "vamp_path": os.getenv("VAMP_PATH", ""),
        "returncode": proc.returncode,
        "diagnostic": listing[-2000:].strip(),
    }


def clear_chordino_probe_cache() -> None:
    chordino_status.cache_clear()
