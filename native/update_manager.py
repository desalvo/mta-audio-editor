"""GitHub based update discovery/downloader for native desktop builds."""
from __future__ import annotations

import json
import logging
import os
import platform
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

REPOSITORY = "desalvo/mta-audio-editor"
GITHUB_API = f"https://api.github.com/repos/{REPOSITORY}"
VALID_CHANNELS = {"stable", "early"}
LOG = logging.getLogger(__name__)


def normalize_channel(value: str | None) -> str:
    raw = (value or "stable").strip().lower().replace("_", " ").replace("-", " ")
    return "early" if raw in {"early", "early release", "prerelease", "preview"} else "stable"


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", value or ""))


def is_newer(remote: str, local: str) -> bool:
    a, b = version_key(remote), version_key(local)
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def asset_release_version(name: str) -> str:
    match = re.search(r"(\d+\.\d+\.\d+(?:-r?\d+|-\d+)?)", str(name or ""), re.IGNORECASE)
    if not match:
        return ""
    value = match.group(1)
    # Historical early packages used 0.2.0-106; normalize them to the
    # current 0.2.0-r106 convention for consistent display/comparison.
    return re.sub(r"-(\d+)$", r"-r\1", value)


def latest_asset_release(assets: list[dict]) -> str:
    versions = [asset_release_version(str(asset.get("name", ""))) for asset in assets]
    versions = [value for value in versions if value]
    if not versions:
        return ""
    return max(versions, key=version_key)


def valid_build(value) -> str:
    value = str(value or '').strip()
    if not re.fullmatch(r'[0-9]{14}', value):
        return ''
    try:
        datetime.strptime(value, '%Y%m%d%H%M%S')
    except ValueError:
        return ''
    return value


def asset_build(name: str) -> str:
    match = re.search(r'-b([0-9]{14})(?=[-.]|$)', name, re.IGNORECASE)
    return valid_build(match.group(1)) if match else ''


