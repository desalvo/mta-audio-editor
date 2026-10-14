"""Cancellation must invalidate cgroup metering throughout admission and settlement."""
import threading
from pathlib import Path
import pytest
from app import ai_cgroup_metering as module


def test_pre_cancelled_cgroup_does_not_resolve_delegate(monkeypatch):
    cancelled = threading.Event()
    cancelled.set()
    monkeypatch.setattr(module.sys, 'platform', 'linux')
    with pytest.raises(RuntimeError, match='cancelled'):
        module.run_cgroup_process(['unused-worker'], cwd='/', cancel_event=cancelled)


def test_cancel_check_blocks_cgroup_before_setup(monkeypatch):
    monkeypatch.setattr(module.sys, 'platform', 'linux')
    calls = []
    def check():
        calls.append(True)
        return True
    with pytest.raises(RuntimeError, match='cancelled'):
        module.run_cgroup_process(['unused-worker'], cwd='/', cancel_check=check)
    assert calls == [True]


def test_cgroup_source_contains_pre_spawn_and_post_exit_barriers():
    import inspect
    source = inspect.getsource(module.run_cgroup_process)
    assert source.count("raise RuntimeError('AI worker cancelled; metering invalid')") >= 4
    assert source.index('proc.wait()\n        # An exit observed') < source.index('return Measurement(')
