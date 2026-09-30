import os
import re
import shutil
import uuid
from pathlib import Path

from .models import Project

ROOT = Path(os.environ.get("MTA_DATA_DIR", "/data/projects")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
PID_RE = re.compile(r"^[a-f0-9]{12}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def pdir(pid: str) -> Path:
    if not PID_RE.fullmatch(pid):
        raise ValueError("invalid project id")
    path = (ROOT / pid).resolve()
    if path.parent != ROOT:
        raise ValueError("invalid project path")
    return path


def _safe_child(base: Path, filename: str) -> Path:
    if not SAFE_NAME_RE.fullmatch(filename):
        raise ValueError("invalid filename")
    path = (base / filename).resolve()
    if path.parent != base.resolve():
        raise ValueError("invalid file path")
    return path


def audio_path(pid: str, filename: str) -> Path:
    return _safe_child(pdir(pid) / "audio", filename)


def attachment_path(pid: str, filename: str) -> Path:
    return _safe_child(pdir(pid) / "attachments", filename)


def create_project(title: str = "Untitled", target: str = "MTA8") -> Project:
    pid = uuid.uuid4().hex[:12]
    d = pdir(pid)
    (d / "audio").mkdir(parents=True)
    (d / "attachments").mkdir()
    p = Project(id=pid, title=title[:200], target=target)
    save_project(p)
    return p


def validate_project_files(project: Project) -> None:
    limit = 8 if project.target == "MTA8" else 16
    if len(project.tracks) > limit:
        raise ValueError(f"{project.target} supports at most {limit} tracks")
    seen_track_ids: set[str] = set()
    for track in project.tracks:
        if track.id in seen_track_ids:
            raise ValueError("duplicate track id")
        seen_track_ids.add(track.id)
        path = audio_path(project.id, track.filename)
        if not path.is_file():
            raise ValueError(f"audio file not found for track {track.id}")
    for name in project.preserved_attachments:
        path = attachment_path(project.id, name)
        if not path.is_file():
            raise ValueError(f"attachment not found: {name}")


def save_project(project: Project):
    d = pdir(project.id)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "project.json.tmp"
    tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(d / "project.json")


def load_project(pid: str) -> Project:
    return Project.model_validate_json((pdir(pid) / "project.json").read_text(encoding="utf-8"))


def list_projects():
    out = []
    if not ROOT.exists():
        return out
    for d in ROOT.iterdir():
        if d.is_dir() and PID_RE.fullmatch(d.name) and (d / "project.json").exists():
            try:
                out.append(load_project(d.name))
            except (OSError, ValueError):
                continue
    return sorted(out, key=lambda x: x.title.lower())


def delete_project(pid: str):
    shutil.rmtree(pdir(pid), ignore_errors=True)
