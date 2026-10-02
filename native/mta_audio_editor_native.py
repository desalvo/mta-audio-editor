"""Native single-user desktop launcher for MTA Audio Editor."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path


APP_NAME = "MTA Audio Editor"

if not getattr(sys, "frozen", False):
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def _bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def _data_root() -> Path:
    override = os.getenv("MTA_NATIVE_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / APP_NAME


def _prepare_environment() -> Path:
    root = _data_root()
    root.mkdir(parents=True, exist_ok=True)
    cache = root / ".cache"
    cache.mkdir(parents=True, exist_ok=True)

    os.environ["MTA_NATIVE_SINGLE_USER"] = "true"
    os.environ["MTA_ALLOW_INSECURE_NO_AUTH"] = "true"
    os.environ["MTA_DATA_DIR"] = str(root)
    os.environ["XDG_CACHE_HOME"] = str(cache)
    os.environ["TORCH_HOME"] = str(cache / "torch")
    os.environ.setdefault("MTA_MAX_UPLOAD_MB", "2048")

    bundled_bin = _bundle_root() / "bin"
    if bundled_bin.is_dir():
        os.environ["PATH"] = str(bundled_bin) + os.pathsep + os.environ.get("PATH", "")
    return root


def _run_demucs_worker() -> int:
    _prepare_environment()
    marker = sys.argv.index("--demucs-worker")
    args = sys.argv[marker + 1 :]
    from demucs.separate import main as demucs_main

    old = sys.argv[:]
    try:
        sys.argv = ["demucs.separate", *args]
        result = demucs_main()
        return int(result or 0)
    finally:
        sys.argv = old


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(port: int):
    import uvicorn
    from app.main import app

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
        server_header=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True, name="mta-native-server")
    thread.start()
    return server, thread


def _wait_ready(url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1.0) as response:  # noqa: S310  # nosec B310 - loopback only
                if response.status == 200:
                    return
        except Exception as exc:
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"Native server did not become ready: {last_error}")


def _native_smoke(url: str) -> int:
    endpoints = ["/api/health", "/api/about", "/api/session", "/api/projects"]
    result: dict[str, object] = {}
    for endpoint in endpoints:
        request = urllib.request.Request(url + endpoint)
        with urllib.request.urlopen(request, timeout=5.0) as response:  # noqa: S310  # nosec B310 - loopback only
            result[endpoint] = {
                "status": response.status,
                "body": json.loads(response.read().decode("utf-8")),
            }
    about = result["/api/about"]["body"]  # type: ignore[index]
    session = result["/api/session"]["body"]  # type: ignore[index]
    if not about.get("native_single_user"):  # type: ignore[union-attr]
        raise RuntimeError("native_single_user flag missing")
    if not session.get("native_single_user"):  # type: ignore[union-attr]
        raise RuntimeError("native session flag missing")
    print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    if "--demucs-worker" in sys.argv:
        return _run_demucs_worker()

    _prepare_environment()
    port = _free_local_port()
    url = f"http://127.0.0.1:{port}"
    server, thread = _start_server(port)
    try:
        _wait_ready(url)
        if "--native-smoke" in sys.argv:
            return _native_smoke(url)

        import webview

        webview.create_window(
            APP_NAME,
            url=url,
            width=1500,
            height=960,
            min_size=(1050, 700),
            text_select=True,
        )
        webview.start(debug=False)
        return 0
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
