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


def _frozen_native_runtime() -> bool:
    return bool(getattr(sys, "frozen", False) or os.getenv("MTA_NATIVE_REQUIRE_BUNDLED_CHORDINO", "").lower() in {"1", "true", "yes"})


def chordino_host_path() -> str | None:
    configured = _configured_host()
    if configured:
        return configured
    # A frozen desktop build must be self-contained.  Falling back to a
    # Homebrew/system Vamp host can hide packaging bugs in CI and then fail on
    # a clean user machine.
    if _frozen_native_runtime():
        return None
    return (
        shutil.which("sonic-annotator")
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
    roots = _candidate_bundle_roots(bundle_root)
    rel_bins = (
        Path("bin"), Path("."), Path("Frameworks/bin"), Path("Resources/bin"),
        Path("_internal/bin"), Path("Frameworks/_internal/bin"), Path("Resources/_internal/bin"),
    )
    rel_vamp = (
        Path("vamp"), Path("Frameworks/vamp"), Path("Resources/vamp"),
        Path("_internal/vamp"), Path("Frameworks/_internal/vamp"), Path("Resources/_internal/vamp"),
    )
    for root in roots:
        for rel in rel_bins:
            directory = root / rel
            if host is None and directory.is_dir():
                for name in hosts:
                    candidate = directory / name
                    if candidate.is_file():
                        host = candidate
                        break
        for rel in rel_vamp:
            directory = root / rel
            if directory.is_dir() and any(directory.glob("nnls-chroma.*")) and directory not in vamp_dirs:
                vamp_dirs.append(directory)

    # PyInstaller's macOS BUNDLE may relocate collected binaries under
    # Contents/Frameworks while data lands under Contents/Resources.  Keep a
    # bounded recursive fallback so layout changes do not break discovery.
    if host is None or not vamp_dirs:
        scan_roots = [r for r in roots if r.is_dir() and r.name in {"Contents", "Frameworks", "Resources", "MacOS", "_internal"}]
        for root in scan_roots:
            if host is None:
                for name in hosts:
                    try:
                        candidate = next(root.rglob(name), None)
                    except OSError:
                        candidate = None
                    if candidate is not None and candidate.is_file():
                        host = candidate
                        break
            if not vamp_dirs:
                try:
                    plugins = list(root.rglob("nnls-chroma.dylib")) + list(root.rglob("nnls-chroma.so")) + list(root.rglob("nnls-chroma.dll"))
                except OSError:
                    plugins = []
                for plugin in plugins:
                    if plugin.parent not in vamp_dirs:
                        vamp_dirs.append(plugin.parent)
    return host, vamp_dirs

def configure_chordino_environment(*, bundle_root: Path | None = None) -> None:
    host, vamp_dirs = _discover_bundled_runtime(bundle_root)
    roots = _candidate_bundle_roots(bundle_root)
    frozen = _frozen_native_runtime()

    # Never let build-runner/Homebrew paths mask a broken frozen bundle.
    if frozen:
        for name in ("MTA_CHORDINO_HOST", "MTA_SONIC_ANNOTATOR", "MTA_VAMP_PATH", "VAMP_PATH"):
            os.environ.pop(name, None)

    bin_dirs: list[str] = []
    framework_dirs: list[str] = []
    for root in roots:
        for rel in (Path("bin"), Path("Frameworks/bin"), Path("Resources/bin"), Path("_internal/bin"), Path("Frameworks/_internal/bin")):
            directory = root / rel
            if directory.is_dir():
                bin_dirs.append(str(directory))
        for rel in (Path("Frameworks"), Path("Frameworks/_internal"), Path("_internal"), Path(".")):
            directory = root / rel
            if directory.is_dir():
                framework_dirs.append(str(directory))

    if host is not None:
        bin_dirs.insert(0, str(host.parent))
        os.environ["MTA_CHORDINO_HOST"] = str(host)
    if bin_dirs:
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join(dict.fromkeys([*bin_dirs, current_path]))
    if vamp_dirs:
        value = os.pathsep.join(dict.fromkeys(str(x) for x in vamp_dirs))
        if not frozen:
            existing = [x for x in os.environ.get("VAMP_PATH", "").split(os.pathsep) if x]
            value = os.pathsep.join(dict.fromkeys([*(str(x) for x in vamp_dirs), *existing]))
        os.environ["VAMP_PATH"] = value
        os.environ["MTA_VAMP_PATH"] = value

    # External Vamp hosts may depend on dylibs collected by PyInstaller under
    # Contents/Frameworks.  Finder-launched apps do not inherit Homebrew
    # loader paths, so provide the bundle locations explicitly to the child.
    if sys.platform == "darwin" and framework_dirs:
        existing = [x for x in os.environ.get("DYLD_LIBRARY_PATH", "").split(os.pathsep) if x]
        os.environ["DYLD_LIBRARY_PATH"] = os.pathsep.join(dict.fromkeys([*framework_dirs, *existing]))

    if not frozen:
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
