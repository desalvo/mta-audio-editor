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
        exact = [(asset, name) for asset, name in candidates if wanted in name]
        if exact:
            candidates = exact
    # Rolling early-main can retain assets from older revisions. Prefer the
    # newest candidate when an exact version match is unavailable.
    candidates.sort(key=lambda item: (str(item[0].get("created_at") or ""), int(item[0].get("id") or 0)), reverse=True)
    return candidates[0][0]


def check_for_update(current_version: str, channel: str = "stable") -> dict:
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
    return {
        "ok": True,
        "channel": normalized,
        "current_version": current_version,
        "latest_version": remote_version,
        "available": bool(remote_version and is_newer(remote_version, current_version)),
        "release_url": str(release.get("html_url") or f"https://github.com/{REPOSITORY}/releases"),
        "asset_name": str(asset.get("name")) if asset else "",
        "asset_url": str(asset.get("browser_download_url")) if asset else "",
        "published_at": str(release.get("published_at") or ""),
    }


def download_and_launch(asset_url: str, asset_name: str) -> dict:
    if not asset_url:
        raise ValueError("update asset URL is missing")
    safe = Path(asset_name or "mta-audio-editor-update").name
    target = Path(tempfile.gettempdir()) / safe
    if not str(asset_url).lower().startswith("https://"):
        raise ValueError("update asset URL must use HTTPS")
    request = urllib.request.Request(asset_url, headers={"User-Agent": "MTA-Audio-Editor-Updater"})  # noqa: S310 -- URL validated above.
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as handle:  # noqa: S310 -- validated HTTPS request.
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]  # noqa: S606 -- intentional installer launcher.
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", str(target)])  # noqa: S606 -- intentional OS installer launcher.
    else:
        subprocess.Popen(["xdg-open", str(target)])  # noqa: S606 -- intentional OS installer launcher.
    return {"ok": True, "path": str(target)}
