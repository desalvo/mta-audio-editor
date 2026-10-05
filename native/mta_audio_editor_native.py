"""Native single-user desktop launcher for MTA Audio Editor."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import http.client
import multiprocessing
from pathlib import Path


APP_NAME = "MTA Audio Editor"


def _configure_native_tls() -> None:
    """Use the operating-system trust store in frozen native applications."""
    try:
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        # Keep normal Python TLS behaviour as a safe fallback; never disable verification.
        try:
            import certifi
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
        except Exception as exc:
            print(f"Native TLS fallback unavailable: {exc}", file=sys.stderr)


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
    _configure_native_tls()
    root = _data_root()
    root.mkdir(parents=True, exist_ok=True)
    cache = root / ".cache"
    cache.mkdir(parents=True, exist_ok=True)

    os.environ["MTA_NATIVE_SINGLE_USER"] = "true"
    os.environ["MTA_ALLOW_INSECURE_NO_AUTH"] = "true"
    os.environ["MTA_DATA_DIR"] = str(root)
    os.environ["XDG_CACHE_HOME"] = str(cache)
    os.environ["TORCH_HOME"] = str(cache / "torch")
    os.environ["MTA_DEMUCS_LOCAL_REPO"] = str(root / "demucs-models" / "repo")
    settings_path = root / "native-settings.json"
    configured_upload_mb = 1024
    if settings_path.is_file():
        try:
            native_settings = json.loads(settings_path.read_text(encoding="utf-8"))
            configured_upload_mb = int(native_settings.get("max_upload_mb", configured_upload_mb))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            configured_upload_mb = 1024
    configured_upload_mb = min(10240, max(1, configured_upload_mb))
    os.environ.setdefault("MTA_MAX_UPLOAD_MB", str(configured_upload_mb))

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
    port = int(url.rsplit(":", 1)[1])
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
        try:
            conn.request("GET", "/api/health")
            response = conn.getresponse()
            response.read()
            if response.status == 200:
                return
        except Exception as exc:
            last_error = exc
        finally:
            conn.close()
        time.sleep(0.1)
    raise RuntimeError(f"Native server did not become ready: {last_error}")


def _native_smoke(url: str) -> int:
    port = int(url.rsplit(":", 1)[1])
    endpoints = ["/api/health", "/api/about", "/api/session", "/api/projects"]
    result: dict[str, object] = {}
    for endpoint in endpoints:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
        try:
            conn.request("GET", endpoint)
            response = conn.getresponse()
            raw = response.read().decode("utf-8")
            result[endpoint] = {
                "status": response.status,
                "body": json.loads(raw),
            }
        finally:
            conn.close()
    about = result["/api/about"]["body"]  # type: ignore[index]
    session = result["/api/session"]["body"]  # type: ignore[index]
    if not about.get("native_single_user"):  # type: ignore[union-attr]
        raise RuntimeError("native_single_user flag missing")
    if not session.get("native_single_user"):  # type: ignore[union-attr]
        raise RuntimeError("native session flag missing")
    print(json.dumps(result, indent=2))
    return 0



class NativeApi:
    """Filesystem bridge exposed only by the desktop pywebview build."""

    def __init__(self) -> None:
        self.window = None
        self.project_paths: dict[str, Path] = {}
        self._project_paths_file = _data_root() / "native-project-paths.json"
        if self._project_paths_file.is_file():
            try:
                raw = json.loads(self._project_paths_file.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.project_paths = {
                        str(project_id): Path(str(path)).expanduser().resolve()
                        for project_id, path in raw.items()
                        if str(project_id).strip() and str(path).strip()
                    }
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                self.project_paths = {}

    def _persist_project_paths(self) -> None:
        self._project_paths_file.parent.mkdir(parents=True, exist_ok=True)
        self._project_paths_file.write_text(
            json.dumps({key: str(value) for key, value in self.project_paths.items()}, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _dialog_path(value):
        if not value:
            return None
        if isinstance(value, (list, tuple)):
            return Path(value[0]) if value else None
        return Path(value)

    def choose_project_save_path(self, suggested_name: str) -> dict:
        if self.window is None:
            raise RuntimeError("native window is not ready")
        import webview

        safe_name = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in suggested_name).strip(" .")
        if not safe_name:
            safe_name = "project"
        if not safe_name.lower().endswith(".mta-project.zip"):
            safe_name += ".mta-project.zip"
        chosen = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=safe_name,
            file_types=("MTA Audio Editor Project (*.zip)",),
        )
        path = self._dialog_path(chosen)
        if path is None:
            return {"ok": False, "cancelled": True}
        if not str(path).lower().endswith(".mta-project.zip"):
            path = Path(str(path) + ".mta-project.zip")
        return {"ok": True, "cancelled": False, "path": str(path)}

    def bind_project_path(self, project_id: str, path: str) -> dict:
        from app.storage import write_project_archive

        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self.project_paths[project_id] = target
        self._persist_project_paths()
        write_project_archive(project_id, target)
        return {"ok": True, "path": str(target)}

    def sync_project(self, project_id: str) -> dict:
        from app.storage import write_project_archive

        target = self.project_paths.get(project_id)
        if target is None:
            return {"ok": False, "bound": False}
        write_project_archive(project_id, target)
        return {"ok": True, "bound": True, "path": str(target)}

    def get_project_path(self, project_id: str) -> dict:
        target = self.project_paths.get(project_id)
        return {
            "ok": True,
            "bound": target is not None,
            "path": str(target) if target is not None else "",
            "home": str(_data_root()),
        }

    def save_project(self, project_id: str, suggested_name: str) -> dict:
        chosen = self.choose_project_save_path(suggested_name)
        if not chosen.get("ok"):
            return chosen
        return self.bind_project_path(project_id, str(chosen["path"]))

    def save_project_copy(self, project_id: str, suggested_name: str) -> dict:
        from app.storage import write_project_archive

        chosen = self.choose_project_save_path(suggested_name)
        if not chosen.get("ok"):
            return chosen
        target = Path(str(chosen["path"])).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        write_project_archive(project_id, target)
        return {"ok": True, "cancelled": False, "path": str(target)}

    def choose_export_save_path(self, suggested_name: str, extension: str) -> dict:
        if self.window is None:
            raise RuntimeError("native window is not ready")
        import webview

        ext = str(extension or "").lower().lstrip(".")
        if ext not in {"mta8", "mta16", "wav", "mp3", "flac"}:
            raise ValueError("unsupported export extension")
        safe_name = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in suggested_name).strip(" .")
        if not safe_name:
            safe_name = "export"
        if not safe_name.lower().endswith(f".{ext}"):
            safe_name += f".{ext}"
        labels = {
            "mta8": "MTA8 (*.mta8)",
            "mta16": "MTA16 (*.mta16)",
            "wav": "WAV Audio (*.wav)",
            "mp3": "MP3 Audio (*.mp3)",
            "flac": "FLAC Audio (*.flac)",
        }
        chosen = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=safe_name,
            file_types=(labels[ext],),
        )
        path = self._dialog_path(chosen)
        if path is None:
            return {"ok": False, "cancelled": True}
        if path.suffix.lower() != f".{ext}":
            path = path.with_suffix(f".{ext}")
        return {"ok": True, "cancelled": False, "path": str(path)}

    def get_native_settings(self) -> dict:
        root = _data_root()
        path = root / "native-settings.json"
        value = int(os.getenv("MTA_MAX_UPLOAD_MB", "1024"))
        if path.is_file():
            try:
                value = int(json.loads(path.read_text(encoding="utf-8")).get("max_upload_mb", value))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        autosave_enabled = True
        update_channel = "stable"
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                autosave_enabled = bool(raw.get("autosave_enabled", True))
                from native.update_manager import normalize_channel
                update_channel = normalize_channel(raw.get("update_channel", "stable"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        return {
            "max_upload_mb": min(10240, max(1, value)),
            "autosave_enabled": autosave_enabled,
            "update_channel": update_channel,
        }

    def set_native_settings(self, max_upload_mb: int, autosave_enabled: bool = True, update_channel: str = "stable") -> dict:
        value = int(max_upload_mb)
        if not 1 <= value <= 10240:
            raise ValueError("max_upload_mb must be between 1 and 10240")
        root = _data_root()
        root.mkdir(parents=True, exist_ok=True)
        from native.update_manager import normalize_channel
        channel = normalize_channel(update_channel)
        (root / "native-settings.json").write_text(
            json.dumps({
                "max_upload_mb": value,
                "autosave_enabled": bool(autosave_enabled),
                "update_channel": channel,
            }, indent=2) + "\n", encoding="utf-8"
        )
        os.environ["MTA_MAX_UPLOAD_MB"] = str(value)
        # app.main is already imported after the embedded server starts; update the
        # live request/upload limit as well as persisting it for the next launch.
        import app.main as app_main
        app_main.MAX_UPLOAD_BYTES = value * 1024 * 1024
        return {
            "ok": True,
            "max_upload_mb": value,
            "autosave_enabled": bool(autosave_enabled),
            "update_channel": channel,
        }

    def list_local_models(self) -> dict:
        from native.model_manager import list_local, catalog
        try: remote = catalog()
        except Exception as exc: remote = {"error": str(exc), "model_profiles": []}
        return {"ok": True, "local": list_local(), "catalog": remote}

    def update_local_model(self, model_id: str) -> dict:
        from native.model_manager import update
        return update(model_id)

    def delete_local_model(self, model_id: str) -> dict:
        from native.model_manager import delete
        return delete(model_id)

    def check_for_updates(self) -> dict:
        from app.version import APP_VERSION
        from native.update_manager import check_for_update
        settings = self.get_native_settings()
        try:
            return check_for_update(APP_VERSION, settings.get("update_channel", "stable"))
        except Exception as exc:
            return {"ok": False, "available": False, "error": str(exc)}

    def install_update(self, asset_url: str, asset_name: str = "") -> dict:
        from native.update_manager import download_and_launch
        return download_and_launch(asset_url, asset_name)

    def open_project(self) -> dict:
        if self.window is None:
            raise RuntimeError("native window is not ready")
        import webview
        from app.storage import import_project_archive

        chosen = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=("MTA Audio Editor Project (*.zip)",),
        )
        path = self._dialog_path(chosen)
        if path is None:
            return {"ok": False, "cancelled": True}
        project = import_project_archive(path, None)
        self.project_paths[project.id] = path.expanduser().resolve()
        self._persist_project_paths()
        return {"ok": True, "cancelled": False, "project": project.model_dump(mode="json")}


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

        native_api = NativeApi()
        window = webview.create_window(
            APP_NAME,
            url=url,
            width=1500,
            height=960,
            min_size=(1050, 700),
            text_select=True,
            js_api=native_api,
        )
        native_api.window = window
        webview.start(debug=False)
        return 0
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    # Required for PyInstaller-frozen apps using torch/demucs multiprocessing.
    # Without this, a spawned worker can execute this launcher again and open
    # a second empty application window instead of becoming a worker process.
    multiprocessing.freeze_support()
    raise SystemExit(main())