def _get_json(url: str) -> dict:
    if not str(url).lower().startswith("https://"):
        raise ValueError("update metadata URL must use HTTPS")
    request = urllib.request.Request(  # noqa: S310 -- URL validated above.
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MTA-Audio-Editor-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:  # noqa: S310 -- validated HTTPS request.
        return json.loads(response.read().decode("utf-8"))


def _platform_tokens() -> list[str]:
    if os.name == "nt":
        return ["windows", ".exe"]
    if sys_platform() == "darwin":
        machine = platform.machine().lower()
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        return ["macos", arch, ".dmg"]
    return ["linux"]


def sys_platform() -> str:
    import sys
    return sys.platform


def choose_asset(assets: list[dict], release_version: str = "") -> dict | None:
    names = [(asset, str(asset.get("name", "")).lower()) for asset in assets]
    wanted = str(release_version or "").strip().lower()

    def eligible(name: str) -> bool:
        if os.name == "nt":
            return name.endswith(".exe") and "windows" in name
        if sys_platform() == "darwin":
            machine = platform.machine().lower()
            arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
            return name.endswith(".dmg") and "macos" in name and arch in name
        return False

    candidates = [(asset, name) for asset, name in names if eligible(name)]
    if not candidates:
        return None
    if wanted:
        exact = [(asset, name) for asset, name in candidates if asset_release_version(name).lower() == wanted]
        if exact:
            candidates = exact
    # Rolling early-main can retain assets from older revisions. Prefer the
    # newest candidate when an exact version match is unavailable.
    candidates.sort(key=lambda item: (version_key(asset_release_version(item[1])), asset_build(item[1]),
                    str(item[0].get("created_at") or ""), int(item[0].get("id") or 0)), reverse=True)
    return candidates[0][0]


def check_for_update(current_version: str, channel: str = "stable", *, current_build: str = '') -> dict:
    normalized = normalize_channel(channel)
    endpoint = f"{GITHUB_API}/releases/latest" if normalized == "stable" else f"{GITHUB_API}/releases/tags/early-main"
    release = _get_json(endpoint)
    remote_version = str(release.get("name") or release.get("tag_name") or "").replace("MTA Audio Editor ", "").strip()
    assets = list(release.get("assets", []))
    manifest: dict = {}
    if normalized == "early":
        # The early-main GitHub release has a fixed human-readable name, so
        # derive a usable release from its actual packages even if the manifest
        # is temporarily unavailable.
        asset_release = latest_asset_release(assets)
        if asset_release:
            remote_version = asset_release
        manifest_asset = next((a for a in assets if a.get("name") == "early-update.json"), None)
        if manifest_asset and manifest_asset.get("browser_download_url"):
            try:
                manifest = _get_json(str(manifest_asset["browser_download_url"]))
                manifest_version = str(manifest.get("version") or "").strip()
                manifest_revision = str(manifest.get("revision") or "").strip()
                manifest_release = str(manifest.get("release") or "").strip()
                if manifest_release:
                    remote_version = manifest_release
                elif manifest_version and manifest_revision:
                    remote_version = f"{manifest_version}-r{manifest_revision}"
                elif manifest_version:
                    remote_version = manifest_version
            except Exception as exc:
                LOG.warning("Unable to read early-release update manifest: %s", exc)
    asset = choose_asset(assets, remote_version)
    local_build = valid_build(current_build)
    remote_build = ''
    if normalized == 'early' and asset:
        # The rolling release may contain other platforms/revisions. Compare
        # against the actual installer this client can download, not a global
        # publication timestamp or a different architecture's build.
        remote_version = asset_release_version(str(asset.get('name') or '')) or remote_version
        remote_build = asset_build(str(asset.get('name') or ''))
        builds = manifest.get('package_builds', {})
        if not remote_build and isinstance(builds, dict):
            remote_build = valid_build(builds.get(str(asset.get('name') or '')))
    newer_release = bool(remote_version and is_newer(remote_version, current_version))
    same_release = (not is_newer(remote_version, current_version)
                    and not is_newer(current_version, remote_version))
    newer_build = bool(normalized == 'early' and asset and same_release
                       and local_build and remote_build and remote_build > local_build)
    available = (newer_release or newer_build) and (normalized != 'early' or bool(asset))
    return {
        "ok": True,
        "channel": normalized,
        "current_version": current_version,
        "latest_version": remote_version,
        "current_build": local_build,
        "latest_build": remote_build,
        "current_display": current_version + (f' · build {local_build}' if normalized == 'early' and local_build else ''),
        "latest_display": remote_version + (f' · build {remote_build}' if normalized == 'early' and remote_build else ''),
        "available": bool(available),
        "release_url": str(release.get("html_url") or f"https://github.com/{REPOSITORY}/releases"),
        "asset_name": str(asset.get("name")) if asset else "",
        "asset_url": str(asset.get("browser_download_url")) if asset else "",
        "published_at": str(release.get("published_at") or ""),
    }


def download_and_launch(asset_url: str, asset_name: str, progress=None) -> dict:
    if not asset_url:
        raise ValueError("update asset URL is missing")
    safe = Path(asset_name or "mta-audio-editor-update").name
    target = Path(tempfile.gettempdir()) / safe
    if not str(asset_url).lower().startswith("https://"):
        raise ValueError("update asset URL must use HTTPS")
    request = urllib.request.Request(asset_url, headers={"User-Agent": "MTA-Audio-Editor-Updater"})  # noqa: S310 -- URL validated above.
    staging = target.with_name(target.name + ".download")
    received = 0
    try:
        with urllib.request.urlopen(request, timeout=30) as response, staging.open("wb") as handle:  # noqa: S310 -- validated HTTPS request.
            total = int(response.headers.get("Content-Length") or 0)
            if progress:
                progress(received, total)
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                if progress:
                    progress(received, total)
            handle.flush()
            os.fsync(handle.fileno())
        if total and received != total:
            raise OSError("Incomplete update download")
        os.replace(staging, target)
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]  # noqa: S606 -- intentional installer launcher.
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", str(target)])  # noqa: S606 -- intentional OS installer launcher.
    else:
        subprocess.Popen(["xdg-open", str(target)])  # noqa: S606 -- intentional OS installer launcher.
    return {"ok": True, "path": str(target)}
