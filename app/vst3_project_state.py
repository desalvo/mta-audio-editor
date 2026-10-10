"""Project-local VST3 snapshots for named inserts; control-thread API only.

A snapshot is not applied to production playback by this module. Loading requires
both the original insert identifier and its exact module path to still match.
The project archive includes these files automatically through storage.py.
"""
from __future__ import annotations

from pathlib import Path

from . import storage
from .models import Project
from native.vst3_probe.state_store import save_checkpoint, load_checkpoint

STATE_DIR = "vst3-checkpoints"


def _insert(project: Project, track_id: str, insert_id: str):
    if track_id == "master":
        inserts = project.master_inserts
    else:
        track = next((track for track in project.tracks if track.id == track_id), None)
        if track is None:
            raise ValueError("Unknown track")
        inserts = track.inserts
    plugin = next((item for item in inserts if item.id == insert_id), None)
    if plugin is None or plugin.plugin != "vst3":
        raise ValueError("Unknown VST3 insert")
    path = plugin.params.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Missing VST3 module path")
    return path


def checkpoint_path(pid: str, track_id: str, insert_id: str) -> Path:
    if not isinstance(track_id, str) or not isinstance(insert_id, str):
        raise ValueError("Invalid VST3 insert id")
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", track_id) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", insert_id):
        raise ValueError("Invalid VST3 insert id")
    return storage.pdir(pid) / STATE_DIR / f"{track_id}--{insert_id}.json"


def save_insert_checkpoint(pid: str, track_id: str, insert_id: str,
                           component: bytes, controller: bytes | None) -> Path:
    """Save a state pair only for a real insert in the current project."""
    project = storage.load_project(pid)
    identity = _insert(project, track_id, insert_id)
    path = checkpoint_path(pid, track_id, insert_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    save_checkpoint(path, identity, component, controller)
    return path


def load_insert_checkpoint(pid: str, track_id: str, insert_id: str) -> tuple[bytes, bytes | None]:
    project = storage.load_project(pid)
    identity = _insert(project, track_id, insert_id)
    return load_checkpoint(checkpoint_path(pid, track_id, insert_id), identity)


def remove_stale_checkpoints(pid: str) -> int:
    """Prune detached insert snapshots; never touch unrecognized files."""
    project = storage.load_project(pid)
    valid = {f"master--{x.id}.json" for x in project.master_inserts if x.plugin == "vst3"}
    for track in project.tracks:
        valid.update(f"{track.id}--{x.id}.json" for x in track.inserts if x.plugin == "vst3")
    directory = storage.pdir(pid) / STATE_DIR
    removed = 0
    if directory.exists():
        for path in directory.glob("*.json"):
            if path.name not in valid and path.is_file() and not path.is_symlink():
                path.unlink()
                removed += 1
    return removed


def capture_insert_checkpoint(pid: str, track_id: str, insert_id: str, supervisor) -> Path:
    """Commit an SDK snapshot to the project (control thread, outside playback).

    Reject changes of plugin identity before contacting the worker; a changed
    project during capture is rejected again before writing the checkpoint.
    The running worker is never modified by this operation.
    """
    identity = _insert(storage.load_project(pid), track_id, insert_id)
    component, controller = supervisor.checkpoint_full_state()
    if _insert(storage.load_project(pid), track_id, insert_id) != identity:
        raise ValueError('VST3 insert changed during checkpoint capture')
    return save_insert_checkpoint(pid, track_id, insert_id, component, controller)


def stage_insert_checkpoint(pid: str, track_id: str, insert_id: str, supervisor) -> bool:
    """Stage an existing project checkpoint on a STOPPED supervisor only.

    A project without a checkpoint starts with plugin defaults. Corrupt,
    incompatible and inaccessible snapshots fail closed, never silently
    substituting a different plugin's state.
    """
    identity = _insert(storage.load_project(pid), track_id, insert_id)
    path = checkpoint_path(pid, track_id, insert_id)
    if not path.exists():
        return False
    supervisor.import_checkpoint(path, identity)
    return True
