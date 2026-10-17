import hashlib
import json
import os
import re
import subprocess
import shutil
import stat
import threading
import time
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path

from .models import Project

try:
    import fcntl
except ImportError:
    fcntl = None

ROOT = Path(os.environ.get("MTA_DATA_DIR", "/data/projects")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
PID_RE = re.compile(r"^[a-f0-9]{12}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$")
PROJECT_ARCHIVE_SCHEMA = "mta-audio-editor/project-archive/v1"
PROJECT_LINK_SCHEMA = "mta-audio-editor/project-link/v1"

GC_QUEUE_NAME = ".gc-pending.json"
SHARED_MEDIA_ROOT = Path(os.environ.get("MTA_SHARED_MEDIA_DIR", str(ROOT.parent / "shared-media"))).resolve()
SHARED_AUDIO_ROOT = SHARED_MEDIA_ROOT / "audio"
SHARED_INDEX_PATH = SHARED_MEDIA_ROOT / "index.json"
_GC_LOCK = threading.RLock()
_GC_ACTIVE: set[str] = set()
_SHARED_LOCK = threading.RLock()
_SESSION_PREVIEW_ROOT = Path(tempfile.mkdtemp(prefix="mta-audio-editor-preview-")).resolve()
_SESSION_PREVIEW_LOCK = threading.RLock()


def session_preview_dir(pid: str) -> Path:
    """Return this process/session's preview cache for a project.

    The cache deliberately lives outside ROOT/project workspaces so derived
    preview media can never become project state or leak into portable exports.
    """
    if not PID_RE.fullmatch(str(pid)):
        raise ValueError("invalid project id")
    path = _SESSION_PREVIEW_ROOT / str(pid)
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_session_preview_cache(pid: str | None = None) -> dict[str, int]:
    """Delete temporary preview media for one project or for the whole app session."""
    removed = 0
    with _SESSION_PREVIEW_LOCK:
        targets = [_SESSION_PREVIEW_ROOT / str(pid)] if pid is not None else [_SESSION_PREVIEW_ROOT]
        for target in targets:
            if not target.exists():
                continue
            for item in target.rglob("*"):
                if item.is_file():
                    removed += 1
            shutil.rmtree(target, ignore_errors=True)
        if pid is not None:
            _SESSION_PREVIEW_ROOT.mkdir(parents=True, exist_ok=True)
    return {"session_preview_deleted": removed}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _shared_blob_path(digest: str, suffix: str = "") -> Path:
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("invalid shared media digest")
    ext = re.sub(r"[^A-Za-z0-9.]", "", suffix or "")[:16]
    return SHARED_AUDIO_ROOT / digest[:2] / f"{digest}{ext}"


@contextmanager
def _shared_process_lock():
    """Serialize shared blob/index mutations across POSIX server workers."""
    if fcntl is None:
        # Refuse uncoordinated mutations on platforms without an OS lock.
        raise RuntimeError("shared-media mutations require POSIX file locking")
    if SHARED_MEDIA_ROOT.is_symlink():
        raise ValueError("unsafe shared media root")
    SHARED_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    lock = SHARED_MEDIA_ROOT / ".shared-media.lock"
    if lock.is_symlink():
        raise ValueError("unsafe shared lock")
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    with os.fdopen(fd, "r+b") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("unsafe shared lock type")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _validate_shared_tree():
    if SHARED_MEDIA_ROOT.is_symlink() or SHARED_AUDIO_ROOT.is_symlink():
        raise ValueError("unsafe shared directory")
    if SHARED_AUDIO_ROOT.exists() and not SHARED_AUDIO_ROOT.is_dir():
        raise ValueError("unsafe shared audio directory")


def _validate_blob_parent(blob: Path):
    _validate_shared_tree()
    if blob.parent.is_symlink() or (blob.parent.exists() and not blob.parent.is_dir()):
        raise ValueError("unsafe shared blob directory")


def _load_shared_index() -> dict:
    if SHARED_INDEX_PATH.is_symlink() or (SHARED_INDEX_PATH.exists() and not SHARED_INDEX_PATH.is_file()):
        raise ValueError("unsafe shared index")
    try:
        raw = json.loads(SHARED_INDEX_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": 1, "assets": {}, "updated_at": 0}
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("invalid shared index") from exc
    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("assets"), dict):
        raise ValueError("invalid shared index schema")
    return raw


def _write_shared_index(index: dict) -> None:
    if SHARED_INDEX_PATH.is_symlink() or (SHARED_INDEX_PATH.exists() and not SHARED_INDEX_PATH.is_file()):
        raise ValueError("unsafe shared index")
    SHARED_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
    index["version"] = 1
    index["updated_at"] = int(time.time())
    _atomic_json_write(SHARED_INDEX_PATH, index)


def _link_or_copy_shared(blob: Path, local: Path) -> None:
    if local.exists():
        try:
            if os.path.samefile(blob, local):
                return
        except OSError:
            pass
    tmp = local.parent / f".{local.name}.{uuid.uuid4().hex}.sharedtmp"
    tmp.unlink(missing_ok=True)
    if local.is_symlink() or blob.is_symlink() or not blob.is_file():
        raise ValueError("unsafe shared-media path")
    try:
        os.link(blob, tmp)
    except OSError:
        shutil.copy2(blob, tmp)
    os.replace(tmp, local)


def promote_project_audio_to_shared(pid: str) -> dict[str, int]:
    """Deduplicate referenced project audio into a content-addressed shared store.

    Project-local paths remain valid and self-contained. When supported by the
    filesystem they become hardlinks to the shared blob, otherwise a local copy
    is retained. The global index is reconstructible and never authoritative.
    """
    project = load_project(pid)
    referenced = referenced_audio_files(project)
    promoted = linked = 0
    with _SHARED_LOCK, _shared_process_lock():
        _validate_shared_tree()
        index = _load_shared_index()
        assets = index.setdefault("assets", {})
        for name in sorted(referenced):
            try:
                local = audio_path(pid, name)
            except ValueError:
                continue
            if local.is_symlink() or not local.is_file():
                continue
            digest = _sha256_file(local)
            blob = _shared_blob_path(digest, local.suffix.lower())
            _validate_blob_parent(blob)
            blob.parent.mkdir(parents=True, exist_ok=True)
            if blob.is_symlink() or (blob.exists() and not blob.is_file()):
                raise ValueError("unsafe shared blob")
            if blob.exists() and _sha256_file(blob) != digest:
                raise ValueError("shared blob digest mismatch")
            if not blob.exists():
                tmp = blob.parent / f".{blob.name}.{uuid.uuid4().hex}.tmp"
                try:
                    shutil.copy2(local, tmp)
                    if _sha256_file(tmp) != digest:
                        raise ValueError("shared copy digest mismatch")
                    os.replace(tmp, blob)
                    _fsync_directory(blob.parent)
                finally:
                    tmp.unlink(missing_ok=True)
                promoted += 1
            _link_or_copy_shared(blob, local)
            linked += 1
            row = assets.setdefault(digest, {"path": str(blob.relative_to(SHARED_MEDIA_ROOT)), "size": blob.stat().st_size, "refs": []})
            refs = {str(x) for x in row.get("refs", [])}
            refs.add(f"{pid}/audio/{name}")
            row["refs"] = sorted(refs)
            row["path"] = str(blob.relative_to(SHARED_MEDIA_ROOT))
            row["size"] = blob.stat().st_size
        _write_shared_index(index)
    return {"promoted": promoted, "linked": linked}


def verified_shared_audio(path: Path) -> bool:
    """Accept hardlinks only to our matching content-addressed regular blob."""
    try:
        _validate_shared_tree()
        before=path.lstat()
        if not stat.S_ISREG(before.st_mode):return False
        digest=_sha256_file(path)
        blob=_shared_blob_path(digest,path.suffix.lower())
        _validate_blob_parent(blob)
        if blob.is_symlink() or not blob.is_file() or not os.path.samefile(path,blob):return False
        after=path.lstat()
        return ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns))
    except (OSError,ValueError):return False


def rescan_shared_media(*, delete_unreferenced: bool = False) -> dict[str, int]:
    """Rebuild the shared-media reference index from every project.

    This emergency-safe rescan treats project.json + clip-library references as
    authoritative. Shared blobs are deleted only after the complete rescan proves
    that no project references their content.
    """
    assets: dict[str, dict] = {}
    projects = references = missing = deleted = 0
    incomplete = False
    with _SHARED_LOCK, _shared_process_lock():
        _validate_shared_tree()
        # Do not overwrite a damaged or future-version index during repair.
        # An operator must explicitly recover it before any index rebuild.
        _load_shared_index()
        if ROOT.exists():
            for d in sorted(ROOT.iterdir()):
                if not PID_RE.fullmatch(d.name):
                    continue
                if d.is_symlink() or not d.is_dir() or not (d / "project.json").is_file() or (d / "project.json").is_symlink():
                    incomplete = True
                    continue
                projects += 1
                try:
                    project = load_project(d.name)
                except (OSError, ValueError, TypeError):
                    incomplete = True
                    continue
                for name in sorted(referenced_audio_files(project)):
                    try:
                        local = audio_path(d.name, name)
                    except ValueError:
                        missing += 1
                        incomplete = True
                        continue
                    if local.is_symlink() or not local.is_file():
                        missing += 1
                        incomplete = True
                        continue
                    digest = _sha256_file(local)
                    blob = _shared_blob_path(digest, local.suffix.lower())
                    _validate_blob_parent(blob)
                    blob.parent.mkdir(parents=True, exist_ok=True)
                    if blob.is_symlink() or (blob.exists() and not blob.is_file()):
                        raise ValueError("unsafe shared blob")
                    if blob.exists() and _sha256_file(blob) != digest:
                        raise ValueError("shared blob digest mismatch")
                    if not blob.exists():
                        tmp = blob.parent / f".{blob.name}.{uuid.uuid4().hex}.tmp"
                        try:
                            shutil.copy2(local, tmp)
                            if _sha256_file(tmp) != digest:
                                raise ValueError("shared copy digest mismatch")
                            os.replace(tmp, blob)
                            _fsync_directory(blob.parent)
                        finally:
                            tmp.unlink(missing_ok=True)
                    _link_or_copy_shared(blob, local)
                    row = assets.setdefault(digest, {"path": str(blob.relative_to(SHARED_MEDIA_ROOT)), "size": blob.stat().st_size, "refs": []})
                    row["refs"].append(f"{d.name}/audio/{name}")
                    references += 1
        if incomplete:
            # A partial scan must not publish a reduced index either: doing so
            # can discard references still owned by an unreadable project.
            raise ValueError("incomplete shared media scan; index publication and deletion forbidden")
        if delete_unreferenced and SHARED_AUDIO_ROOT.is_symlink():
            raise ValueError("unsafe shared audio directory")
        if delete_unreferenced and SHARED_AUDIO_ROOT.exists():
            keep_paths = {(SHARED_MEDIA_ROOT / row["path"]).resolve() for row in assets.values()}
            for directory in SHARED_AUDIO_ROOT.iterdir():
                if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
                    raise ValueError("unsafe shared blob directory")
            for blob in SHARED_AUDIO_ROOT.rglob("*"):
                if not blob.is_symlink() and blob.is_file() and blob.resolve() not in keep_paths:
                    blob.unlink(missing_ok=True)
                    deleted += 1
            for folder in sorted((p for p in SHARED_AUDIO_ROOT.rglob("*") if p.is_dir()), reverse=True):
                try:
                    folder.rmdir()
                except OSError:
                    pass
        _write_shared_index({"version": 1, "assets": assets, "updated_at": int(time.time())})
    return {"projects": projects, "references": references, "missing": missing, "deleted": deleted, "assets": len(assets)}




def cleanup_project_preview_cache(pid: str, *, keep_per_track: int = 0) -> dict[str, int]:
    """Remove legacy preview artifacts from a project workspace.

    Since r210 previews are session-only temporary files outside the project.
    Any historic ``.preview`` tree or ``preview-master.mp3`` found inside a
    workspace is obsolete and is removed in full when the project is opened.
    ``keep_per_track`` remains accepted for compatibility but is ignored.
    """
    del keep_per_track
    removed = 0
    base = pdir(pid)
    cache = base / ".preview"
    if cache.exists():
        for path in cache.rglob("*"):
            if path.is_file():
                removed += 1
        shutil.rmtree(cache, ignore_errors=True)
    master = base / "preview-master.mp3"
    if master.exists():
        master.unlink(missing_ok=True)
        removed += 1
    # r209 and earlier could briefly place Sample Editor effect previews here.
    for path in base.glob(".sample-fx-*"):
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return {"preview_deleted": removed, "preview_kept": 0}

def maintain_project_storage(pid: str) -> dict[str, int]:
    """Opening-time maintenance for project media and rebuildable caches."""
    from .project_media_usage import cleanup
    gc_result = cleanup(pid)
    previews = cleanup_project_preview_cache(pid)
    shared = promote_project_audio_to_shared(pid)
    return {**gc_result, **previews, **shared}


def _gc_queue_path(pid: str) -> Path:
    return pdir(pid) / GC_QUEUE_NAME


def _atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    try:
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        _fsync_directory(path.parent)
    finally:
        tmp.unlink(missing_ok=True)


def referenced_audio_files(project: Project) -> set[str]:
    return {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}


def _read_gc_queue(pid: str) -> set[str]:
    """Read the durable queue; never silently discard malformed recovery state."""
    path = _gc_queue_path(pid)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("unsafe GC journal")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    if (not isinstance(raw, dict) or raw.get("version") != 1 or
            not isinstance(raw.get("audio"), list) or
            any(not isinstance(x, str) or not SAFE_NAME_RE.fullmatch(x)
                for x in raw["audio"]) or
            len(raw["audio"]) != len(set(raw["audio"]))):
        raise ValueError("invalid GC journal")
    return set(raw["audio"])


def _write_gc_queue(pid: str, names: set[str]) -> None:
    path = _gc_queue_path(pid)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError("unsafe GC journal")
    if not names:
        path.unlink(missing_ok=True)
        _fsync_directory(path.parent)
        return
    _atomic_json_write(path, {"version": 1, "audio": sorted(names), "updated_at": int(time.time())})


def reconcile_project_gc(pid: str, candidates: set[str] | None = None) -> set[str]:
    """Durably queue unreferenced project audio for crash-safe background cleanup.

    project.json is always authoritative: referenced files are never queued. On
    startup, candidates=None additionally discovers orphan files left by a crash
    between the logical-delete commit and journal creation.
    """
    from .project_media_usage import lock
    with lock(pid), _GC_LOCK:
        project = load_project(pid)
        referenced = referenced_audio_files(project)
        from .project_media_usage import pending_files
        referenced |= pending_files(pid)[0]['audio']
        queued = _read_gc_queue(pid)
        audio_dir = pdir(pid) / "audio"
        if audio_dir.is_symlink():
            raise ValueError("unsafe GC audio directory")
        if candidates is None and audio_dir.exists():
            candidates = {f.name for f in audio_dir.iterdir() if f.is_file() and SAFE_NAME_RE.fullmatch(f.name)}
        for name in candidates or set():
            if SAFE_NAME_RE.fullmatch(name) and name not in referenced:
                queued.add(name)
        queued.difference_update(referenced)
        _write_gc_queue(pid, queued)
        return queued


def run_project_gc(pid: str) -> dict[str, int]:
    """Remove only unreferenced, regular audio files from a safe media root."""
    deleted = skipped = 0
    from .project_media_usage import lock
    with lock(pid), _GC_LOCK:
        try:
            project = load_project(pid)
            referenced = referenced_audio_files(project)
            from .project_media_usage import pending_files
            referenced |= pending_files(pid)[0]['audio']
            queued = _read_gc_queue(pid)
        except (OSError, ValueError, TypeError):
            return {"deleted": 0, "skipped": 0}
        audio_dir = pdir(pid) / "audio"
        if audio_dir.is_symlink() or not audio_dir.is_dir():
            return {"deleted": 0, "skipped": len(queued)}
        remaining: set[str] = set()
        for name in sorted(queued):
            if name in referenced:
                skipped += 1
                continue
            target = audio_dir / name
            try:
                metadata = target.lstat()
                if not stat.S_ISREG(metadata.st_mode):
                    skipped += 1
                    remaining.add(name)
                    continue
                target.unlink()
                deleted += 1
            except FileNotFoundError:
                continue
            except OSError:
                remaining.add(name)
        try:
            _fsync_directory(audio_dir)
        finally:
            _write_gc_queue(pid, remaining)
    return {"deleted": deleted, "skipped": skipped}


def _gc_worker(pid: str) -> None:
    # Retry only when the durable queue makes progress. Failed deletions are
    # preserved for the next scheduled pass rather than busy-spun indefinitely.
    try:
        time.sleep(0.05)
        previous = None
        while True:
            before = _read_gc_queue(pid)
            if before == previous:
                break
            previous = before
            run_project_gc(pid)
            with _GC_LOCK:
                after = _read_gc_queue(pid)
                if not after or after == before:
                    break
    finally:
        with _GC_LOCK:
            _GC_ACTIVE.discard(pid)


def schedule_project_gc(pid: str, candidates: set[str] | None = None, *, reconcile_orphans: bool = False) -> None:
    try:
        reconcile_project_gc(pid, None if reconcile_orphans else (candidates or set()))
    except (OSError, ValueError):
        return
    with _GC_LOCK:
        if pid in _GC_ACTIVE:
            return
        _GC_ACTIVE.add(pid)
    threading.Thread(target=_gc_worker, args=(pid,), name=f"mta-gc-{pid}", daemon=True).start()


def resume_pending_gc() -> None:
    """Reconcile orphan audio and resume interrupted GC for every project."""
    if not ROOT.exists():
        return
    for d in ROOT.iterdir():
        if d.is_symlink() or not d.is_dir() or not PID_RE.fullmatch(d.name) or not (d / "project.json").exists():
            continue
        schedule_project_gc(d.name, reconcile_orphans=True)



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


def create_project(title: str = "Untitled", target: str = "MTA8", owner_user_id: int | None = None, sample_rate: int = 44100, audio_storage_mode: str = "wav") -> Project:
    pid = uuid.uuid4().hex[:12]
    d = pdir(pid)
    (d / "audio").mkdir(parents=True)
    (d / "attachments").mkdir()
    (d / "originals").mkdir()
    rate = int(sample_rate) if int(sample_rate) in {44100, 48000, 96000} else 44100
    p = Project(id=pid, owner_user_id=owner_user_id, title=title[:200], target=target, sample_rate=rate, audio_storage_mode="flac" if audio_storage_mode == "flac" else "wav")
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


def _fsync_directory(path: Path) -> None:
    """Best-effort directory fsync so atomic renames survive abrupt shutdowns."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def migrate_project_audio_to_flac(project: Project) -> dict:
    """Stage+verify all integer-PCM assets, atomically commit references, then delete old WAVs.

    Only explicit user action should call this for a legacy project. Floating-point
    PCM is deliberately left untouched: integer FLAC cannot represent it exactly.
    """
    validate_project_files(project)
    filenames = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
    staged: dict[str, tuple[Path, Path]] = {}
    original_tracks = [track.filename for track in project.tracks]
    original_clips = [(clip.filename, clip.current_location) for clip in project.clip_library]
    original_mode = project.audio_storage_mode
    committed = False
    skipped: list[str] = []
    try:
        for old_name in sorted(filenames):
            if Path(old_name).suffix.lower() != ".wav":
                continue
            source = audio_path(project.id, old_name)
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name,sample_rate,channels", "-of", "json", str(source)], capture_output=True, text=True, check=True)
            stream = json.loads(probe.stdout).get("streams", [{}])[0]
            codec = stream.get("codec_name", "")
            if codec not in {"pcm_s16le", "pcm_s24le", "pcm_u8"}:
                skipped.append(old_name)
                continue
            final = source.with_name(f"{source.stem}-{uuid.uuid4().hex[:8]}.flac")
            tmp = final.with_name(f".{final.stem}.staged.flac")
            # FLAC stores integer PCM without sample-value loss; retain channel count/rate.
            run = subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(source), "-map", "0:a:0", "-c:a", "flac", "-compression_level", "1", str(tmp)], capture_output=True, text=True)
            if run.returncode:
                raise RuntimeError(f"FLAC conversion failed for {old_name}: {run.stderr.strip()}")
            verified = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(tmp), "-f", "null", "-"], capture_output=True, text=True)
            if verified.returncode or not tmp.is_file() or tmp.stat().st_size == 0:
                raise RuntimeError(f"FLAC decode validation failed for {old_name}")
            # Validate key timing characteristics before publishing the new file.
            result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels", "-of", "json", str(tmp)], capture_output=True, text=True, check=True)
            converted = json.loads(result.stdout).get("streams", [{}])[0]
            if any(str(converted.get(k)) != str(stream.get(k)) for k in ("sample_rate", "channels")):
                raise RuntimeError(f"FLAC channel/sample rate mismatch for {old_name}")
            staged[old_name] = (tmp, final)
        # File publication first; project.json remains authoritative until save.
        for tmp, final in staged.values():
            os.replace(tmp, final)
        _fsync_directory(pdir(project.id) / "audio")
        old_names = {old: final.name for old, (_, final) in staged.items()}
        for track in project.tracks:
            track.filename = old_names.get(track.filename, track.filename)
        for clip in project.clip_library:
            if clip.filename in old_names:
                clip.filename = old_names[clip.filename]
                clip.current_location = f"audio/{clip.filename}"
        project.audio_storage_mode = "flac"
        save_project(project, _skip_flac_conversion=True)
        committed = True
        # Old WAVs remain protected until a GC worker re-reads committed project.json.
        if old_names:
            reconcile_project_gc(project.id, set(old_names))
            run_project_gc(project.id)
        return {"converted": len(staged), "skipped": skipped, "audio_storage_mode": "flac"}
    except Exception:
        # No metadata is committed before conversion completes; a failed stage leaves WAV usable.
        if not committed:
            for track, original in zip(project.tracks, original_tracks):
                track.filename = original
            for clip, (name, location) in zip(project.clip_library, original_clips):
                clip.filename = name
                clip.current_location = location
            project.audio_storage_mode = original_mode
            # A failed transaction may already have published some new files.
            # Queue them instead of deleting any potentially referenced media.
            schedule_project_gc(project.id, {final.name for _, final in staged.values()})
        for tmp, _ in staged.values():
            tmp.unlink(missing_ok=True)
        raise


def save_project(project: Project, *, _skip_flac_conversion: bool = False):
    # FLAC is a project storage policy, not a global rewrite of WAV projects.
    # Persist newly rendered integer-PCM sources as FLAC only for opted-in projects.
    if not _skip_flac_conversion and project.audio_storage_mode == "flac":
        names = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
        if any(Path(name).suffix.lower() == ".wav" for name in names):
            migrate_project_audio_to_flac(project)
            return
    d = pdir(project.id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "audio").mkdir(exist_ok=True)
    (d / "attachments").mkdir(exist_ok=True)
    (d / "originals").mkdir(exist_ok=True)
    target = d / "project.json"
    tmp = d / f".project.json.{uuid.uuid4().hex}.tmp"
    payload = project.model_dump_json(indent=2).encode("utf-8")
    try:
        with tmp.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Validate the exact bytes that will become authoritative before replace.
        Project.model_validate_json(tmp.read_bytes())
        os.replace(tmp, target)
        _fsync_directory(d)
    finally:
        tmp.unlink(missing_ok=True)


def load_project(pid: str) -> Project:
    raw = (pdir(pid) / "project.json").read_text(encoding="utf-8")
    project = Project.model_validate_json(raw)
    # One-time migration: old marker entries predate persistent IDs. The IDs
    # must be saved before the next request, or each load would assign new IDs.
    if any(not marker.get("id") for marker in json.loads(raw).get("markers", [])):
        save_project(project)
    return project


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
    return _sha256_file(path)


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
    # Exclusive ownership: never overwrite a concurrent original and never
    # remove a destination unless this call created it.  Copying directly into
    # the final pathname is safe under the shared project lock; the journal
    # handles forced termination before a project commit.
    owned_identity = None
    try:
        with source.open('rb') as src, dst.open('xb') as out:
            st = os.fstat(out.fileno())
            owned_identity = (st.st_dev, st.st_ino)
            shutil.copyfileobj(src, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        directory = os.open(str(dst.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        if owned_identity is not None:
            try:
                st = dst.lstat()
                if stat.S_ISREG(st.st_mode) and (st.st_dev, st.st_ino) == owned_identity:
                    dst.unlink()
            except FileNotFoundError:
                pass
        raise
    return dst


def project_files(pid: str) -> list[dict]:
    project = load_project(pid)
    from .project_media_usage import timeline_files,pending_files
    referenced_audio = timeline_files(project)
    library = {c.filename for c in project.clip_library}
    pending,_ = pending_files(pid)
    items: list[dict] = []
    for category, subdir in (("audio","audio"),("attachment","attachments"),("original","originals")):
        base = pdir(pid) / subdir
        if base.is_symlink() or not base.exists():
            continue
        for f in sorted(base.iterdir(), key=lambda x: x.name.lower()):
            if f.is_symlink() or not f.is_file() or f.name.startswith('.'):
                continue
            busy = f.name in pending.get(category,set())
            items.append({
                "category": category,
                "name": f.name,
                "size": f.stat().st_size,
                "referenced": busy or (category == "audio" and f.name in referenced_audio),
                "timeline": category == "audio" and f.name in referenced_audio,
                "reusable": category == "audio" and f.name in library,
                "pending_job": busy,
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
    from .project_media_usage import lock,timeline_files,pending_files
    with lock(pid):
        project = load_project(pid)
        path = file_path(pid, category, filename)
        directory = {'audio':'audio','original':'originals','attachment':'attachments'}.get(category)
        if directory and ((pdir(pid)/directory).is_symlink() or (pdir(pid)/directory/filename).is_symlink()):
            raise ValueError('unsafe media link')
        if category == 'source':
            raise ValueError('cannot delete the project source file')
        pending,_ = pending_files(pid)
        if filename in pending.get(category,set()):
            raise ValueError('cannot delete media required by a pending job')
        if category == 'audio' and filename in timeline_files(project):
            raise ValueError('cannot delete an audio file referenced by a track')
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(filename)
        if category == 'audio':
            # Commit removal from the reusable library before unlinking its media.
            kept = [clip for clip in project.clip_library if clip.filename != filename]
            if len(kept) != len(project.clip_library):
                project.clip_library = kept
                save_project(project)
            reconcile_project_gc(pid,{filename})
            run_project_gc(pid)
        else:
            path.unlink()



def write_project_link(pid: str, link_path: Path) -> Path:
    """Write a lightweight native .maeproj manifest atomically.

    The heavy project data remains in the modular workspace/shared-media store.
    This file is intentionally small and is never a ZIP archive.
    """
    project = load_project(pid)
    validate_project_files(project)
    link_path = Path(link_path)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": PROJECT_LINK_SCHEMA,
        "project_id": project.id,
        "title": project.title,
        "owner_user_id": project.owner_user_id,
        "workspace_format": 1,
    }
    _atomic_json_write(link_path, payload)
    return link_path


def read_project_link(link_path: Path) -> Project:
    """Open a lightweight .maeproj manifest from the local modular workspace."""
    link_path = Path(link_path)
    if zipfile.is_zipfile(link_path):
        raise ValueError("legacy portable project archive")
    try:
        payload = json.loads(link_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("invalid project manifest") from exc
    if payload.get("schema") != PROJECT_LINK_SCHEMA:
        raise ValueError("unsupported project manifest schema")
    pid = str(payload.get("project_id") or "")
    if not PID_RE.fullmatch(pid):
        raise ValueError("invalid project id in manifest")
    project = load_project(pid)
    validate_project_files(project)
    return project


def is_portable_project_archive(path: Path) -> bool:
    """Return True for legacy/current portable ZIP project archives."""
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False

def write_project_archive(pid: str, archive_path: Path) -> Path:
    """Write a .maeproj atomically so autosave can never expose a partial ZIP.

    The archive is assembled and validated in a sibling temporary file, fsynced,
    and only then atomically replaces the previous project file. If the process
    exits or is killed during autosave, the prior valid archive stays untouched.
    """
    project = load_project(pid)
    validate_project_files(project)
    base = pdir(pid)
    archive_path = Path(archive_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": PROJECT_ARCHIVE_SCHEMA,
        "project_id": project.id,
        "title": project.title,
        "owner_user_id": project.owner_user_id,
        "includes_originals": True,
    }
    tmp = archive_path.parent / f".{archive_path.name}.{uuid.uuid4().hex}.tmp"
    try:
        pending_gc = _read_gc_queue(pid)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.writestr("archive-manifest.json", json.dumps(manifest, indent=2))
            for path in sorted(base.rglob("*")):
                if not path.is_file():
                    continue
                rel = path.relative_to(base)
                if path.name == GC_QUEUE_NAME or (path.name.startswith(".project.json.") and path.name.endswith(".tmp")):
                    continue
                if rel.parts and rel.parts[0] == ".preview":
                    continue
                if path.name == "preview-master.mp3" or path.name.startswith(".sample-fx-"):
                    continue
                if path.parent == (base / "audio") and path.name in pending_gc:
                    continue
                z.write(path, Path("project") / path.relative_to(base))
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        # Refuse to replace a valid existing archive with an incomplete/corrupt one.
        with zipfile.ZipFile(tmp, "r") as z:
            if z.testzip() is not None:
                raise ValueError("corrupt project archive")
            if "archive-manifest.json" not in z.namelist() or "project/project.json" not in z.namelist():
                raise ValueError("incomplete project archive")
            Project.model_validate_json(z.read("project/project.json"))
        os.replace(tmp, archive_path)
        _fsync_directory(archive_path.parent)
    finally:
        tmp.unlink(missing_ok=True)
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
                if rel.name == GC_QUEUE_NAME:
                    continue
                if rel.parts and rel.parts[0] == "vst3-checkpoints":
                    # The isolated worker's state is inert data, but impose
                    # bounds before decompressing untrusted project archives.
                    if (len(rel.parts) != 2 or not re.fullmatch(
                            r"[A-Za-z0-9_-]{1,64}--[A-Za-z0-9_-]{1,64}\.json", rel.name)
                            or info.file_size > 3 * 1024 * 1024):
                        raise ValueError("invalid VST3 checkpoint in project archive")
                if rel.parts and rel.parts[0] == ".preview":
                    continue
                if rel.name == "preview-master.mp3" or rel.name.startswith(".sample-fx-"):
                    continue
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
