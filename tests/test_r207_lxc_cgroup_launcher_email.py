"""Tests for delegated cgroup launcher and non-locking email changes."""
from __future__ import annotations

from pathlib import Path

from app import ai_cgroup_launcher


def test_launcher_uses_delegated_leaf_before_enabling_controllers(tmp_path, monkeypatch):
    root = tmp_path / "cgroup"
    parent = root / "system.slice" / "mta-audio-editor.service"
    parent.mkdir(parents=True)
    (parent / "cgroup.controllers").write_text("cpu io memory")
    (parent / "cgroup.subtree_control").write_text("")
    membership = tmp_path / "membership"
    membership.write_text("0::/system.slice/mta-audio-editor.service\n")
    real_read = Path.read_text

    def read_text(path, *args, **kwargs):
        if str(path) == "/proc/self/cgroup":
            return real_read(membership, *args, **kwargs)
        if str(path).endswith('mta-ai-accounting/cgroup.subtree_control'):
            return 'cpu io'
        return real_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    result = ai_cgroup_launcher.configure(root)
    assert result == str(parent / "mta-ai-accounting")
    assert (parent / "mta-web-process" / "cgroup.procs").read_text().isdigit()
    assert (parent / "cgroup.subtree_control").read_text() == "+cpu +io"
    assert (parent / "mta-ai-accounting" / "cgroup.subtree_control").read_text() == "cpu io"


def test_launcher_fails_closed_without_controllers(tmp_path, monkeypatch):
    root = tmp_path / "cgroup"
    parent = root / "system.slice" / "mta-audio-editor.service"
    parent.mkdir(parents=True)
    (parent / "cgroup.controllers").write_text("memory")
    membership = tmp_path / "membership"
    membership.write_text("0::/system.slice/mta-audio-editor.service\n")
    real_read = Path.read_text

    def read_text(path, *args, **kwargs):
        return real_read(membership if str(path) == "/proc/self/cgroup" else path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    import pytest
    with pytest.raises(RuntimeError, match="CPU/IO"):
        ai_cgroup_launcher.configure(root)
    assert not (parent / "mta-ai-accounting").exists()


def test_installer_delegates_and_uses_launcher():
    script = (Path(__file__).resolve().parents[1] / "scripts" / "install_mta.sh").read_text()
    assert "Delegate=cpu io" in script
    assert "ExecStart=$VENV/bin/python -m app.ai_cgroup_launcher" in script
