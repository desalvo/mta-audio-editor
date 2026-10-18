"""Run Windows modal file dialogs on the existing STA GUI thread."""
import sys
import threading


def file_dialog(window, dialog_type, *, start_timeout=10, **options):
    if window is None:raise RuntimeError('Native window is not ready')
    def choose():return window.create_file_dialog(dialog_type,**options)
    if sys.platform!='win32':return choose()
    native=window.native
    if native is None:raise RuntimeError('Native window is not ready')
    if not native.InvokeRequired:return choose()
    # BeginInvoke returns immediately. Invoke can hold the Python/.NET bridge
    # while the GUI callback needs it, and would defeat the start timeout.
    from System import Action
    started=threading.Event();finished=threading.Event();guard=threading.Lock()
    result=[];errors=[];cancelled=False
    def run():
        with guard:
            if cancelled:return
            started.set()
        try:result.append(choose())
        except Exception as exc:errors.append(exc)
        finally:finished.set()
    native.BeginInvoke(Action(run))
    if not started.wait(start_timeout):
        with guard:
            if not started.is_set():
                cancelled=True
                raise RuntimeError('Native file dialog could not start: GUI thread is not responding')
    # A visible modal dialog may legitimately stay open while the user chooses.
    finished.wait()
    if errors:raise RuntimeError('Native file dialog failed') from errors[0]
    return result[0]
