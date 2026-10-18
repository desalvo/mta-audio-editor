"""Native single-user desktop launcher for MTA Audio Editor."""

from __future__ import annotations

import base64
import json
import locale
import os
import socket
import subprocess
import sys
import threading
import time
import http.client
import multiprocessing
import logging
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_NAME = "MTA Audio Editor"
PROJECT_EXTENSION = ".maeproj"
PORTABLE_PROJECT_EXTENSION = ".maeprojz"
LEGACY_PROJECT_EXTENSIONS = (PORTABLE_PROJECT_EXTENSION, ".mta-project.zip", ".zip")


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
    if getattr(sys, "frozen", False):
        os.environ["MTA_NATIVE_REQUIRE_BUNDLED_CHORDINO"] = "true"
    os.environ["MTA_DATA_DIR"] = str(root)
    # Native diagnostics belong to the user, not the Linux server default.
    os.environ.setdefault("MTA_DIAGNOSTIC_DIR", str(root / "diagnostics"))
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
    try:
        from app.chordino_runtime import configure_chordino_environment, clear_chordino_probe_cache
        configure_chordino_environment(bundle_root=_bundle_root())
        clear_chordino_probe_cache()
    except Exception as exc:
        print(f"Chordino runtime setup unavailable: {exc}", file=sys.stderr)
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


def _native_startup_log_path() -> Path:
    """A per-user diagnostic path, available in PyInstaller --windowed mode."""
    path = _data_root() / "logs" / "native-startup.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _native_startup_logger() -> logging.Logger:
    logger = logging.getLogger("mta.native.startup")
    log_path = _native_startup_log_path()
    for old in list(logger.handlers):
        # This logger is process-wide. A previous run/test may have configured
        # it against another per-user data directory. Never leave a stale file
        # handler attached just because some other handler is present.
        if isinstance(old, RotatingFileHandler) and Path(old.baseFilename) != log_path:
            logger.removeHandler(old)
            logging.getLogger("pywebview").removeHandler(old)
            old.close()
    if not any(
        isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_path
        for handler in logger.handlers
    ):
        handler = RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024,
            backupCount=2, encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(threadName)s %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    backend=logging.getLogger("pywebview")
    for handler in logger.handlers:
        if isinstance(handler,RotatingFileHandler) and handler not in backend.handlers:backend.addHandler(handler)
    return logger


def _start_server(port: int):
    import uvicorn
    from app.main import app

    uvicorn_logger = logging.getLogger("uvicorn.error")
    previous = (uvicorn_logger.disabled, uvicorn_logger.level)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        # PyInstaller --windowed on Windows can set sys.stdout/stderr to None.
        # Avoid Uvicorn's default formatter, which calls stream.isatty().
        log_config=None,
        access_log=False,
        server_header=False,
    )
    server = uvicorn.Server(config)

    def run_with_diagnostics():
        # Uvicorn catches ASGI lifespan exceptions and then raises SystemExit(3).
        # Capture its error logger directly: --windowed has no stderr, and the
        # outer exception alone contains none of the original lifespan traceback.
        startup_logger = _native_startup_logger()
        attached = [handler for handler in startup_logger.handlers
                    if handler not in uvicorn_logger.handlers]
        for handler in attached:
            uvicorn_logger.addHandler(handler)
        uvicorn_logger.disabled = False
        uvicorn_logger.setLevel(logging.WARNING)
        try:
            server.run()
        except BaseException as exc:
            # Background exceptions otherwise disappear in Windows --windowed.
            server._mta_startup_exception = exc
            _native_startup_logger().error("Native HTTP thread crashed:\n%s", traceback.format_exc())
        finally:
            for handler in attached:
                uvicorn_logger.removeHandler(handler)
            uvicorn_logger.disabled, previous_level = previous
            uvicorn_logger.setLevel(previous_level)
            if not getattr(server, "started", False):
                _native_startup_logger().error(
                    "Native HTTP server exited before signaling startup; port=%d", port
                )

    thread = threading.Thread(target=run_with_diagnostics, daemon=True, name="mta-native-server")
    thread.start()
    return server, thread


