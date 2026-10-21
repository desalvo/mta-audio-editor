"""Unprivileged Linux filesystem confinement for interactive server plugin windows.

A plugin's file chooser must not expose other users' projects or server secrets.
Landlock applies to the worker and its descendants, without root or namespaces.
"""
import ctypes as C
import os
from pathlib import Path
import platform
import site
import sys

_LIB=C.CDLL(None,use_errno=True)
_SUPPORTED=platform.machine().lower() in ('x86_64','amd64','aarch64','arm64') and sys.platform.startswith('linux')


def available():
    return bool(_SUPPORTED and _LIB.syscall(444,0,0,1)>=3)


class Ruleset(C.Structure):_fields_=[('handled',C.c_uint64)]
class Beneath(C.Structure):
    _pack_=1
    _fields_=[('access',C.c_uint64),('parent',C.c_int32)]


def confine(root,sources,plugin_roots):
    if not available():raise RuntimeError('Original server plugin editors require Linux Landlock ABI 3 or newer; the host/container policy must permit it')
    root=Path(root).resolve();all_access=(1<<15)-1
    attributes=Ruleset(all_access);fd=_LIB.syscall(444,C.byref(attributes),C.sizeof(attributes),0)
    if fd<0:raise OSError(C.get_errno(),'Cannot create plugin filesystem confinement')
    descriptors=[]
    try:
        def allow(path,writable=False):
            path=Path(path).resolve()
            if not path.exists():return
            descriptor=os.open(path,os.O_PATH|os.O_CLOEXEC);descriptors.append(descriptor)
            access=all_access if writable else (1|4|8)
            if path.is_file() or not path.is_dir():access&=1|2|4|(1<<14)
            rule=Beneath(access,descriptor)
            if _LIB.syscall(445,fd,1,C.byref(rule),0)<0:raise OSError(C.get_errno(),'Cannot allow plugin runtime resource')
        allow(root,True);allow('/dev/null',True)
        for path in ['/usr','/lib','/lib64','/bin','/sbin','/etc/fonts','/etc/ld.so.cache','/etc/localtime','/etc/ssl/certs','/dev/null','/dev/urandom','/dev/random','/proc/self',sys.prefix,sys.base_prefix,*site.getsitepackages(),site.getusersitepackages(),Path(__file__).resolve().parent,Path(__file__).resolve().parents[1]/'bin',*plugin_roots,*sources]:allow(path)
        # X11 connection is already open; font/sample caches stay worker-private.
        if _LIB.prctl(38,1,0,0,0)<0 or _LIB.syscall(446,fd,0)<0:raise OSError(C.get_errno(),'Cannot activate plugin filesystem confinement')
    finally:
        for descriptor in descriptors:os.close(descriptor)
        os.close(fd)


_ENV_KEYS={'MTA_FLUIDSYNTH_LIBRARY','MTA_GM_SOUNDFONT_DIR','PATH','PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','SYSTEMROOT','WINDIR','LANG','LC_ALL','TZ','SSL_CERT_FILE','SSL_CERT_DIR','FONTCONFIG_FILE','FONTCONFIG_PATH','OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MTA_DATA_DIR','MTA_AUDIO_CORE_PATH','MTA_NATIVE_FFMPEG','MTA_NATIVE_FFPROBE','MTA_VST3_PATHS','MTA_SERVER_VST3_DRY_LIMIT_BYTES','MTA_VST3_DISPLAY_TEST_TCP'}


def worker_environment():
    # Scrub BEFORE exec: unsetenv in the child does not erase the initial
    # environment exposed by /proc/self/environ on Linux.
    return {name:value for name,value in os.environ.items() if name in _ENV_KEYS}


def private_environment(root):
    root=Path(root);home=root/'home';home.mkdir(mode=0o700,exist_ok=True)
    # Drop server credentials before third-party code or its display starts.
    safe=worker_environment()
    os.environ.clear();os.environ.update(safe)
    os.environ.update(HOME=str(home),XDG_CONFIG_HOME=str(home/'config'),XDG_CACHE_HOME=str(home/'cache'),TMPDIR=str(root))
