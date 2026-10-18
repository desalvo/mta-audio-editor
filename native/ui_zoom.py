"""Persisted full-page zoom using native web-engine APIs on the GUI thread."""
from pathlib import Path
import json
import os
import sys
import tempfile
import threading

MIN_ZOOM = 50
MAX_ZOOM = 200
_QT_REQUESTS = []


def validate_zoom(value):
    if type(value) is not int or not MIN_ZOOM <= value <= MAX_ZOOM:
        raise ValueError('Interface zoom must be an integer from 50 to 200 percent')
    return value


def load_zoom(root):
    path = Path(root) / 'native-ui-zoom.json'
    try:
        if path.is_symlink() or path.stat().st_size > 1024:
            return 100
        return validate_zoom(json.loads(path.read_text())['zoom_percent'])
    except (OSError, ValueError, TypeError, KeyError):
        return 100


def save_zoom(root, value):
    value = validate_zoom(value)
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.ui-zoom-', dir=root)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.chmod(name, 0o600)
            json.dump({'zoom_percent': value}, stream)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, root / 'native-ui-zoom.json')
    finally:
        Path(name).unlink(missing_ok=True)


def _engine(window):
    if window is None or getattr(window, 'native', None) is None:
        raise RuntimeError('Native window is not ready for interface zoom')
    engine = getattr(window.native, 'webview', None)
    if engine is None:
        # pywebview 6.2.1 Cocoa/GTK expose the engine through the backend
        # instance; newer releases also expose window.native.webview.
        view = window.gui.BrowserView.instances.get(window.uid)
        engine = getattr(view, 'webview', None)
    if engine is None:
        raise RuntimeError('Native web engine is not ready for interface zoom')
    return engine


def _set_engine_zoom(engine, factor):
    if hasattr(engine, 'ZoomFactor'):
        settings = getattr(getattr(engine, 'CoreWebView2', None), 'Settings', None)
        if settings is not None:
            # Host-driven zoom remains available. Disable unmanaged user zoom
            # so WebView2 accelerators cannot bypass/double our persisted keys.
            settings.IsZoomControlEnabled = False
        engine.ZoomFactor = factor  # WebView2 WinForms
    elif callable(getattr(engine, 'setPageZoom_', None)):
        engine.setPageZoom_(factor)  # WKWebView: layout/page zoom, not magnification
    elif callable(getattr(engine, 'set_zoom_level', None)):
        engine.set_zoom_level(factor)  # WebKitGTK
    elif callable(getattr(engine, 'setZoomFactor', None)):
        engine.setZoomFactor(factor)  # Qt WebEngine/WebKit
    else:
        raise RuntimeError('Interface zoom is unavailable in this native web engine')


def _dispatch(window, engine, callback):
    native = window.native
    if hasattr(native, 'BeginInvoke'):
        if native.InvokeRequired:
            from System import Action
            native.BeginInvoke(Action(callback))
        else:
            callback()
    elif sys.platform == 'darwin':
        from Foundation import NSThread
        from PyObjCTools import AppHelper
        if NSThread.isMainThread(): callback()
        else: AppHelper.callAfter(callback)
    elif callable(getattr(engine, 'set_zoom_level', None)):
        from gi.repository import GLib
        if GLib.MainContext.default().is_owner(): callback()
        else: GLib.idle_add(callback)
    elif callable(getattr(engine, 'setZoomFactor', None)):
        from qtpy import QtCore
        if QtCore.QThread.currentThread() == engine.thread():
            callback(); return
        class Request(QtCore.QObject):
            trigger = QtCore.Signal()
            @QtCore.Slot()
            def run(self):
                try: callback()
                finally:
                    _QT_REQUESTS.remove(self)
                    self.deleteLater()
        request = Request(); _QT_REQUESTS.append(request)
        request.moveToThread(engine.thread())
        request.trigger.connect(request.run)
        request.trigger.emit()
    else:
        raise RuntimeError('Interface zoom is unavailable in this native web engine')


def apply_zoom(window, value, *, timeout=5):
    value = validate_zoom(value)
    engine = None if window is not None and hasattr(window.native,'BeginInvoke') else _engine(window)
    done = threading.Event(); expired = threading.Event(); errors = []
    def change():
        if expired.is_set():return False
        try: _set_engine_zoom(_engine(window) if engine is None else engine, value / 100)
        except Exception as exc: errors.append(exc)
        finally: done.set()
        return False  # GLib idle callbacks are one-shot.
    _dispatch(window, engine, change)
    if not done.wait(timeout):
        expired.set()
        raise RuntimeError('Native interface zoom timed out')
    if errors:
        raise RuntimeError('Native interface zoom failed') from errors[0]
    return value