def _wait_ready(url: str, timeout: float = 90.0, *, server=None, thread=None) -> None:
    port = int(url.rsplit(":", 1)[1])
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if thread is not None and not thread.is_alive():
            exc = getattr(server, "_mta_startup_exception", None)
            message = f"Native HTTP server exited before readiness: {exc!r}"
            _native_startup_logger().error(message)
            raise RuntimeError(f"{message}. Diagnostic log: {_native_startup_log_path()}")
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1.0)
        try:
            conn.request("GET", "/api/health")
            response = conn.getresponse()
            response.read()
            if response.status == 200:
                _native_startup_logger().info("Native HTTP server ready on port %d", port)
                return
            last_error = RuntimeError(f"Health endpoint returned HTTP {response.status}")
        except Exception as exc:
            last_error = exc
        finally:
            conn.close()
        time.sleep(0.2)
    message = f"Native server did not become ready within {timeout:g}s: {last_error}"
    _native_startup_logger().error(message)
    raise RuntimeError(f"{message}. Diagnostic log: {_native_startup_log_path()}")


def _startup_timeout_seconds() -> float:
    try:
        return max(20.0, min(180.0, float(os.environ.get("MTA_NATIVE_STARTUP_TIMEOUT", "90"))))
    except (ValueError, OverflowError):
        return 90.0


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
    from app.chordino_runtime import chordino_status
    chordino = chordino_status()
    result["chordino"] = chordino
    if not chordino.get("available"):
        raise RuntimeError(
            "bundled Chordino unavailable: "
            + json.dumps(chordino, ensure_ascii=False, default=str)
        )
    print(json.dumps(result, indent=2))
    return 0



