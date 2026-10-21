"""Opt-in offline regression: no background model maintenance or external IO.

Production defaults are unchanged. Integration runs which intentionally require
the network must be selected and authorized separately.
"""
import ipaddress
import os
import socket

import pytest

OFFLINE=os.environ.get('MTA_TEST_OFFLINE')=='1'
if OFFLINE:
    os.environ['MTA_DEMUCS_MODEL_AUTO_UPDATE']='false'
    os.environ['MTA_UVR_KARA2_AUTO_REPAIR']='0'
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['TRANSFORMERS_OFFLINE']='1'


@pytest.fixture
def local_native_ai(monkeypatch):
    """Explicit local unit-test route, without disabling server authentication."""
    from app import main,native_ai_routing
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    monkeypatch.setattr(native_ai_routing,'is_remote',lambda kind:False)


@pytest.fixture
def unix_socket_capability(tmp_path):
    """Skip only transport integration when the OS forbids AF_UNIX sockets."""
    target=tmp_path/'capability.sock'
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as probe:
            probe.bind(str(target))
    except (AttributeError,PermissionError) as exc:
        pytest.skip('Environment does not permit local Unix socket transport: '+str(exc))
    finally:
        target.unlink(missing_ok=True)


@pytest.fixture
def chromium_capability():
    """Missing browser binaries are a prerequisite, not a product test failure.

    A browser that exists but fails to launch still fails the selected test.
    This fixture never downloads software or suppresses launch/runtime errors.
    """
    from pathlib import Path
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as browser:
        executable=Path(browser.chromium.executable_path)
        if not executable.is_file():
            pytest.skip('Chromium executable is not installed; real browser acceptance requires the target environment')


def local_host(host):
    if isinstance(host,bytes):host=host.decode('ascii')
    if host=='localhost':return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False


@pytest.fixture(autouse=True)
def offline_network_guard(monkeypatch):
    if not OFFLINE:return
    original_connect=socket.socket.connect
    original_connect_ex=socket.socket.connect_ex
    original_resolve=socket.getaddrinfo

    def connect(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6) and not local_host(address[0]):
            raise PermissionError('Offline regression prohibits external connections')
        return original_connect(sock,address)

    def connect_ex(sock,address):
        if sock.family in (socket.AF_INET,socket.AF_INET6) and not local_host(address[0]):
            raise PermissionError('Offline regression prohibits external connections')
        return original_connect_ex(sock,address)

    def resolve(host,*args,**kwargs):
        if host is not None and not local_host(host):
            raise PermissionError('Offline regression prohibits external DNS')
        return original_resolve(host,*args,**kwargs)

    monkeypatch.setattr(socket.socket,'connect',connect)
    monkeypatch.setattr(socket.socket,'connect_ex',connect_ex)
    monkeypatch.setattr(socket,'getaddrinfo',resolve)


@pytest.fixture(scope='session')
def compiled_audio_core_build(tmp_path_factory):
    """Build source once; module fixtures copy it to keep native state isolated."""
    from pathlib import Path
    import shutil
    if not shutil.which('cmake') or not any(shutil.which(c) for c in ('g++', 'clang++', 'cl')):
        pytest.skip('A native C++20 compiler and CMake are required')
    from scripts.build_audio_core import build
    return build(Path(__file__).resolve().parents[1], tmp_path_factory.mktemp('shared-core-build'))
