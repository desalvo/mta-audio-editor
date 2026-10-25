"""Real namespace-local PID identity; no monkeypatching process ownership."""
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app import linux_proc_view, ai_arranger_runtime as queue


def test_current_process_identity_reads_self_instead_of_unrelated_outer_pid():
    process = linux_proc_view.directory(os.getpid())
    assert process == Path('/proc/self')
    fields = (process / 'stat').read_text().rsplit(')',1)[1].split()
    assert queue._process_identity(os.getpid()).endswith(':' + fields[19])


def test_child_namespace_pid_resolves_same_kernel_process_and_actual_death():
    child = subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)'])
    try:
        process = linux_proc_view.directory(child.pid)
        assert process is not None
        status = (process / 'status').read_text()
        assert any(line.startswith('NSpid:') and int(line.split()[-1]) == child.pid for line in status.splitlines())
        identity = queue._process_identity(child.pid)
        assert identity
        child.kill()
        child.wait(timeout=5)
        assert queue._process_identity(child.pid) is None
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_unverifiable_namespace_never_becomes_death(monkeypatch):
    if int(Path('/proc/self/stat').read_text().split()[0]) == os.getpid():
        pytest.skip('This case requires a genuinely different mounted proc PID namespace')
    child = subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)'])
    original = Path.stat
    def wrong(path, *a, **kw):
        if str(path).endswith('/ns/pid') and str(path) != '/proc/self/ns/pid':
            return SimpleNamespace(st_ino=-1)
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'stat',wrong)
    try:
        assert linux_proc_view.directory(child.pid) is None
        assert queue._process_identity(child.pid) == ''
    finally:
        child.kill()
        child.wait(timeout=5)
