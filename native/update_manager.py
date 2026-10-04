"""GitHub based update discovery/downloader for native desktop builds."""
from __future__ import annotations

import json
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


def normalize_channel(value: str | None) -> str:
    raw = (value or "stable").strip().lower().replace("_", " ").replace("-", " ")
    return "early" if raw in {"early", "early release", "prerelease", "preview"} else "stable"


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", value or ""))


def is_newer(remote: str, local: str) -> bool:
    a, b = version_key(remote), version_key(local)
    size = max(len(a), len(b))
    return a + (0,) * (size - len(a)) > b + (0,) * (size - len(b))


def _get_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "MTA-Audio-Editor-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
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


def choose_asset(assets: list[dict]) -> dict | None:
    names = [(asset, str(asset.get("name", "")).lower()) for asset in assets]
    if os.name == "nt":
        for asset, name in names:
            if name.endswith(".exe") and "windows" in name:
                return asset
    elif sys_platform() == "darwin":
        machine = platform.machine().lower()
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        for asset, name in names:
            if name.endswith(".dmg") and "macos" in name and arch in name:
                return asset
    return None


def check_for_update(current_version: str, channel: str = "stable") -> dict:
    normalized = normalize_channel(channel)
    endpoint = f"{GITHUB_API}/releases/latest" if normalized == "stable" else f"{GITHUB_API}/releases/tags/early-main"
    release = _get_json(endpoint)
    remote_version = str(release.get("name") or release.get("tag_name") or "").replace("MTA Audio Editor ", "").strip()
    if normalized == "early":
        manifest_asset = next((a for a in release.get("assets", []) if a.get("name") == "early-update.json"), None)
        if manifest_asset and manifest_asset.get("browser_download_url"):
            try:
                manifest = _get_json(str(manifest_asset["browser_download_url"]))
                remote_version = str(manifest.get("version") or remote_version)
            except Exception:
                pass
    asset = choose_asset(list(release.get("assets", [])))
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
    request = urllib.request.Request(asset_url, headers={"User-Agent": "MTA-Audio-Editor-Updater"})
    with urllib.request.urlopen(request, timeout=30) as response, target.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    if os.name == "nt":
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys_platform() == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
    return {"ok": True, "path": str(target)}