class NativeApi:
    """Filesystem bridge exposed only by the desktop pywebview build."""

    def __dir__(self):
        # pywebview recursively walks public attributes while exposing js_api.
        # Never let that walk enter Window / WinForms / COM or filesystem state.
        members={}
        for cls in reversed(type(self).__mro__):members.update(vars(cls))
        return sorted(name for name,value in members.items()
                      if not name.startswith('_') and (callable(value) or isinstance(value,staticmethod)))

    def _file_dialog(self, dialog_type, **options):
        from native.gui_dialogs import file_dialog
        options.setdefault('directory',str(Path.home()))
        logger=_native_startup_logger()
        logger.info('Opening native file dialog; kind=%s',dialog_type)
        try:
            result=file_dialog(self.window,dialog_type,**options)
            logger.info('Native file dialog closed; selected=%s',bool(result))
            return result
        except Exception:
            logger.exception('Native file dialog failed')
            raise

    def open_external_url(self, url: str) -> dict:
        """Only open the exact pending account approval URL in the system browser."""
        from app.native_ai_account import public_status
        from urllib.parse import urlsplit
        expected=public_status().get('verification_uri')
        if not expected or url!=expected or urlsplit(url).scheme!='https':
            return {'ok':False,'error':'Unrecognized account approval URL'}
        import webbrowser
        return {'ok':bool(webbrowser.open(url,new=2))}

    def __init__(self) -> None:
        self.window = None
        self._ui_zoom_lock = threading.Lock()
        self._update_download_status = {"state": "idle", "received": 0, "total": 0}
        self._update_download_lock = threading.Lock()
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

    def read_clipboard(self) -> dict:
        """Return text from the operating-system clipboard for native WebViews."""
        try:
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["/usr/bin/pbpaste"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                return {"ok": result.returncode == 0, "text": result.stdout if result.returncode == 0 else ""}
            if os.name == "nt":
                import ctypes
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                cf_unicode_text = 13
                if not user32.OpenClipboard(None):
                    return {"ok": False, "text": ""}
                try:
                    handle = user32.GetClipboardData(cf_unicode_text)
                    if not handle:
                        return {"ok": True, "text": ""}
                    kernel32.GlobalLock.restype = ctypes.c_void_p
                    pointer = kernel32.GlobalLock(handle)
                    if not pointer:
                        return {"ok": False, "text": ""}
                    try:
                        return {"ok": True, "text": ctypes.wstring_at(pointer)}
                    finally:
                        kernel32.GlobalUnlock(handle)
                finally:
                    user32.CloseClipboard()
            for command in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"]):
                try:
                    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        return {"ok": True, "text": result.stdout}
                except (FileNotFoundError, OSError, subprocess.SubprocessError):
                    continue
        except Exception as exc:
            print(f"Native clipboard read failed: {exc}", file=sys.stderr)
            return {"ok": False, "text": "", "error": str(exc)}
        return {"ok": False, "text": ""}

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
        # r217: portable projects are the default native project format.
        # The lightweight .maeproj manifest remains supported for legacy/workspace
        # compatibility, but every newly chosen project file is self-contained.
        if safe_name.lower().endswith(PROJECT_EXTENSION):
            safe_name = safe_name[:-len(PROJECT_EXTENSION)]
        if not safe_name.lower().endswith(PORTABLE_PROJECT_EXTENSION):
            safe_name += PORTABLE_PROJECT_EXTENSION
        chosen = self._file_dialog(
            webview.FileDialog.SAVE,
            save_filename=safe_name,
            file_types=("Portable MTA Audio Editor Project (*.maeprojz)",),
        )
        path = self._dialog_path(chosen)
        if path is None:
            return {"ok": False, "cancelled": True}
        if not str(path).lower().endswith(PORTABLE_PROJECT_EXTENSION):
            path = Path(str(path) + PORTABLE_PROJECT_EXTENSION)
        return {"ok": True, "cancelled": False, "path": str(path)}

    @staticmethod
    def _write_bound_project(project_id: str, target: Path) -> str:
        from app.storage import is_portable_project_archive, write_project_archive, write_project_link

        lower = target.name.lower()
        portable = lower.endswith(PORTABLE_PROJECT_EXTENSION) or lower.endswith(".mta-project.zip") or lower.endswith(".zip")
        # Legacy .maeproj files may themselves be portable ZIP archives. Preserve
        # that representation when an existing archive is opened and rebound.
        if lower.endswith(PROJECT_EXTENSION) and target.exists() and is_portable_project_archive(target):
            portable = True
        if portable:
            write_project_archive(project_id, target)
            return "portable"
        write_project_link(project_id, target)
        return "manifest"

    def bind_project_path(self, project_id: str, path: str) -> dict:
        target = Path(path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self.project_paths[project_id] = target
        self._persist_project_paths()
        project_format = self._write_bound_project(project_id, target)
        return {"ok": True, "path": str(target), "format": project_format, "portable": project_format == "portable"}

    def confirm_project_close(self) -> dict:
        self._allow_project_close = True
        if self.window is not None:
            self.window.destroy()
        return {"ok": True}

    def _guard_project_close(self):
        if getattr(self, '_allow_project_close', False):
            return True
        if getattr(self, '_project_close_check_pending', False):
            return False
        self._project_close_check_pending = True

        def check():
            # Return from the synchronous OS closing callback before asking the
            # WebView to execute JS, so its UI thread remains free to answer.
            try:
                ready = self.window.evaluate_js("typeof window.mtaRequestNativeClose === 'function'")
                if ready:
                    self.window.evaluate_js("window.mtaRequestNativeClose(); void 0")
                else:
                    # Before the editor is loaded there are no edits to lose.
                    self.confirm_project_close()
            except Exception:
                _native_startup_logger().exception("Cannot verify unsaved project state; keeping window open")
            finally:
                self._project_close_check_pending = False

        threading.Thread(target=check, name='mta-project-close', daemon=True).start()
        return False

    def sync_project(self, project_id: str) -> dict:
        target = self.project_paths.get(project_id)
        if target is None:
            return {"ok": False, "bound": False}
        project_format = self._write_bound_project(project_id, target)
        return {"ok": True, "bound": True, "path": str(target), "format": project_format, "portable": project_format == "portable"}

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
        """Create a self-contained portable project archive without rebinding the workspace."""
        from app.storage import write_project_archive
        if self.window is None:
            raise RuntimeError("native window is not ready")
        import webview
        safe_name = "".join(ch if ch.isalnum() or ch in " ._-" else "_" for ch in suggested_name).strip(" .") or "project"
        if safe_name.lower().endswith(PROJECT_EXTENSION):
            safe_name = safe_name[:-len(PROJECT_EXTENSION)]
        if not safe_name.lower().endswith(PORTABLE_PROJECT_EXTENSION):
            safe_name += PORTABLE_PROJECT_EXTENSION
        chosen = self._file_dialog(
            webview.FileDialog.SAVE,
            save_filename=safe_name,
            file_types=("MTA Audio Editor Portable Project (*.maeprojz)",),
        )
        path = self._dialog_path(chosen)
        if path is None:
            return {"ok": False, "cancelled": True}
        target = Path(path)
        if not str(target).lower().endswith(PORTABLE_PROJECT_EXTENSION):
            target = Path(str(target) + PORTABLE_PROJECT_EXTENSION)
        target = target.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        write_project_archive(project_id, target)
        return {"ok": True, "cancelled": False, "path": str(target), "portable": True}

    def choose_export_save_path(self, suggested_name: str, extension: str) -> dict:
        if self.window is None:
            raise RuntimeError("native window is not ready")
        import webview

        ext = str(extension or "").lower().lstrip(".")
        if ext not in {"mta8", "mta16", "wav", "mp3", "flac", "pdf", "txt", "cho", "zip", "mp4"}:
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
            "zip": "ZIP Archive (*.zip)",
            "mp4": "MP4 Video (*.mp4)",
            "pdf": "PDF Document (*.pdf)",
            "txt": "Text File (*.txt)",
            "cho": "ChordPro (*.cho)",
        }
        chosen = self._file_dialog(
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

    def _write_generated_file_to_path(self, path: str, data_base64: str) -> dict:
        """Atomically persist generated content to a path already approved by a native save dialog."""
        target = Path(str(path or "")).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = str(data_base64 or "")
        if "," in raw and raw.lstrip().startswith("data:"):
            raw = raw.split(",", 1)[1]
        payload = base64.b64decode(raw, validate=False)
        temp = target.with_name(f".{target.name}.tmp-{os.getpid()}-{time.time_ns()}")
        try:
            with temp.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
            try:
                dir_fd = os.open(str(target.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
        finally:
            temp.unlink(missing_ok=True)
        return {"ok": True, "cancelled": False, "path": str(target), "bytes": len(payload)}

    def save_generated_file_to_path(self, path: str, data_base64: str) -> dict:
        """Persist bytes to a destination returned by choose_export_save_path()."""
        target = Path(str(path or "")).expanduser().resolve()
        if target.suffix.lower().lstrip(".") not in {"wav", "mp3", "flac", "pdf", "txt", "cho", "mta8", "mta16"}:
            raise ValueError("unsupported generated-file extension")
        return self._write_generated_file_to_path(str(target), data_base64)

    def save_generated_file(self, suggested_name: str, extension: str, data_base64: str) -> dict:
        """Show the native save dialog and atomically persist generated content."""
        chosen = self.choose_export_save_path(suggested_name, extension)
        if not chosen.get("ok"):
            return chosen
        return self._write_generated_file_to_path(str(chosen["path"]), data_base64)

    def restore_ui_zoom(self) -> dict:
        from native.ui_zoom import load_zoom, apply_zoom
        with self._ui_zoom_lock:
            value = load_zoom(_data_root())
            if value!=100:value=apply_zoom(self.window,value)
        return {'ok': True, 'zoom_percent': value}

    def set_ui_zoom(self, zoom_percent: int) -> dict:
        from native.ui_zoom import validate_zoom, apply_zoom, save_zoom
        value = validate_zoom(zoom_percent)
        with self._ui_zoom_lock:
            apply_zoom(self.window, value)
            save_zoom(_data_root(), value)
        return {'ok': True, 'zoom_percent': value}

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
        language = "auto"
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                autosave_enabled = bool(raw.get("autosave_enabled", True))
                from native.update_manager import normalize_channel
                update_channel = normalize_channel(raw.get("update_channel", "stable"))
                language = str(raw.get("language", "auto")).lower()
                if language not in {"auto", "it", "en"}:
                    language = "auto"
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        recent_projects = []
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                recent_projects = []
                for x in raw.get("recent_projects", []):
                    recent_id = str(x).strip()
                    if recent_id and recent_id not in recent_projects:
                        recent_projects.append(recent_id)
                    if len(recent_projects) >= 15:
                        break
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                recent_projects = []
        return {
            "max_upload_mb": min(10240, max(1, value)),
            "autosave_enabled": autosave_enabled,
            "update_channel": update_channel,
            "recent_projects": recent_projects,
            "language": language,
            "system_language": (locale.getlocale()[0] or os.getenv("LANG", "en")).split(".", 1)[0].replace("_", "-"),
        }

    def set_native_settings(self, max_upload_mb: int, autosave_enabled: bool = True, update_channel: str = "stable", language: str = "auto") -> dict:
        value = int(max_upload_mb)
        if not 1 <= value <= 10240:
            raise ValueError("max_upload_mb must be between 1 and 10240")
        root = _data_root()
        root.mkdir(parents=True, exist_ok=True)
        from native.update_manager import normalize_channel
        channel = normalize_channel(update_channel)
        language = str(language or "auto").lower()
        if language not in {"auto", "it", "en"}:
            raise ValueError("language must be auto, it or en")
        settings_path = root / "native-settings.json"
        existing = {}
        if settings_path.is_file():
            try:
                existing = json.loads(settings_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                existing = {}
        existing.update({
            "max_upload_mb": value,
            "autosave_enabled": bool(autosave_enabled),
            "update_channel": channel,
            "language": language,
        })
        settings_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
        os.environ["MTA_MAX_UPLOAD_MB"] = str(value)
        # app.main is already imported after the embedded server starts; update the
        # live request/upload limit as well as persisting it for the next launch.
        import sys
        app_main = sys.modules.get("app.main")
        if app_main is not None:
            app_main.MAX_UPLOAD_BYTES = value * 1024 * 1024
        return {
            "ok": True,
            "max_upload_mb": value,
            "autosave_enabled": bool(autosave_enabled),
            "update_channel": channel,
            "language": language,
            "system_language": (locale.getlocale()[0] or os.getenv("LANG", "en")).split(".", 1)[0].replace("_", "-"),
        }


    def set_recent_projects(self, project_ids: list[str]) -> dict:
        root = _data_root()
        root.mkdir(parents=True, exist_ok=True)
        path = root / "native-settings.json"
        raw = {}
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                raw = {}
        clean = []
        seen_paths = set()
        for project_id in project_ids or []:
            value = str(project_id).strip()
            if not value or value in clean:
                continue
            bound = self.project_paths.get(value)
            path_key = None
            if bound is not None:
                try:
                    path_key = str(bound.expanduser().resolve()).casefold()
                except (OSError, RuntimeError):
                    path_key = str(bound).casefold()
            if path_key and path_key in seen_paths:
                continue
            clean.append(value)
            if path_key:
                seen_paths.add(path_key)
            if len(clean) >= 15:
                break
        raw["recent_projects"] = clean
        path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "recent_projects": clean}

    def list_local_models(self) -> dict:
        from native.model_manager import list_local, catalog, local_repo
        try: remote = catalog()
        except Exception as exc: remote = {"error": str(exc), "model_profiles": []}
        return {"ok": True, "local": list_local(), "catalog": remote, "storage_path": str(local_repo())}

    def update_local_model(self, model_id: str) -> dict:
        from native.model_manager import update
        return update(model_id)

    def delete_local_model(self, model_id: str) -> dict:
        from native.model_manager import delete
        return delete(model_id)

    def check_for_updates(self) -> dict:
        from app.version import APP_RELEASE, BUILD_ID
        from native.update_manager import check_for_update
        settings = self.get_native_settings()
        try:
            return check_for_update(APP_RELEASE, settings.get("update_channel", "stable"), current_build=BUILD_ID)
        except Exception as exc:
            return {"ok": False, "available": False, "error": str(exc)}

    def update_download_status(self) -> dict:
        with self._update_download_lock:
            return dict(self._update_download_status)

    def install_update(self, asset_url: str, asset_name: str = "") -> dict:
        from native.update_manager import download_and_launch
        with self._update_download_lock:
            if self._update_download_status["state"] == "downloading":
                return {"ok": False, "error": "Download already in progress"}
            self._update_download_status = {"state": "downloading", "received": 0, "total": 0}

        def report(received: int, total: int) -> None:
            with self._update_download_lock:
                self._update_download_status.update(received=received, total=total)

        def worker() -> None:
            try:
                result = download_and_launch(asset_url, asset_name, progress=report)
                with self._update_download_lock:
                    self._update_download_status.update(state="complete", path=result["path"])
            except Exception as exc:
                with self._update_download_lock:
                    self._update_download_status.update(state="error", error=str(exc))

        threading.Thread(target=worker, daemon=True, name="mta-update-download").start()
        return {"ok": True, "state": "downloading"}

    def _import_project_path(self, path: Path) -> dict:
        from app.storage import import_project_archive, is_portable_project_archive, read_project_link

        resolved = path.expanduser().resolve()
        if is_portable_project_archive(resolved):
            project = import_project_archive(resolved, None)
            # r217: an opened portable project remains bound to the file that the
            # user opened. Autosave and manual Save therefore atomically rewrite
            # that .maeprojz instead of only updating the hidden workspace copy.
            self.project_paths[project.id] = resolved
            self._persist_project_paths()
            return {"ok": True, "cancelled": False, "project": project.model_dump(mode="json"), "path": str(resolved), "portable_import": True, "bound": True}
        project = read_project_link(resolved)
        self.project_paths[project.id] = resolved
        self._persist_project_paths()
        return {"ok": True, "cancelled": False, "project": project.model_dump(mode="json"), "path": str(resolved), "workspace": True}

    def consume_startup_project(self) -> dict:
        pending = getattr(self, "startup_project_path", None)
        if pending is None:
            return {"ok": True, "project": None}
        self.startup_project_path = None
        try:
            return self._import_project_path(Path(pending))
        except Exception as exc:
            return {"ok": False, "project": None, "error": str(exc)}

    def open_project(self) -> dict:
        if self.window is None:
            raise RuntimeError("native window is not ready")
        import webview

        chosen = self._file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=(
                "Portable MTA Audio Editor Project (*.maeprojz)",
                "MTA Audio Editor Project (*.maeproj)",
                "Legacy MTA Audio Editor Project (*.zip)",
            ),
        )
        path = self._dialog_path(chosen)
        if path is None:
            return {"ok": False, "cancelled": True}
        return self._import_project_path(path)

    def list_recent_projects(self) -> dict:
        """Return recent native projects that still have an accessible project file."""
        settings = self.get_native_settings()
        rows = []
        seen_paths = set()
        for project_id in settings.get("recent_projects", []):
            path = self.project_paths.get(str(project_id))
            if path is None or not path.is_file():
                continue
            try:
                path_key = str(path.expanduser().resolve()).casefold()
            except (OSError, RuntimeError):
                path_key = str(path).casefold()
            if path_key in seen_paths:
                continue
            seen_paths.add(path_key)
            rows.append({
                "id": str(project_id),
                "path": str(path),
                "name": path.stem,
            })
            if len(rows) >= 15:
                break
        return {"ok": True, "projects": rows}

    def open_recent_project(self, project_id: str) -> dict:
        """Open a native recent project from its bound project file/workspace."""
        key = str(project_id or "").strip()
        if not key:
            return {"ok": False, "error": "project id missing"}
        path = self.project_paths.get(key)
        if path is None:
            return {"ok": False, "error": "recent project path not found"}
        try:
            from app.storage import load_project
            # The persistent modular workspace is authoritative after first import.
            # The .maeproj path is now a lightweight manifest; portable ZIP export is separate.
            project = load_project(key)
            return {"ok": True, "cancelled": False, "project": project.model_dump(mode="json"), "path": str(path), "workspace": True}
        except Exception:
            if not path.is_file():
                return {"ok": False, "error": "recent project workspace and archive are unavailable", "path": str(path)}
            try:
                return self._import_project_path(path)
            except Exception as exc:
                return {"ok": False, "error": str(exc), "path": str(path)}


def _startup_project_path(argv: list[str] | None = None) -> Path | None:
    args = list(sys.argv[1:] if argv is None else argv)
    for raw in args:
        if not raw or raw.startswith("--"):
            continue
        candidate = Path(raw).expanduser()
        lower = candidate.name.lower()
        if lower.endswith(PROJECT_EXTENSION) or lower.endswith(LEGACY_PROJECT_EXTENSIONS):
            if candidate.is_file():
                return candidate.resolve()
    return None


def main() -> int:
    if "--demucs-worker" in sys.argv:
        return _run_demucs_worker()

    _prepare_environment()
    logger = _native_startup_logger()
    port = _free_local_port()
    url = f"http://127.0.0.1:{port}"
    logger.info("Starting native HTTP server on port %d; frozen=%s", port, bool(getattr(sys, "frozen", False)))
    try:
        server, thread = _start_server(port)
    except Exception:
        logger.exception("Native server initialization failed before thread launch")
        raise
    try:
        _wait_ready(url, timeout=_startup_timeout_seconds(), server=server, thread=thread)
        if "--native-smoke" in sys.argv:
            return _native_smoke(url)

        import webview

        native_api = NativeApi()
        native_api.startup_project_path = _startup_project_path()
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
        logger.info("Native window created; exposing %d bridge methods",len(dir(native_api)))
        window.events.loaded += lambda: logger.info("Native page load event received")
        window.events.closing += native_api._guard_project_close
        webview.start(debug=False)
        return 0
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def _hide_background_worker_dock_icon() -> None:
    """Prevent macOS multiprocessing / frozen model workers from appearing in Dock."""
    if sys.platform != "darwin":
        return
    args = " ".join(sys.argv[1:])
    if not ("--multiprocessing-fork" in args or "--demucs-worker" in args or "resource_tracker" in args):
        return
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyProhibited
        NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyProhibited)
    except ImportError:
        # PyObjC is optional; do not break workers when it is unavailable.
        pass


if __name__ == "__main__":
    _hide_background_worker_dock_icon()
    # Required for PyInstaller-frozen apps using torch/demucs multiprocessing.
    # Without this, a spawned worker can execute this launcher again and open
    # a second empty application window instead of becoming a worker process.
    multiprocessing.freeze_support()
    raise SystemExit(main())
