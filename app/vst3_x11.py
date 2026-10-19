"""Linux editor guard for JUCE's transient zero-window focus probes.

Xlib's default handler terminates the process for BadWindow, including harmless
queries against XID 0 while a standalone window is being attached. Suppress only
BadWindow for that nonexistent sentinel, forwarding every other X error to the
previous handler. Never used by the audio callback or on Windows/macOS.
"""
from contextlib import contextmanager
import ctypes as ct
import sys


class Error(ct.Structure):
    _fields_=[('type',ct.c_int),('display',ct.c_void_p),('resourceid',ct.c_ulong),('serial',ct.c_ulong),('error_code',ct.c_ubyte),('request_code',ct.c_ubyte),('minor_code',ct.c_ubyte)]


def transient(error):return error.error_code==3 and error.resourceid==0


@contextmanager
def editor_errors():
    if not sys.platform.startswith('linux'):
        yield;return
    try:lib=ct.CDLL('libX11.so.6')
    except OSError:
        yield;return
    callback_type=ct.CFUNCTYPE(ct.c_int,ct.c_void_p,ct.POINTER(Error));previous=None
    @callback_type
    def handler(display,event):
        if transient(event.contents):return 0
        return callback_type(previous)(display,event)
    lib.XSetErrorHandler.argtypes=[ct.c_void_p];lib.XSetErrorHandler.restype=ct.c_void_p
    previous=lib.XSetErrorHandler(ct.cast(handler,ct.c_void_p))
    if previous is None:
        lib.XSetErrorHandler(None);yield;return
    try:yield
    finally:lib.XSetErrorHandler(previous)
