import hashlib
import json
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path

from .models import Project

ROOT = Path(os.environ.get("MTA_DATA_DIR", "/data/projects")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
PID_RE = re.compile(r"^[a-f0-9]{12}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$")
PROJECT_ARCHIVE_SCHEMA = "mta-audio-editor/project-archive/v1"


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


def originals_dir(pid: str) -> Path:
    path = pdir(pid) / "originals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def original_path(pid: str, filename: str) -> Path:
    return _safe_child(originals_dir(pid), filename)


def create_project(title: str = "Untitled", target: str = "MTA8", owner_user_id: int | None = None) -> Project:
    pid = uuid.uuid4().hex[:12]
    d = pdir(pid)
    (d / "audio").mkdir(parents=True)
    (d / "attachments").mkdir()
    (d / "originals").mkdir()
    p = Project(id=pid, owner_user_id=owner_user_id, title=title[:200], target=target)
    save_project(p)
    return p


def validate_project_files(project: Project) -> None:
    seen_track_ids: set[str] = set()
    for track in project.tracks:
        if track.id in seen_track_ids:
            raise ValueError("duplicate track id")
        seen_track_ids.add(track.id)
        path = audio_path(project.id, track.filename)
        if not path.is_file():
            raise ValueError(f"audio file not found for track {track.id}")
    seen_clip_ids: set[str] = set()
    for clip in project.clip_library:
        if clip.id in seen_clip_ids:
            raise ValueError("duplicate project clip id")
        seen_clip_ids.add(clip.id)
        path = audio_path(project.id, clip.filename)
        if not path.is_file():
            raise ValueError(f"audio file not found for project clip {clip.id}")
    for name in project.preserved_attachments:
        path = attachment_path(project.id, name)
        if not path.is_file():
            raise ValueError(f"attachment not found: {name}")


def save_project(project: Project):
    d = pdir(project.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(exist_ok=True)
    (d / "attachments").mkdir(exist_ok=True)
    (d / "originals").mkdir(exist_ok=True)
    tmp = d / "project.json.tmp"
    tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
    tmp.replace(d / "project.json")


def load_project(pid: str) -> Project:
    return Project.model_validate_json((pdir(pid) / "project.json").read_text(encoding="utf-8"))


def list_projects(owner_user_id: int | None = None, include_shared: bool = True, is_admin: bool = False):
    out = []
    if not ROOT.exists():
        return out
    for d in ROOT.iterdir():
        if d.is_dir() and PID_RE.fullmatch(d.name) and (d / "project.json").exists():
            try:
                p = load_project(d.name)
            except (OSError, ValueError):
                continue
            if is_admin or owner_user_id is None:
                out.append(p)
                continue
            if p.owner_user_id == owner_user_id or (include_shared and owner_user_id in p.shared_with_user_ids):
                out.append(p)
    return sorted(out, key=lambda x: x.title.lower())


def project_access(project: Project, user_id: int, role: str, *, owner_only: bool = False) -> bool:
    if role == "admin":
        return True
    if project.owner_user_id is None:
        return False
    if project.owner_user_id == user_id:
        return True
    return (not owner_only) and user_id in project.shared_with_user_ids


def claim_legacy_project(pid: str, user_id: int) -> Project:
    project = load_project(pid)
    if project.owner_user_id is None:
        project.owner_user_id = user_id
        save_project(project)
    return project


def delete_project(pid: str):
    shutil.rmtree(pdir(pid), ignore_errors=True)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_duplicate_project_file(pid: str, candidate: Path) -> dict | None:
    if not candidate.is_file():
        return None
    candidate_size = candidate.stat().st_size
    candidate_hash = None
    for item in project_files(pid):
        try:
            existing = file_path(pid, item["category"], item["name"])
        except ValueError:
            continue
        if not existing.is_file() or existing.resolve() == candidate.resolve():
            continue
        if existing.stat().st_size != candidate_size:
            continue
        candidate_hash = candidate_hash or file_sha256(candidate)
        if file_sha256(existing) == candidate_hash:
            return item
    return None


def _unique_original_name(pid: str, requested: str) -> str:
    name = Path(requested).name
    if not SAFE_NAME_RE.fullmatch(name):
        stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(name).stem)[:90] or "upload"
        ext = re.sub(r"[^A-Za-z0-9.]+", "", Path(name).suffix)[:12]
        name = f"{stem}{ext}"
    base = originals_dir(pid)
    candidate = name
    n = 2
    while (base / candidate).exists():
        p = Path(name)
        candidate = f"{p.stem}-{n}{p.suffix}"
        n += 1
    return candidate


def preserve_original(pid: str, source: Path, original_name: str) -> Path:
    duplicate = find_duplicate_project_file(pid, source)
    if duplicate and duplicate["category"] == "original":
        return original_path(pid, duplicate["name"])
    name = _unique_original_name(pid, original_name)
    dst = original_path(pid, name)
    shutil.copy2(source, dst)
    return dst


def project_files(pid: str) -> list[dict]:
    project = load_project(pid)
    referenced_audio = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
    items: list[dict] = []
    for category, subdir in (("audio","audio"),("attachment","attachments"),("original","originals")):
        base = pdir(pid) / subdir
        if not base.exists():
            continue
        for f in sorted(base.iterdir(), key=lambda x: x.name.lower()):
            if not f.is_file():
                continue
            items.append({
                "category": category,
                "name": f.name,
                "size": f.stat().st_size,
                "referenced": category == "audio" and f.name in referenced_audio,
            })
    src = pdir(pid) / "source.mta"
    if src.is_file():
        items.append({"category":"source","name":"source.mta","size":src.stat().st_size,"referenced":True})
    return items


def file_path(pid: str, category: str, filename: str) -> Path:
    if category == "audio":
        return audio_path(pid, filename)
    if category == "attachment":
        return attachment_path(pid, filename)
    if category == "original":
        return original_path(pid, filename)
    if category == "source" and filename == "source.mta":
        return pdir(pid) / "source.mta"
    raise ValueError("invalid file category")


def delete_project_file(pid: str, category: str, filename: str) -> None:
    project = load_project(pid)
    if category == "audio" and (any(t.filename == filename for t in project.tracks) or any(c.filename == filename for c in project.clip_library)):
        raise ValueError("cannot delete an audio file referenced by a track or project clip")
    if category == "source":
        raise ValueError("cannot delete the project source file")
    path = file_path(pid, category, filename)
    if not path.exists():
        raise FileNotFoundError(filename)
    path.unlink()


def write_project_archive(pid: str, archive_path: Path) -> Path:
    project = load_project(pid)
    validate_project_files(project)
    base = pdir(pid)
    manifest = {
        "schema": PROJECT_ARCHIVE_SCHEMA,
        "project_id": project.id,
        "title": project.title,
        "owner_user_id": project.owner_user_id,
        "includes_originals": True,
    }
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        z.writestr("archive-manifest.json", json.dumps(manifest, indent=2))
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.name != "project.json.tmp":
                z.write(path, Path("project") / path.relative_to(base))
    return archive_path


def _safe_zip_members(z: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    out = []
    for info in z.infolist():
        name = info.filename.replace("\\", "/")
        p = Path(name)
        if info.is_dir():
            continue
        if p.is_absolute() or ".." in p.parts or not name.startswith("project/"):
            if name != "archive-manifest.json":
                raise ValueError("unsafe project archive path")
        out.append(info)
    return out


def import_project_archive(archive_path: Path, owner_user_id: int | None) -> Project:
    with zipfile.ZipFile(archive_path) as z:
        members = _safe_zip_members(z)
        try:
            manifest = json.loads(z.read("archive-manifest.json"))
        except Exception as exc:
            raise ValueError("missing or invalid archive manifest") from exc
        if manifest.get("schema") != PROJECT_ARCHIVE_SCHEMA:
            raise ValueError("unsupported project archive schema")
        if "project/project.json" not in z.namelist():
            raise ValueError("project.json missing from archive")
        imported = Project.model_validate_json(z.read("project/project.json"))
        new_id = uuid.uuid4().hex[:12]
        target = pdir(new_id)
        target.mkdir(parents=True)
        try:
            for info in members:
                if not info.filename.startswith("project/"):
                    continue
                rel = Path(info.filename).relative_to("project")
                dst = (target / rel).resolve()
                if target.resolve() not in dst.parents:
                    raise ValueError("unsafe project archive path")
                dst.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, dst.open("wb") as out:
                    shutil.copyfileobj(src, out)
            imported.id = new_id
            imported.owner_user_id = owner_user_id
            imported.shared_with_user_ids = []
            save_project(imported)
            validate_project_files(imported)
            return imported
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise
