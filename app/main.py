import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .audio_engine import auto_align_ms, delete_range, delete_song_range, ensure_clips, media_duration_ms, render_mix, shift_track
from .codec import export_mta, ffprobe, import_mta
from .models import Clip, DeleteRangeRequest, MoveTrackRequest, Project, Track
from .plugins import STEM_SPLITTER, plugin_catalog
from .security import auth_failure_response, check_basic_auth
from .storage import (
    audio_path,
    create_project,
    delete_project,
    list_projects,
    load_project,
    pdir,
    save_project,
    validate_project_files,
)
from .version import APP_VERSION, BUILD_ID, CREATOR, REPOSITORY

app = FastAPI(title="MTA Audio Editor", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)
BASE = Path(__file__).parent
MAX_UPLOAD_BYTES = int(os.getenv("MTA_MAX_UPLOAD_MB", "512")) * 1024 * 1024
SAFE_DOWNLOAD_RE = re.compile(r"[^A-Za-z0-9._ -]+")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def _is_public(path: str) -> bool:
    return path.startswith("/static/") or path in {
        "/api/health",
        "/api/about",
        "/docs/user",
        "/docs/pdf/user",
    }


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if not _is_public(request.url.path) and not check_basic_auth(request):
        return auth_failure_response()

    # Browser clients must mark every state-changing request. This prevents
    # cross-site form submission from reusing cached HTTP Basic credentials.
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-mta-request") != "1":
        return HTMLResponse("Missing request integrity header", status_code=403)

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_BYTES + 1024 * 1024:
                return HTMLResponse("Request too large", status_code=413)
        except ValueError:
            return HTMLResponse("Invalid Content-Length", status_code=400)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; media-src 'self' blob:; connect-src 'self'"
    )
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


@app.get("/", response_class=HTMLResponse)
def home():
    return (
        (BASE / "templates" / "index.html")
        .read_text(encoding="utf-8")
        .replace("__VERSION__", APP_VERSION)
        .replace("__BUILD__", BUILD_ID)
    )


def _render_doc(name: str) -> str:
    return (
        (BASE / "docs" / name)
        .read_text(encoding="utf-8")
        .replace("__VERSION__", APP_VERSION)
        .replace("__BUILD__", BUILD_ID)
        .replace("__CREATOR__", CREATOR)
        .replace("__REPOSITORY__", REPOSITORY)
    )


@app.get("/docs/user", response_class=HTMLResponse)
def user_docs():
    return _render_doc("user.html")


@app.get("/docs/admin", response_class=HTMLResponse)
def admin_docs():
    return _render_doc("admin.html")


@app.get("/docs/pdf/user")
def user_pdf():
    return FileResponse(BASE / "docs" / "MTA-Audio-Editor-User-Manual.pdf", filename="MTA-Audio-Editor-User-Manual.pdf")


@app.get("/docs/pdf/admin")
def admin_pdf():
    return FileResponse(
        BASE / "docs" / "MTA-Audio-Editor-Administrator-Manual.pdf",
        filename="MTA-Audio-Editor-Administrator-Manual.pdf",
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION, "build": BUILD_ID}


@app.get("/api/about")
def about():
    return {
        "name": "MTA Audio Editor",
        "version": APP_VERSION,
        "build": BUILD_ID,
        "creator": CREATOR,
        "repository": REPOSITORY,
        "license": "EUPL-1.2",
    }




@app.get("/api/plugins")
def plugins():
    return {"inserts": plugin_catalog(), "stem_splitter": STEM_SPLITTER.status()}


@app.get("/api/projects")
def projects():
    return list_projects()


@app.post("/api/projects")
def project_new(title: str = "Untitled", target: str = "MTA8"):
    return create_project(title, target if target in {"MTA8", "MTA16"} else "MTA8")


@app.get("/api/projects/{pid}")
def project_get(pid: str):
    try:
        project = load_project(pid)
        for track in project.tracks:
            ensure_clips(track)
        return project
    except (OSError, ValueError):
        raise HTTPException(404, "project not found") from None


@app.put("/api/projects/{pid}")
def project_put(pid: str, project: Project):
    if pid != project.id:
        raise HTTPException(400, "project id mismatch")
    try:
        validate_project_files(project)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    save_project(project)
    return project


@app.delete("/api/projects/{pid}")
def project_delete(pid: str):
    try:
        delete_project(pid)
    except ValueError as exc:
        raise HTTPException(400, "invalid project id") from exc
    return {"ok": True}


@app.get("/api/projects/{pid}/audio/{filename}")
def project_audio(pid: str, filename: str):
    try:
        path = audio_path(pid, filename)
    except ValueError as exc:
        raise HTTPException(400, "invalid audio path") from exc
    if not path.exists():
        raise HTTPException(404, "audio not found")
    return FileResponse(path)


def _copy_limited(src, dst: Path):
    total = 0
    with dst.open("wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                dst.unlink(missing_ok=True)
                raise HTTPException(413, "upload exceeds configured limit")
            out.write(chunk)


def _save_upload(pid: str, file: UploadFile):
    ext = Path(file.filename or "track.wav").suffix.lower() or ".bin"
    if len(ext) > 12 or not ext.replace(".", "").isalnum():
        raise HTTPException(400, "invalid file extension")
    filename = f"{uuid.uuid4().hex[:10]}{ext}"
    dst = audio_path(pid, filename)
    _copy_limited(file.file, dst)
    try:
        ffprobe(dst)
    except Exception as exc:
        dst.unlink(missing_ok=True)
        raise HTTPException(400, "invalid or unsupported audio file") from exc
    return filename, dst, media_duration_ms(dst)


@app.post("/api/projects/{pid}/tracks")
async def add_track(
    pid: str,
    file: UploadFile = File(...),
    name: str = "",
    type: str = "other",
    offset_ms: int = 0,
    sync_mode: str = "manual",
    reference_track_id: str = "",
):
    project = load_project(pid)
    if len(project.tracks) >= (8 if project.target == "MTA8" else 16):
        raise HTTPException(400, "track limit reached")
    filename, dst, duration = _save_upload(pid, file)
    allowed = Track.model_fields["type"].annotation.__args__
    track = Track(
        id=uuid.uuid4().hex[:10],
        name=(name or Path(file.filename or filename).stem)[:200],
        type=type if type in allowed else "other",
        filename=filename,
        duration_ms=duration,
        clips=[
            Clip(
                id=uuid.uuid4().hex[:10],
                source_start_ms=0,
                source_end_ms=duration,
                timeline_start_ms=max(0, offset_ms),
            )
        ],
    )
    if sync_mode == "auto" and project.tracks:
        ref = next((item for item in project.tracks if item.id == reference_track_id), project.tracks[0])
        try:
            delta = auto_align_ms(audio_path(pid, ref.filename), dst)
            shift_track(track, delta)
        except Exception as exc:
            dst.unlink(missing_ok=True)
            raise HTTPException(400, "automatic sync failed") from exc
    project.tracks.append(track)
    save_project(project)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/replace")
async def replace_track(
    pid: str,
    track_id: str,
    file: UploadFile = File(...),
    sync_mode: str = "keep",
    offset_ms: int = 0,
    reference_track_id: str = "",
):
    project = load_project(pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    ensure_clips(track)
    previous_offset = track.clips[0].timeline_start_ms if track.clips else 0
    old = audio_path(pid, track.filename)
    filename, dst, duration = _save_upload(pid, file)

    track.filename = filename
    track.duration_ms = duration
    track.clips = [Clip(id=uuid.uuid4().hex[:10], source_start_ms=0, source_end_ms=duration, timeline_start_ms=0)]
    try:
        if sync_mode == "manual":
            shift_track(track, offset_ms)
        elif sync_mode == "auto":
            refs = [item for item in project.tracks if item.id != track.id]
            if not refs:
                raise HTTPException(400, "automatic sync needs another reference track")
            ref = next((item for item in refs if item.id == reference_track_id), refs[0])
            shift_track(track, auto_align_ms(audio_path(pid, ref.filename), dst))
        elif sync_mode == "keep":
            shift_track(track, previous_offset)
        else:
            raise HTTPException(400, "invalid sync mode")
    except HTTPException:
        dst.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dst.unlink(missing_ok=True)
        raise HTTPException(400, "automatic sync failed") from exc

    save_project(project)
    if old.exists() and old.name != filename:
        old.unlink(missing_ok=True)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/move")
def move_track(pid: str, track_id: str, req: MoveTrackRequest):
    project = load_project(pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    shift_track(track, req.offset_ms)
    save_project(project)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/autosync")
def autosync_track(pid: str, track_id: str, reference_track_id: str = ""):
    project = load_project(pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    refs = [item for item in project.tracks if item.id != track_id]
    if not track or not refs:
        raise HTTPException(400, "track/reference not available")
    ref = next((item for item in refs if item.id == reference_track_id), refs[0])
    try:
        delta = auto_align_ms(audio_path(pid, ref.filename), audio_path(pid, track.filename))
        shift_track(track, delta)
        save_project(project)
        return {"project": project, "delta_ms": delta, "reference_track_id": ref.id}
    except Exception as exc:
        raise HTTPException(400, "automatic sync failed") from exc


@app.post("/api/projects/{pid}/delete-range")
def edit_delete_range(pid: str, req: DeleteRangeRequest):
    project = load_project(pid)
    if req.end_ms <= req.start_ms:
        raise HTTPException(400, "invalid range")
    if req.track_ids is None:
        delete_song_range(project, req.start_ms, req.end_ms)
    else:
        wanted = set(req.track_ids)
        known = {track.id for track in project.tracks}
        if not wanted <= known:
            raise HTTPException(400, "unknown track id in selection")
        for track in project.tracks:
            if track.id in wanted:
                delete_range(track, req.start_ms, req.end_ms, req.ripple)
    save_project(project)
    return project


@app.post("/api/import")
async def import_file(file: UploadFile = File(...)):
    project = create_project(Path(file.filename or "Imported").stem[:200])
    src = pdir(project.id) / "source.mta"
    _copy_limited(file.file, src)
    try:
        return import_mta(src, project)
    except Exception as exc:
        delete_project(project.id)
        raise HTTPException(400, "MTA import failed") from exc


def _download_name(title: str, ext: str) -> str:
    clean = SAFE_DOWNLOAD_RE.sub("_", title).strip(" ._")[:120] or "project"
    return f"{clean}.{ext}"


@app.post("/api/stems/split")
async def split_stems(
    file: UploadFile = File(...),
    project_id: str = "",
    target: str = "MTA8",
    model: str = "htdemucs_6s",
):
    if Path(file.filename or "").suffix.lower() != ".mp3":
        raise HTTPException(400, "stem separation currently accepts MP3 input")
    if not STEM_SPLITTER.available():
        raise HTTPException(503, "Demucs stem plugin is not installed in this runtime")
    try:
        project = load_project(project_id) if project_id else create_project(Path(file.filename or "Stems").stem[:200], target if target in {"MTA8", "MTA16"} else "MTA8")
    except (OSError, ValueError) as exc:
        raise HTTPException(404, "project not found") from exc
    max_tracks = 8 if project.target == "MTA8" else 16
    if len(project.tracks) >= max_tracks:
        raise HTTPException(400, "track limit reached")
    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        source = td / "source.mp3"
        _copy_limited(file.file, source)
        try:
            ffprobe(source)
            stems = STEM_SPLITTER.split(source, td / "stems", model=model)
        except Exception as exc:
            raise HTTPException(400, "stem separation failed") from exc
        mapping = {
            "drums": "drums", "bass": "bass", "guitar": "guitars", "piano": "keyboards",
            "vocals": "melody", "other": "other"
        }
        room = max_tracks - len(project.tracks)
        for stem in stems[:room]:
            stem_name = stem.stem.lower()
            kind = mapping.get(stem_name, "other")
            filename = f"{uuid.uuid4().hex[:10]}.wav"
            dst = audio_path(project.id, filename)
            shutil.copyfile(stem, dst)
            duration = media_duration_ms(dst)
            project.tracks.append(Track(
                id=uuid.uuid4().hex[:10], name=stem.stem.title(), type=kind, filename=filename, duration_ms=duration,
                clips=[Clip(id=uuid.uuid4().hex[:10], source_start_ms=0, source_end_ms=duration, timeline_start_ms=0)]
            ))
    save_project(project)
    return project


@app.get("/api/projects/{pid}/preview-mix")
def preview_mix(pid: str):
    project = load_project(pid)
    out = pdir(pid) / "preview-master.mp3"
    try:
        validate_project_files(project)
        render_mix(project, audio_path, out, fmt="mp3", bitrate="192k")
    except Exception as exc:
        raise HTTPException(400, "preview mix failed") from exc
    return FileResponse(out, media_type="audio/mpeg", filename="preview-master.mp3")


@app.get("/api/projects/{pid}/export")
def export(pid: str, format: str = "mta"):
    project = load_project(pid)
    try:
        validate_project_files(project)
        if format == "mta":
            ext = "mta8" if project.target == "MTA8" else "mta16"
            out = pdir(pid) / f"export.{ext}"
            export_mta(project, out)
            media_type = "application/octet-stream"
        elif format == "wav":
            ext = "wav"
            out = pdir(pid) / "export.wav"
            render_mix(project, audio_path, out, fmt="wav")
            media_type = "audio/wav"
        elif format == "mp3":
            ext = "mp3"
            out = pdir(pid) / "export.mp3"
            render_mix(project, audio_path, out, fmt="mp3", bitrate="320k")
            media_type = "audio/mpeg"
        else:
            raise HTTPException(400, "unsupported export format")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "export failed") from exc
    return FileResponse(out, filename=_download_name(project.title, ext), media_type=media_type)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=os.getenv("MTA_HOST", "0.0.0.0"), port=int(os.getenv("MTA_PORT", "8080")))
