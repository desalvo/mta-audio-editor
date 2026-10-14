import stat
from app.secure_https import https_urlopen
import base64
import hashlib
import json
import logging
import os
import re
import shutil
import shlex
import subprocess
import tempfile
import threading
import time
import uuid
import zipfile
import wave
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles

from .audio_engine import auto_align_ms, delete_range, delete_song_range, ensure_clips, estimate_bpm_and_signature, estimate_adaptive_tempo_map, generate_adaptive_metronome_wav, generate_chords_piano_wav, generate_silent_chords_wav, refresh_chords_piano_wav_region, refresh_chords_waveform_region, generate_metronome_wav, zoned_metronome_beats, stabilize_adaptive_beats, media_duration_ms, project_duration_ms, render_mix, render_track, render_track_export, shift_track, waveform_peaks
from .codec import export_mta, ffprobe, import_mta, resolve_mta_device_profile, suggested_slots, validate_slot_mapping
from .models import AutoMixRequest, Clip, CustomPresetRequest, DeleteRangeRequest, DeleteTracksRequest, InstantiateProjectClipRequest, UpdateProjectClipRequest, MoveTrackRequest, TrackDelayRequest, MtaExportRequest, Project, ProjectClip, ProjectExportRequest, TrackExportRequest, RightsRecord, Track, SampleEditRequest, SampleEffectRequest
from .mlive_mp3 import embed_mlive_merish_metadata
from .mp3g import build_mp3g_zip
from .plugins import STEM_SPLITTER, delete_user_preset, plugin_manifest, save_user_preset

from .model_updater import (COREML_DIR, ONNX_DIR, start_background_updater, update_once as update_mobile_demucs_models,
    server_inventory as demucs_server_inventory, blacklist_model as blacklist_demucs_model,
    unblacklist_model as unblacklist_demucs_model, load_blacklist as demucs_blacklist,
    public_catalog as demucs_public_catalog, native_bundle as demucs_native_bundle,
    delete_local_model as delete_local_demucs_model, model_storage_usage as demucs_model_storage_usage)
COREML_DEMUCS_MODEL_DIR = Path(os.getenv("MTA_DEMUCS_COREML_MODEL_DIR", str(COREML_DIR))).expanduser()
ONNX_DEMUCS_MODEL_DIR = Path(os.getenv("MTA_DEMUCS_ONNX_MODEL_DIR", str(ONNX_DIR))).expanduser()
from .security import auth_failure_response, check_basic_auth
from .auth import (
    authenticate, begin_totp, confirm_email, create_session, delete_session, disable_totp,
    enable_totp, find_user, get_smtp_config, get_user, list_users, public_user,
    register_user, require_admin, require_user, resend_verification, save_smtp_config,
    session_user, test_smtp_config, totp_qr_svg, totp_uri, update_profile,
    update_user_admin, delete_user_admin, change_password, request_password_reset, reset_password,
    oauth_public_providers, oauth_authorize_url, oauth_verify_state, oauth_exchange_profile, social_login_or_register,
    create_model_access_token, model_access_token, require_model_read, revoke_model_access_tokens,
)
from .auto_mix import disable_auto_mix, enable_auto_mix
from .ai_models import ai_catalog, chords_catalog, lyrics_catalog, download_chord_model, download_lyrics_model, delete_chord_model, delete_lyrics_model, chord_engine_available
from .mta_reverse import analyze_mta, diff_blobs
from .music_text import build_chordpro, build_karaoke_ass, build_lyrics_pdf, extract_chords, extract_chords_progressive, extract_lyrics, extract_lyrics_progressive, extract_markers, lyrics_engine_available, map_source_events_to_timeline, synchronized_plain_text, transpose_chords, transpose_key_name
from .storage import (
    audio_path,
    create_project,
    delete_project,
    delete_project_file,
    file_path,
    find_duplicate_project_file,
    import_project_archive,
    list_projects,
    load_project,
    migrate_project_audio_to_flac,
    pdir,
    preserve_original,
    originals_dir,
    project_access,
    project_files,
    save_project,
    validate_project_files,
    write_project_archive,
    ROOT as STORAGE_ROOT,
    schedule_project_gc,
    resume_pending_gc,
    maintain_project_storage,
    rescan_shared_media,
    session_preview_dir,
    cleanup_session_preview_cache,
)
from .rights_registry import (provider_catalog as rights_provider_catalog, search_provider as search_rights_provider, search_musicbrainz_metadata, resolve_musicbrainz_metadata)
from . import sample_editor as sample_editor_engine
from .version import APP_RELEASE, APP_RELEASE_CHANNEL, APP_REVISION, APP_VERSION, BUILD_ID, CREATOR, REPOSITORY

from .ai_arranger import RearrangeRequest, RemixRequest, catalog as arranger_catalog, prepare_plan as arranger_plan, prepare_remix_plan, assess_plan
from .ai_job_queue import ai_jobs
from . import ai_arranger_runtime
from .ai_token_routes import router as ai_token_router
from .ai_gateway import router as ai_gateway_router
from .ai_billing_routes import router as ai_billing_router
from .ai_worker_protocol import configured_worker, run_worker_with_project_audio, worker_capabilities, WorkerUnavailable

app = FastAPI(title="MTA Audio Editor", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(ai_token_router)
app.include_router(ai_gateway_router)
app.include_router(ai_billing_router)


def _audible_export_project(project: Project) -> Project:
    """Return an export-only view that omits tracks explicitly muted by the user."""
    export_project = project.model_copy(deep=True)
    export_project.tracks = [track for track in export_project.tracks if not track.mute]
    if not export_project.tracks:
        raise ValueError("all project tracks are muted")
    return export_project


def _musical_export_project(project: Project) -> Project:
    """Return a non-destructive MTA export view with mute filtering and transposition."""
    export_project = _audible_export_project(project)
    export_project.chords = transpose_chords([ch for ch in project.chords if not ch.excluded], project.pitch_semitones)
    export_project.key = transpose_key_name(project.key, project.pitch_semitones)
    return export_project

@app.on_event("startup")
def _start_diagnostic_cleanup():
    # Cleanup works even with collection disabled; daemon stops on process exit.
    def loop():
        import time as _time
        while True:
            try:
                _mta_diagnostics.clean()
            except (OSError, RuntimeError):
                LOGGER.warning("Diagnostics cleanup unavailable", exc_info=True)
            _time.sleep(3600)
    _mta_diagnostics.install_event_capture()
    threading.Thread(target=loop, daemon=True, name="mta-diagnostic-retention").start()


@app.on_event("startup")
def _start_background_services():
    # Repair interrupted stem imports before exposing restored project state.
    # A damaged journal is left intact and never triggers destructive cleanup.
    try:
        from .ai_recovered_stem_transaction import reconcile_on_startup
        stem_recovery = reconcile_on_startup()
        LOGGER.info('Recovered stem imports on startup: %s', stem_recovery)
        if stem_recovery['errors']:
            LOGGER.error('Unresolved stem import journals: %s', stem_recovery['errors'])
    except Exception:
        LOGGER.exception('Recovered stem import startup reconciliation unavailable')
    try:
        from .ai_upload_transaction import reconcile_on_startup as recover_uploads
        upload_recovery = recover_uploads()
        LOGGER.info('Ordinary upload recovery on startup: %s', upload_recovery)
        if upload_recovery['errors']:
            LOGGER.error('Unresolved ordinary uploads: %s', upload_recovery['errors'])
    except Exception:
        LOGGER.exception('Ordinary upload startup recovery unavailable')
    try:
        from .ai_async_track_transaction import reconcile_on_startup as recover_async_tracks
        async_track_recovery = recover_async_tracks()
        LOGGER.info('Async track recovery on startup: %s', async_track_recovery)
        if async_track_recovery['errors']:
            LOGGER.error('Unresolved async track receipts: %s', async_track_recovery['errors'])
    except Exception:
        LOGGER.exception('Async track startup reconciliation unavailable')
    start_background_updater()
    resume_pending_gc()
    if NATIVE_SINGLE_USER:
        # ACE-Step may initialise large models or contact its local backend.
        # Never block the native WebView HTTP readiness on optional AI startup.
        def _launch_optional_ace_step() -> None:
            try:
                from .ace_step_desktop_manager import auto_start_server
                auto_start_server()
            except Exception:
                LOGGER.exception("Optional desktop ACE-Step autostart failed")
        threading.Thread(target=_launch_optional_ace_step, daemon=True,
                         name="mta-desktop-ace-autostart").start()


@app.on_event("shutdown")
def _cleanup_session_previews_on_shutdown():
    if NATIVE_SINGLE_USER:
        from .ace_step_desktop_manager import stop_server
        stop_server()
    cleanup_session_preview_cache()
LOGGER = logging.getLogger(__name__)
BASE = Path(__file__).parent
MAX_UPLOAD_BYTES = int(os.getenv("MTA_MAX_UPLOAD_MB", "1024")) * 1024 * 1024
NATIVE_SINGLE_USER = os.getenv("MTA_NATIVE_SINGLE_USER", "").lower() in {"1", "true", "yes", "on"}


LEAD_BACKING_MODELS = [
    {"id": "uvr_mdxnet_kara_2", "filename": "UVR_MDXNET_KARA_2.onnx", "display_name": "UVR-MDX-NET Karaoke 2", "engine": "MDX", "quality": "balanced", "recommended": True},
    {"id": "mel_roformer_karaoke_aufr33", "filename": "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", "display_name": "Mel-RoFormer Karaoke Aufr33/Viperx", "engine": "RoFormer", "quality": "high", "recommended": False},
    {"id": "mel_roformer_karaoke_gabox_v2", "filename": "mel_band_roformer_karaoke_gabox_v2.ckpt", "display_name": "MelBand RoFormer Karaoke Gabox V2", "engine": "RoFormer", "quality": "high", "recommended": False},
]
LEAD_BACKING_DEFAULT_MODEL = os.getenv("MTA_LEAD_BACKING_DEFAULT_MODEL", "uvr_mdxnet_kara_2").strip() or "uvr_mdxnet_kara_2"
LEAD_BACKING_MODEL_DIR = Path(os.getenv("MTA_LEAD_BACKING_MODEL_DIR", str(STORAGE_ROOT / ".cache" / "lead-backing-models"))).expanduser().resolve()

def _lead_backing_model_info(model_id: str) -> dict:
    model = next((dict(item) for item in LEAD_BACKING_MODELS if item["id"] == model_id), None)
    if model is None:
        raise ValueError("unsupported lead/backing vocal model")
    model["installed"] = (LEAD_BACKING_MODEL_DIR / model["filename"]).exists()
    model["location"] = "local" if NATIVE_SINGLE_USER else "server"
    model["path"] = str(LEAD_BACKING_MODEL_DIR / model["filename"])
    return model

def _lead_backing_engine_available() -> bool:
    # Do not import the heavy ML stack to render a settings dialog.
    import importlib.util
    try:
        return importlib.util.find_spec("audio_separator") is not None
    except (ImportError, ValueError):
        return False


def _lead_backing_catalog() -> dict:
    return {
        "default_model": LEAD_BACKING_DEFAULT_MODEL if any(x["id"] == LEAD_BACKING_DEFAULT_MODEL for x in LEAD_BACKING_MODELS) else "uvr_mdxnet_kara_2",
        "models": [_lead_backing_model_info(item["id"]) for item in LEAD_BACKING_MODELS],
        "storage": "local" if NATIVE_SINGLE_USER else "server",
        "on_demand": True,
        "engine_available": _lead_backing_engine_available(),
        "model_directory": str(LEAD_BACKING_MODEL_DIR),
    }

def _download_lead_backing_model(model_id: str) -> dict:
    info = _lead_backing_model_info(model_id)
    LEAD_BACKING_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from audio_separator.separator import Separator
    except ImportError as exc:
        raise RuntimeError("Il motore audio-separator non è installato in questo runtime. Installare le dipendenze di separazione (requirements-stems.txt) e riavviare l’app, oppure selezionare il metodo DSP FFmpeg center/side.") from exc
    separator = Separator(model_file_dir=str(LEAD_BACKING_MODEL_DIR), output_dir=str(LEAD_BACKING_MODEL_DIR), info_only=True)
    separator.download_model_files(info["filename"])
    return _lead_backing_model_info(model_id)

NATIVE_BLOCKED_PATH_PREFIXES = (
    "/account",
    "/admin/",
    "/api/account",
    "/api/admin/",
    "/register",
    "/forgot-password",
    "/reset-password",
    "/verify-email",
    "/resend-verification",
    "/oauth/",
)


SAFE_DOWNLOAD_RE = re.compile(r"[^A-Za-z0-9._ -]+")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

STEM_JOBS: dict[str, dict] = {}
STEM_JOB_LOCK = threading.Lock()
MEDIA_JOBS: dict[str, dict] = {}
MEDIA_JOB_LOCK = threading.Lock()
METRONOME_TRACK_LOCK = threading.Lock()
CHORDS_TRACK_LOCK = threading.Lock()



def _stem_job_update(job_id: str, **changes) -> None:
    with STEM_JOB_LOCK:
        job = STEM_JOBS.get(job_id)
        if job is not None:
            job.update(changes)
            job["updated_at"] = time.time()


def _stem_durable_payload(job: dict, source: Path, keep_original_track: bool) -> dict:
    """Persist only project-owned source locators and JSON-safe stem options."""
    pid = job["project_id"]
    source = Path(source).resolve(strict=True)
    locator = None
    for category in ("audio", "original"):
        try:
            candidate = file_path(pid, category, source.name)
            if candidate.resolve(strict=True) == source:
                locator = category
                break
        except (ValueError, OSError):
            continue
    if locator is None:
        raise ValueError("Stem source must belong to the project storage")
    fields = ("source_track_id", "model", "stem_count", "filename", "estimate_bpm",
              "stem_name_prefix", "extract_lyrics", "extract_chords", "lyrics_model",
              "chords_engine", "split_backing_vocals", "backing_vocal_model",
              "split_percussions", "percussion_method", "stem_targets", "singer_mode",
              "singers", "singer_model", "singer_target")
    return {"schema_version": 1, "project_id": pid, "source_category": locator,
            "source_name": source.name, "keep_original_track": bool(keep_original_track),
            "options": {name: job.get(name) for name in fields}}


def _restore_stem_split_job(pid, payload, job_id):
    """Restore *only queued* stem work using a validated project-local source."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("project_id") != pid:
        raise ValueError("Invalid durable stem request")
    category, name, options = payload.get("source_category"), payload.get("source_name"), payload.get("options")
    if category not in ("audio", "original") or not isinstance(name, str) or not isinstance(options, dict):
        raise ValueError("Invalid stem source or options")
    if type(payload.get("keep_original_track")) is not bool:
        raise ValueError("Invalid stem track policy")
    source = file_path(pid, category, name)
    if not source.is_file() or source.is_symlink() or source.stat().st_nlink != 1:
        raise ValueError("Missing or unsafe durable stem source")
    if not isinstance(options.get("model"), str) or not options["model"]:
        raise ValueError("Invalid stem model")
    if type(options.get("stem_count")) is not int or options["stem_count"] < 0:
        raise ValueError("Invalid stem count")
    targets = options.get("stem_targets")
    if not isinstance(targets, list) or not targets or any(not isinstance(t, str) for t in targets) or not set(targets) <= _STEM_TARGETS:
        raise ValueError("Invalid stem targets")
    for field in ("split_backing_vocals", "split_percussions", "singer_mode", "extract_lyrics", "extract_chords", "estimate_bpm"):
        if options.get(field) is not None and type(options[field]) is not bool:
            raise ValueError("Invalid stem flag")
    if not isinstance(options.get("singers"), list):
        raise ValueError("Invalid singers")
    load_project(pid)
    now = time.time()
    with STEM_JOB_LOCK:
        job = STEM_JOBS.setdefault(job_id, {
            "id": job_id, "project_id": pid, "status": "queued", "progress": 5,
            "message": "Recovered queued stem separation", "created_at": now,
            "updated_at": now, "error": None, "cancel_event": threading.Event(),
            **options,
        })
    def execute(_progress_path, stop):
        job["cancel_event"] = stop
        if stop.is_set():
            job["status"] = "cancelled"
            return
        _stem_split_worker(job_id, source, payload["keep_original_track"])
        if job["status"] == "failed":
            raise RuntimeError(str(job.get("error") or "Stem separation failed")[:300])
    return execute


ai_arranger_runtime.register_restorer("stem-separation", _restore_stem_split_job)


def _stem_job_public(job: dict) -> dict:
    queue_row = _legacy_ai_queue_state(job)
    return {
        "queue_position": queue_row.get("queue_position") if queue_row else None,
        "jobs_ahead": queue_row.get("jobs_ahead") if queue_row else 0,
        "id": job["id"],
        "project_id": job["project_id"],
        "source_track_id": job.get("source_track_id"),
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "model": job["model"],
        "filename": job["filename"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "cancel_requested": job["cancel_event"].is_set(),
        "error": job.get("error"),
        "analysis": job.get("analysis", {}),
        "vocal_split_method": job.get("vocal_split_method"),
        "backing_vocal_model": job.get("backing_vocal_model"),
        "split_backing_vocals": bool(job.get("split_backing_vocals")),
        "split_percussions": bool(job.get("split_percussions")),
        "stem_targets": job.get("stem_targets", ["all"]),
        "singer_mode": bool(job.get("singer_mode")),
        "singer_model": job.get("singer_model"),
        "singer_target": job.get("singer_target"),
        "singers": job.get("singers", []),
    }


def _media_job_update(job_id: str, **changes) -> None:
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.get(job_id)
        if job is not None:
            job.update(changes)
            job["updated_at"] = time.time()


def _enqueue_existing_ai_job(job: dict, work, *, durable_payload=None):
    """Admit legacy AI work to the shared SQLite FIFO queue.

    Lyrics/chords requests carry a versioned, reconstructible payload. Other
    legacy callables remain intentionally non-replayable until their side
    effects can be made crash-safe.
    """
    jid = job["id"]
    project = job.get("project_id") or "server-models"
    def run(_progress_path, stop=None):
        if stop is not None:
            job["cancel_event"] = stop
        if job.get("cancel_event") is not None and job["cancel_event"].is_set():
            job["status"] = "cancelled"
            return
        job["status"] = "running"
        work()
        if job.get("status") in ("failed", "error"):
            raise RuntimeError(str(job.get("error") or "AI worker failed")[:300])
    if durable_payload is not None:
        operation = "stem-separation" if job["id"] in STEM_JOBS else job.get("kind", "ai")
        return ai_arranger_runtime.start(project, operation, run,
            job_id=jid, payload=durable_payload, cancellable=True)
    return ai_arranger_runtime.start(project, job.get("kind", "ai"), run, job_id=jid)


def _restore_text_music_job(pid, payload, job_id):
    """Restore queued Whisper/chords only; never replay a running job.

    The queue owns crash decisions. Rebuild the legacy API status projection
    before returning a callable, so web clients can poll restored jobs.
    """
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported text AI request schema")
    kind = payload.get("kind")
    if kind not in ("lyrics", "chords", "markers") or payload.get("project_id") != pid:
        raise ValueError("Text AI adapter/payload mismatch")
    if not isinstance(payload.get("track_id"), str) or not payload["track_id"]:
        raise ValueError("Invalid text AI track")
    if payload.get("model_or_engine") is not None and not isinstance(payload["model_or_engine"], str):
        raise ValueError("Invalid text AI model")
    if type(payload.get("advanced_alignment", False)) is not bool:
        raise ValueError("Invalid alignment flag")
    options = payload.get("chord_options")
    if options is not None and not isinstance(options, dict):
        raise ValueError("Invalid chord options")
    start, end = payload.get("range_start_ms"), payload.get("range_end_ms")
    if (start is None) != (end is None) or (start is not None and
        (type(start) is not int or type(end) is not int or start < 0 or end <= start)):
        raise ValueError("Invalid text AI range")
    # Validate the project and source before scheduling recovered inference.
    project = load_project(pid)
    if not any(item.id == payload["track_id"] for item in project.tracks):
        raise ValueError("Restored text AI track no longer exists")
    with MEDIA_JOB_LOCK:
        if job_id not in MEDIA_JOBS:
            now = time.time()
            MEDIA_JOBS[job_id] = {
                "id": job_id, "kind": "extract-" + kind, "project_id": pid,
                "status": "queued", "progress": 0, "message": "Recovered queued AI analysis",
                "created_at": now, "updated_at": now, "result": None,
                "error": None, "partial": None, "cancel_event": threading.Event(),
            }
        job = MEDIA_JOBS[job_id]
    def execute(_progress_path, stop):
        job["cancel_event"] = stop
        if stop.is_set():
            job["status"] = "cancelled"
            return
        job["status"] = "running"
        _text_music_worker(job_id, pid, payload["track_id"], kind,
            payload.get("model_or_engine") or "", payload.get("advanced_alignment", False),
            options, start, end)
        if job.get("status") in ("failed", "error"):
            raise RuntimeError(str(job.get("error") or "Text AI job failed")[:300])
    return execute


for _text_ai_kind in ("lyrics", "chords", "markers"):
    ai_arranger_runtime.register_restorer("extract-" + _text_ai_kind, _restore_text_music_job)


def _legacy_ai_queue_state(job: dict):
    try:
        row = ai_arranger_runtime.get(job["id"])
    except (OSError, ValueError):
        return None
    if not row:
        return None
    if row["state"] in ("queued", "cancelled", "interrupted"):
        job["status"] = row["state"]
        job["message"] = row["message"]
    return row


def _media_job_public(job: dict) -> dict:
    cancel_event=job.get("cancel_event")
    queue_row = _legacy_ai_queue_state(job)
    return {
        "queue_position": queue_row.get("queue_position") if queue_row else None,
        "jobs_ahead": queue_row.get("jobs_ahead") if queue_row else 0,
        "id": job["id"],
        "kind": job["kind"],
        "project_id": job.get("project_id"),
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "result": job.get("result"),
        "error": job.get("error"),
        "partial": job.get("partial"),
        "cancel_supported": cancel_event is not None,
        "cancel_requested": bool(cancel_event and cancel_event.is_set()),
    }



def _is_public(path: str) -> bool:
    return (
        path.startswith("/static/")
        or path in {"/api/health", "/api/about", "/login", "/register", "/verify-email", "/resend-verification", "/forgot-password", "/reset-password"}
        or path.startswith("/oauth/")
        or path.startswith("/docs/user")
        or path.startswith("/docs/pdf/user")
        or path == "/api/models/catalog"
    )


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if NATIVE_SINGLE_USER and (
        request.url.path == "/login"
        or request.url.path == "/logout"
        or request.url.path.startswith(NATIVE_BLOCKED_PATH_PREFIXES)
        or (request.url.path.startswith("/api/projects/") and "/shares" in request.url.path)
    ):
        if request.url.path.startswith("/api/"):
            return HTMLResponse("Not available in native single-user mode", status_code=404)
        return RedirectResponse(url="/", status_code=303)

    user = session_user(request)
    model_bearer_ok = (
        request.method in {"GET", "HEAD"}
        and (
            request.url.path.startswith("/api/models/")
            or request.url.path.startswith("/api/mobile/demucs-coreml/")
            or request.url.path.startswith("/api/mobile/demucs-onnx/")
        )
        and model_access_token(request, "models:read") is not None
    )
    # Dedicated AI tokens authorize only the gateway; never grant full MTA session access.
    ai_gateway_token_ok = False
    if request.url.path.startswith('/api/ai-gateway/') or request.url.path.startswith('/api/ai-jobs'):
        from .ai_access import authenticate as authenticate_ai_token
        bearer = request.headers.get('authorization', '')
        ai_gateway_token_ok = bearer.lower().startswith('bearer ') and authenticate_ai_token(bearer[7:]) is not None
    if not _is_public(request.url.path) and user is None and not model_bearer_ok and not ai_gateway_token_ok and not check_basic_auth(request):
        if request.url.path.startswith("/api/"):
            return auth_failure_response()
        return RedirectResponse(url="/login", status_code=303)

    # API mutations must carry an explicit same-origin request marker.
    if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-mta-request") != "1" and not ai_gateway_token_ok:
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
    script_policy = "script-src 'self' 'unsafe-inline'"
    if NATIVE_SINGLE_USER:
        # pywebview 6.x creates js_api proxy methods with JavaScript's Function
        # constructor. WKWebView enforces CSP for that constructor, so the native
        # bridge stays present but empty unless unsafe-eval is enabled. Keep this
        # exception strictly limited to the loopback-only desktop application.
        script_policy += " 'unsafe-eval'"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        f"{script_policy}; media-src 'self' blob:; connect-src 'self'"
    )
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


def _template(name: str, **replacements) -> str:
    text = (BASE / "templates" / name).read_text(encoding="utf-8")
    text = text.replace("__VERSION__", APP_VERSION).replace("__REVISION__", APP_REVISION).replace("__BUILD__", BUILD_ID)
    for key, value in replacements.items():
        text = text.replace(f"__{key.upper()}__", str(value))
    return text


def _alert(message: str, ok: bool = False) -> str:
    if not message:
        return ""
    cls = "ok" if ok else "error"
    safe = (
        str(message).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f'<div class="alert {cls}">{safe}</div>'


def _actor(request: Request) -> dict:
    user = session_user(request)
    if user is not None:
        if int(user["id"]) == 0:
            return dict(user)
        return public_user(user)
    if check_basic_auth(request):
        return {
            "id": 0,
            "username": os.getenv("MTA_ADMIN_USERNAME", "admin"),
            "email": os.getenv("MTA_ADMIN_EMAIL", ""),
            "role": "admin",
            "active": True,
            "email_confirmed": True,
            "totp_enabled": False,
        }
    raise HTTPException(401, "Autenticazione richiesta.")


def _project_for_actor(request: Request, pid: str, *, owner_only: bool = False) -> Project:
    try:
        project = load_project(pid)
    except (OSError, ValueError):
        raise HTTPException(404, "project not found") from None
    actor = _actor(request)
    if project.owner_user_id is None and actor["id"] > 0:
        # One-time migration of pre-multi-user projects on first authenticated access.
        project.owner_user_id = actor["id"]
        save_project(project)
    if actor["id"] == 0 and actor["role"] == "admin":
        return project
    if not project_access(project, actor["id"], actor["role"], owner_only=owner_only):
        raise HTTPException(404, "project not found")
    return project


def _project_archive_name(project: Project) -> str:
    clean = SAFE_DOWNLOAD_RE.sub("_", project.title).strip(" ._")[:100] or "project"
    return f"{clean}-{project.id}.maeprojz"


def _social_buttons(mode: str) -> str:
    providers=oauth_public_providers()
    if not providers: return ""
    links="".join(f'<a class="social-login social-{p["id"]}" href="/oauth/{p["id"]}/start">Continua con {p["label"]}</a>' for p in providers)
    return f'<div class="social-auth"><div class="auth-divider"><span>oppure</span></div>{links}</div>'


@app.get("/oauth/{provider}/start")
def oauth_start(provider: str, request: Request):
    try: url,nonce=oauth_authorize_url(provider,request)
    except ValueError as exc: return HTMLResponse(_template("message.html",title="Login social non disponibile",message=str(exc),extra=""),status_code=400)
    response=RedirectResponse(url,status_code=303);secure=request.url.scheme=="https" or request.headers.get("x-forwarded-proto","").lower()=="https"
    response.set_cookie("mta_oauth_state",nonce,max_age=600,httponly=True,secure=secure,samesite="lax",path=f"/oauth/{provider}/callback")
    return response

@app.get("/oauth/{provider}/callback", response_class=HTMLResponse)
def oauth_callback(provider: str, request: Request, code: str="", state: str="", error: str=""):
    nonce=request.cookies.get("mta_oauth_state","")
    if error or not code or not oauth_verify_state(provider,state,nonce):
        return HTMLResponse(_template("message.html",title="Login social non riuscito",message="Richiesta OAuth annullata, scaduta o non valida.",extra=""),status_code=400)
    try:
        profile=oauth_exchange_profile(provider,code,request);user,created=social_login_or_register(provider,profile)
    except (ValueError,OSError) as exc:
        LOGGER.warning("OAuth callback failed for %s: %s",provider,exc)
        return HTMLResponse(_template("message.html",title="Login social non riuscito",message=str(exc),extra=""),status_code=400)
    if created or not user["active"]:
        response=HTMLResponse(_template("message.html",title="Registrazione completata",message="La registrazione è stata completata. Il tuo indirizzo email è stato verificato dal provider social, quindi non è richiesta una conferma email separata. Il profilo resta disabilitato finché un amministratore non lo approva; quando verrà approvato riceverai automaticamente un'email di conferma.",extra=""))
    else:
        token=create_session(user["id"],request);response=RedirectResponse("/",status_code=303);secure=request.url.scheme=="https" or request.headers.get("x-forwarded-proto","").lower()=="https";response.set_cookie("mta_session",token,max_age=12*3600,httponly=True,secure=secure,samesite="lax",path="/")
    response.delete_cookie("mta_oauth_state",path=f"/oauth/{provider}/callback");return response


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if session_user(request):
        return RedirectResponse("/", status_code=303)
    return _template("login.html", error="", social_buttons=_social_buttons("login"))


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request):
    form = await request.form()
    identifier = str(form.get("identifier", "")).strip()
    password = str(form.get("password", ""))
    totp = str(form.get("totp", "")).strip()
    user, error = authenticate(identifier, password, totp)
    if not user:
        return HTMLResponse(_template("login.html", error=_alert(error), social_buttons=_social_buttons("login")), status_code=401)
    token = create_session(user["id"], request)
    response = RedirectResponse("/", status_code=303)
    secure = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"
    response.set_cookie(
        "mta_session", token, max_age=12 * 3600, httponly=True, secure=secure,
        samesite="lax", path="/"
    )
    return response


@app.get("/logout")
def logout(request: Request):
    delete_session(request.cookies.get("mta_session"))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("mta_session", path="/")
    return response


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if session_user(request):
        return RedirectResponse("/", status_code=303)
    return _template("register.html", error="", social_buttons=_social_buttons("register"))


@app.post("/register", response_class=HTMLResponse)
async def register_submit(request: Request):
    form = await request.form()
    if str(form.get("password", "")) != str(form.get("password2", "")):
        return HTMLResponse(_template("register.html", error=_alert("Le password non coincidono."), social_buttons=_social_buttons("register")), status_code=400)
    try:
        user, token = register_user(
            str(form.get("username", "")),
            str(form.get("email", "")),
            str(form.get("display_name", "")),
            str(form.get("password", "")),
            base_url=str(request.base_url).rstrip("/"),
        )
    except ValueError as exc:
        return HTMLResponse(_template("register.html", error=_alert(str(exc)), social_buttons=_social_buttons("register")), status_code=400)
    extra = ""
    if os.getenv("MTA_DEV_EXPOSE_EMAIL_TOKENS", "").lower() in {"1","true","yes","on"}:
        extra = f'<p class="alert ok">DEV verification token: <code>{token}</code></p>'
    return HTMLResponse(_template(
        "message.html",
        title="Registrazione completata - approvazione richiesta",
        message=f"La registrazione è completata. Abbiamo inviato una mail di conferma a {user['email']}. La conferma dell'email non abilita automaticamente il profilo: l'account resterà disabilitato finché un amministratore non lo approverà. Dopo l'approvazione riceverai automaticamente una mail di conferma dell'abilitazione.",
        extra=extra,
    ))


@app.get("/verify-email", response_class=HTMLResponse)
def verify_email_page(token: str = ""):
    ok = bool(token) and confirm_email(token)
    return _template(
        "message.html",
        title="Email confermata" if ok else "Link non valido",
        message="La tua email è stata confermata. Il tuo account è ora in attesa di approvazione." if ok else "Il link è scaduto, non valido o già utilizzato.",
        extra="",
    )


@app.post("/resend-verification", response_class=HTMLResponse)
async def resend_verification_page(request: Request):
    form = await request.form()
    resend_verification(str(form.get("identifier", "")), base_url=str(request.base_url).rstrip("/"))
    return _template("message.html", title="Richiesta ricevuta", message="Se l'account esiste e non è ancora confermato, è stato inviato un nuovo messaggio.", extra="")



@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page():
    return _template("forgot-password.html", error="")


@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_submit(request: Request):
    form = await request.form()
    request_password_reset(str(form.get("identifier","")), str(request.base_url).rstrip("/"))
    return _template(
        "message.html",
        title="Richiesta ricevuta",
        message="Se l'account esiste ed ha un'email confermata, riceverai un link per reimpostare la password.",
        extra="",
    )


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(token: str = ""):
    return _template("reset-password.html", error="", token=token)


@app.post("/reset-password", response_class=HTMLResponse)
async def reset_password_submit(request: Request):
    form = await request.form()
    token = str(form.get("token",""))
    p1 = str(form.get("password",""))
    p2 = str(form.get("password2",""))
    if p1 != p2:
        return HTMLResponse(_template("reset-password.html", error=_alert("Le password non coincidono."), token=token), status_code=400)
    try:
        ok = reset_password(token,p1)
    except ValueError as exc:
        return HTMLResponse(_template("reset-password.html", error=_alert(str(exc)), token=token), status_code=400)
    if not ok:
        return HTMLResponse(_template("reset-password.html", error=_alert("Link non valido o scaduto."), token=token), status_code=400)
    return _template("message.html", title="Password aggiornata", message="Ora puoi accedere con la nuova password.", extra="")


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    # Browser navigation must never expose FastAPI's JSON 401 document as a white page.
    # API endpoints keep returning 401; interactive pages redirect to login.
    if not session_user(request):
        return RedirectResponse(url="/login?next=/account", status_code=303)
    return _template("account.html")


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    require_admin(request)
    return _template("admin.html")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    require_admin(request)
    return _template("admin.html")


@app.get("/api/session")
def api_session(request: Request):
    user = public_user(require_user(request))
    user["native_single_user"] = NATIVE_SINGLE_USER
    return user


@app.get("/api/account")
def api_account(request: Request):
    return public_user(require_user(request))


@app.patch("/api/account")
def api_account_update(request: Request, body: dict):
    user = require_user(request)
    try:
        updated, _ = update_profile(user["id"], display_name=body.get("display_name"), email=body.get("email"), base_url=str(request.base_url).rstrip("/"))
        if updated.get("pending_email"):
            from .auth import _smtp_full
            smtp = _smtp_full()
            updated["email_change_message"] = (
                "Nuova email in attesa di conferma; indirizzo precedente e accesso conservati."
                if smtp.get("host") and smtp.get("from_email") else
                "SMTP non configurato: modifica email in attesa, account ancora attivo. Configura SMTP per completare la verifica."
            )
        return updated
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/account/password")
def api_account_password(request: Request, body: dict):
    user = require_user(request)
    try:
        change_password(user["id"], str(body.get("current", "")), str(body.get("new_password", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    delete_session(request.cookies.get("mta_session"))
    return {"ok": True}


@app.post("/api/account/totp/begin")
def api_totp_begin(request: Request):
    user = require_user(request)
    secret, uri = begin_totp(user["id"])
    return {"secret": secret, "uri": uri}


@app.get("/api/account/totp/qr")
def api_totp_qr(request: Request):
    user = require_user(request)
    refreshed = get_user(user["id"])
    if not refreshed or not refreshed["totp_pending_enc"]:
        raise HTTPException(404, "Nessuna configurazione TOTP in corso.")
    return Response(totp_qr_svg(totp_uri(refreshed)), media_type="image/svg+xml")


@app.post("/api/account/totp/enable")
def api_totp_enable(request: Request, body: dict):
    user = require_user(request)
    try:
        enable_totp(user["id"], str(body.get("code", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/account/totp/disable")
def api_totp_disable(request: Request, body: dict):
    user = require_user(request)
    try:
        disable_totp(user["id"], str(body.get("password", "")), str(body.get("code", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


def _tree_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for item in path.rglob("*"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total

def _workspace_usage_for_user(user_id: int) -> int:
    total = 0
    for project in list_projects():
        if project.owner_user_id == user_id:
            total += _tree_size(pdir(project.id))
    return total

def _storage_payload(request: Request) -> dict:
    actor = _actor(request)
    disk = shutil.disk_usage(STORAGE_ROOT)
    model_usage = demucs_model_storage_usage()
    users = list_users()
    if actor["role"] != "admin":
        users = [u for u in users if u["id"] == actor["id"]]
    workspaces=[]
    for user in users:
        used=_workspace_usage_for_user(user["id"])
        quota=int(user.get("workspace_quota_bytes") or 0)
        workspaces.append({
            "user_id":user["id"],"username":user["username"],"display_name":user.get("display_name") or "",
            "used_bytes":used,"quota_bytes":quota,"remaining_bytes":max(0,quota-used) if quota else None,
            "percent":round((used/quota)*100,1) if quota else None,
        })
    return {
        "disk":{"total_bytes":disk.total,"used_bytes":disk.used,"free_bytes":disk.free},
        "models":model_usage,"workspaces":workspaces,"max_upload_bytes":MAX_UPLOAD_BYTES,
        "data_dir":str(STORAGE_ROOT),"version":APP_VERSION,"build":BUILD_ID,
    }

def _ensure_workspace_capacity(owner_user_id: int | None, additional_bytes: int) -> None:
    if not owner_user_id or owner_user_id <= 0 or additional_bytes <= 0:
        return
    row=get_user(owner_user_id)
    if not row:
        return
    quota=int(row["workspace_quota_bytes"] or 0)
    if not quota:
        return
    used=_workspace_usage_for_user(owner_user_id)
    if used + additional_bytes > quota:
        raise HTTPException(413, f"Quota workspace superata: {used} byte usati su {quota} byte disponibili.")

@app.get("/api/storage")
def api_storage(request: Request):
    require_user(request)
    return _storage_payload(request)


@app.post("/api/storage/shared/rescan")
def api_storage_shared_rescan(request: Request, delete_unreferenced: bool = True):
    require_admin(request)
    return rescan_shared_media(delete_unreferenced=delete_unreferenced)


# Opt-in support bundle endpoints. API access requires an authenticated administrator.
from . import diagnostic_bundle as _mta_diagnostics


@app.get("/api/admin/diagnostics/settings")
def admin_diagnostics_settings(request: Request):
    require_admin(request)
    return {"enabled": _mta_diagnostics.enabled(), "retention_hours": 24,
            "scope": "redacted structured diagnostics; no project data or raw journals"}


@app.put("/api/admin/diagnostics/settings")
def admin_diagnostics_update(request: Request, body: dict):
    require_admin(request)
    try:
        return {"enabled": _mta_diagnostics.configure(body.get("enabled"))}
    except (ValueError, PermissionError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/admin/diagnostics/bundles")
def admin_diagnostics_create(request: Request):
    require_admin(request)
    if not _mta_diagnostics.enabled():
        raise HTTPException(403, "Diagnostics disabled; enable MTA_DIAGNOSTICS_ENABLED in server settings")
    try:
        # Never expose model prompts, user inputs, artifacts, or secret environment.
        recent = ai_arranger_runtime.list_jobs(50)
        compact = [{"id": j.get("job_id"), "operation": j.get("operation"),
                    "state": j.get("state"), "phase": j.get("phase"),
                    "progress_percent": j.get("progress_percent"),
                    "cpu_seconds": j.get("cpu_seconds"), "gpu_seconds": j.get("gpu_seconds")}
                   for j in recent]
        report = {"ai_queue": {"max_concurrent_jobs": ai_arranger_runtime._limit(),
                                "jobs": compact},
                  "runtime": {"pid": os.getpid(), "python": __import__("platform").python_version(),
                              "os": __import__("platform").system()},
                  "components": {"ace_step_url_configured": bool(os.environ.get("MTA_ACE_STEP_URL")),
                                 "ai_worker_enabled": os.environ.get("MTA_AI_WORKER_ENABLED", "false").lower() == "true"}}
        path = _mta_diagnostics.create(report)
    except Exception:
        LOGGER.exception("Unable to create sanitized diagnostics")
        raise HTTPException(500, "Diagnostic bundle creation failed")
    return {"name": path.name, "url": "/api/admin/diagnostics/bundles/" + path.name,
            "expires_in_seconds": _mta_diagnostics.RETENTION}


@app.get("/api/admin/diagnostics/bundles/{name}")
def admin_diagnostics_download(name: str, request: Request):
    require_admin(request)
    if not _mta_diagnostics.enabled():
        raise HTTPException(403, "Diagnostics disabled")
    try:
        path = _mta_diagnostics.resolve(name)
    except FileNotFoundError:
        raise HTTPException(404, "Bundle not found or expired")
    return FileResponse(path, media_type="application/zip", filename=name,
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@app.get("/api/admin/web-settings")
def api_admin_web_settings(request: Request):
    require_admin(request)
    return _storage_payload(request)

@app.get("/api/admin/users")
def api_admin_users(request: Request):
    require_admin(request)
    return list_users()


@app.patch("/api/admin/users/{user_id}")
def api_admin_user_update(user_id: int, request: Request, body: dict):
    actor = require_admin(request)
    try:
        return update_user_admin(user_id, actor["id"], active=body.get("active"), role=body.get("role"), workspace_quota_bytes=body.get("workspace_quota_bytes"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.delete("/api/admin/users/{user_id}")
def api_admin_user_delete(user_id: int, request: Request):
    actor = require_admin(request)
    try:
        delete_user_admin(user_id, actor["id"])
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.get("/api/admin/smtp")
def api_admin_smtp(request: Request):
    require_admin(request)
    return get_smtp_config()


@app.put("/api/admin/smtp")
def api_admin_smtp_save(request: Request, body: dict):
    require_admin(request)
    try:
        return save_smtp_config(body)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/admin/smtp/test")
def api_admin_smtp_test(request: Request, body: dict):
    require_admin(request)
    try:
        test_smtp_config(body)
    except Exception as exc:
        raise HTTPException(400, f"Connessione SMTP fallita: {exc}") from exc
    return {"ok": True}


@app.get("/api/admin/projects-dump")
def api_admin_projects_dump(request: Request):
    require_admin(request)
    tmp = Path(tempfile.mkstemp(prefix="mta-all-projects-", suffix=".zip")[1])
    users = {u["id"]: u for u in list_users()}
    manifest = {
        "schema": "mta-audio-editor/all-projects-dump/v1",
        "version": APP_VERSION,
        "revision": APP_REVISION,
        "release": APP_RELEASE,
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "users": [
            {"id": u["id"], "username": u["username"], "email": u["email"], "role": u["role"]}
            for u in users.values()
        ],
    }
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.writestr("dump-manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
            for project in list_projects():
                owner = users.get(project.owner_user_id)
                owner_label = f"{project.owner_user_id}-{owner['username']}" if owner else f"{project.owner_user_id or 'legacy'}-unknown"
                project_label = f"{project.id}-{SAFE_DOWNLOAD_RE.sub('_',project.title)[:80]}"
                base = pdir(project.id)
                prefix = Path("users") / owner_label / "projects" / project_label
                for path in sorted(base.rglob("*")):
                    if path.is_file() and path.name != "project.json.tmp":
                        z.write(path, prefix / path.relative_to(base))
        return FileResponse(
            tmp,
            media_type="application/zip",
            filename=f"mta-audio-editor-all-projects-{APP_RELEASE}.zip",
            background=BackgroundTask(lambda: tmp.unlink(missing_ok=True)),
        )
    except Exception:
        tmp.unlink(missing_ok=True)
        raise



@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return (
        (BASE / "templates" / "index.html")
        .read_text(encoding="utf-8")
        .replace("__VERSION__", APP_VERSION)
        .replace("__REVISION__", APP_REVISION)
        .replace("__BUILD__", BUILD_ID)
        .replace("__BODY_CLASS__", "native-single-user" if NATIVE_SINGLE_USER else "")
    )


def _render_doc(name: str) -> str:
    return (
        (BASE / "docs" / name)
        .read_text(encoding="utf-8")
        .replace("__VERSION__", APP_VERSION)
        .replace("__REVISION__", APP_REVISION)
        .replace("__BUILD__", BUILD_ID)
        .replace("__CREATOR__", CREATOR)
        .replace("__REPOSITORY__", REPOSITORY)
    )


@app.get("/docs/user", response_class=HTMLResponse)
def user_docs():
    return _render_doc("user.html")


@app.get("/docs/admin", response_class=HTMLResponse)
def admin_docs(request: Request):
    user = session_user(request)
    if user is not None and user["role"] != "admin":
        raise HTTPException(403, "Ruolo amministratore richiesto.")
    return _render_doc("admin.html")


@app.get("/docs/user/en", response_class=HTMLResponse)
def user_docs_en():
    return _render_doc("user-en.html")


@app.get("/docs/admin/en", response_class=HTMLResponse)
def admin_docs_en(request: Request):
    user = session_user(request)
    if user is not None and user["role"] != "admin":
        raise HTTPException(403, "Administrator role required.")
    return _render_doc("admin-en.html")


@app.get("/docs/pdf/user")
def user_pdf():
    return FileResponse(BASE / "docs" / "MTA-Audio-Editor-User-Manual-IT.pdf", filename="MTA-Audio-Editor-User-Manual-IT.pdf")


@app.get("/docs/pdf/admin")
def admin_pdf(request: Request):
    user = session_user(request)
    if user is not None and user["role"] != "admin":
        raise HTTPException(403, "Ruolo amministratore richiesto.")
    return FileResponse(
        BASE / "docs" / "MTA-Audio-Editor-Administrator-Manual-IT.pdf",
        filename="MTA-Audio-Editor-Administrator-Manual-IT.pdf",
    )


@app.get("/docs/pdf/user/en")
def user_pdf_en():
    return FileResponse(BASE / "docs" / "MTA-Audio-Editor-User-Manual-EN.pdf", filename="MTA-Audio-Editor-User-Manual-EN.pdf")


@app.get("/docs/pdf/admin/en")
def admin_pdf_en(request: Request):
    user = session_user(request)
    if user is not None and user["role"] != "admin":
        raise HTTPException(403, "Administrator role required.")
    return FileResponse(
        BASE / "docs" / "MTA-Audio-Editor-Administrator-Manual-EN.pdf",
        filename="MTA-Audio-Editor-Administrator-Manual-EN.pdf",
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "version": APP_VERSION, "revision": APP_REVISION, "build": BUILD_ID}


@app.get("/api/about")
def about():
    return {
        "name": "MTA Audio Editor",
        "version": APP_VERSION,
        "revision": APP_REVISION,
        "release": APP_RELEASE,
        "release_channel": APP_RELEASE_CHANNEL,
        "build": BUILD_ID,
        "creator": CREATOR,
        "repository": REPOSITORY,
        "license": "EUPL-1.2",
        "native_single_user": NATIVE_SINGLE_USER,
    }




@app.get("/api/vst3/plugins")
def vst3_plugin_list(request: Request):
    from .vst3_host import discover_plugins, runtime_available
    # Only the locally installed desktop host can access external plugin binaries.
    if not NATIVE_SINGLE_USER:
        return {"available": False, "plugins": [], "reason": "Desktop application required"}
    return {"available": runtime_available(), "plugins": discover_plugins()}


@app.get("/api/vst3/parameters")
def vst3_parameters(request: Request, path: str):
    import subprocess
    import sys
    import json
    from .vst3_host import validate_plugin_path, runtime_available
    if not NATIVE_SINGLE_USER or not runtime_available():
        raise HTTPException(status_code=403, detail="Desktop VST3 host required")
    try:
        plugin = validate_plugin_path(path)
        proc = subprocess.run([sys.executable, '-m', 'app.vst3_host', '--inspect-plugin', str(plugin)],
                              capture_output=True, text=True, timeout=15)
        if proc.returncode:
            raise ValueError(proc.stderr[-500:] or 'VST3 inspection failed')
        return json.loads(proc.stdout)
    except (ValueError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/plugins")
def plugins():
    manifest = plugin_manifest()
    return {
        "inserts": manifest["presets"],
        "schemas": manifest["schemas"],
        "custom": manifest["custom"],
        "factory_params": manifest["factory_params"],
        "notes": manifest["notes"],
        "stem_splitter": {**STEM_SPLITTER.status(), "lead_backing": _lead_backing_catalog()},
        "text_models": ai_catalog(native=NATIVE_SINGLE_USER),
    }


@app.post("/api/presets")
def create_custom_preset(req: CustomPresetRequest):
    try:
        params = save_user_preset(req.plugin, req.name, req.params)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"plugin": req.plugin, "name": req.name, "preset": f"user:{req.name}", "params": params}


@app.delete("/api/presets/{plugin}/{name}")
def remove_custom_preset(plugin: str, name: str):
    if plugin not in plugin_manifest()["presets"]:
        raise HTTPException(404, "plugin not found")
    if not delete_user_preset(plugin, name):
        raise HTTPException(404, "user preset not found")
    return {"ok": True}




@app.get('/api/ai-arranger/model-cache')
def ai_arranger_model_cache(request: Request):
    # Remote applications use MTA's authenticated API; the raw model server
    # remains on loopback or a private container network.
    _actor(request)
    from .ace_model_cache import cache_status
    return cache_status()


@app.get('/api/ai-arranger/worker-status')
def ai_arranger_worker_status(request: Request):
    _actor(request)
    return worker_capabilities()


@app.get('/api/ai-arranger/catalog')
def ai_arranger_catalog(request: Request):
    _actor(request)
    return arranger_catalog()


@app.post('/api/projects/{pid}/ai-arranger/preflight')
def ai_arranger_preflight(pid: str, request: Request, body: RearrangeRequest):
    project = _project_for_actor(request, pid)
    try:
        return assess_plan(arranger_plan(project, body))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/api/projects/{pid}/remix/preflight')
def ai_remix_preflight(pid: str, request: Request, body: RemixRequest):
    project = _project_for_actor(request, pid)
    try:
        return assess_plan(prepare_remix_plan(project, body))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/api/projects/{pid}/ai-arranger/plan')
def ai_arranger_project_plan(pid: str, request: Request, body: RearrangeRequest):
    project = _project_for_actor(request, pid)
    try:
        return arranger_plan(project, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/projects/{pid}/remix/plan')
def ai_remix_project_plan(pid: str, request: Request, body: RemixRequest):
    project = _project_for_actor(request, pid)
    try:
        return prepare_remix_plan(project, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/projects/{pid}/ai-arranger/jobs')
def create_ai_arranger_job(pid: str, request: Request, body: RearrangeRequest):
    project = _project_for_actor(request, pid)
    try:
        plan = arranger_plan(project, body)
        return ai_jobs.submit(pid, str(_actor(request)['id']), 'rearrange', plan)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/api/projects/{pid}/remix/jobs')
def create_ai_remix_job(pid: str, request: Request, body: RemixRequest):
    project = _project_for_actor(request, pid)
    try:
        plan = prepare_remix_plan(project, body)
        return ai_jobs.submit(pid, str(_actor(request)['id']), 'remix', plan)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/projects/{pid}/ai-jobs')
def list_ai_planning_jobs(pid: str, request: Request, limit: int = 20,
                          offset: int = 0, status: str | None = None):
    _project_for_actor(request, pid)
    try:
        return ai_jobs.list(pid, str(_actor(request)['id']), limit=limit,
                            offset=offset, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get('/api/projects/{pid}/ai-jobs/{job_id}')
def get_ai_job(pid: str, job_id: str, request: Request):
    _project_for_actor(request, pid)
    result = ai_jobs.get(job_id, pid, str(_actor(request)['id']))
    if result is None:
        raise HTTPException(404, 'AI job not found')
    return result


@app.post('/api/projects/{pid}/ai-jobs/{job_id}/cancel')
def cancel_ai_job(pid: str, job_id: str, request: Request):
    _project_for_actor(request, pid)
    result = ai_jobs.cancel(job_id, pid, str(_actor(request)['id']))
    if result is None:
        raise HTTPException(404, 'AI job not found')
    return result


def _generate_ai_preview(plan: dict, project: Project) -> Response:
    """Explicit opt-in external worker output; never mutate the original project."""
    if configured_worker() is None:
        raise HTTPException(503, 'No verified AI inference executable is configured')
    try:
        audio, meta = run_worker_with_project_audio(plan, project, audio_path)
    except WorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(422, f'AI preview validation failed: {exc}') from exc
    return Response(content=audio, media_type='audio/wav', headers={
        'X-MTA-AI-Sample-Rate': str(meta['sample_rate']),
        'X-MTA-AI-Channels': str(meta['channels']),
        'Cache-Control': 'no-store',
        'Content-Disposition': 'attachment; filename="ai-preview.wav"',
    })


@app.post('/api/projects/{pid}/ai-arranger/generate')
def ai_arranger_generate(pid: str, request: Request, body: RearrangeRequest):
    project = _project_for_actor(request, pid)
    try:
        plan = arranger_plan(project, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _generate_ai_preview(plan, project)


@app.post('/api/projects/{pid}/remix/generate')
def ai_remix_generate(pid: str, request: Request, body: RemixRequest):
    project = _project_for_actor(request, pid)
    try:
        plan = prepare_remix_plan(project, body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return _generate_ai_preview(plan, project)


def _publish_durable_generated_audio(job_id, pid, audio, metadata):
    """Serialize *all* generated tracks targeting one project across processes.

    Per-job outbox locks are insufficient: two independent jobs can otherwise
    read the same project snapshot and overwrite one another's new track.
    """
    import hashlib
    from .ai_project_lock import project_publication_lock
    with project_publication_lock(pid):
        # Load only after acquiring the project lock to avoid stale snapshots.
        project = load_project(pid)
        filename = 'ai-' + job_id + '.wav'
        already = next((track for track in project.tracks if track.filename == filename), None)
        target = audio_path(pid, filename)
        expected_hash = hashlib.sha256(audio).hexdigest()
        if already:
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash:
                raise RuntimeError('Existing AI publication differs from staged audio')
            return project
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash:
            raise RuntimeError('Existing AI output conflicts with staged audio')
        return _append_ai_generated_track(project, audio, metadata['wav'],
            mode=metadata['mode'], input_source=metadata['input_source'], job_id=job_id,
            allow_matching_existing=True)


def _recover_audio_publications():
    from . import ai_publish_outbox
    published = ai_publish_outbox.recover(_publish_durable_generated_audio)
    from . import ai_finalization
    for receipt in ai_publish_outbox.published_jobs():
        try:
            ai_finalization.reconcile(receipt)
        except Exception:
            logging.getLogger(__name__).exception('AI finalization recovery remains pending for job %s', receipt)
    return published


def _append_ai_generated_track(project: Project, audio: bytes, meta: dict, *, mode: str, input_source: str, job_id: str | None = None, allow_matching_existing: bool = False) -> Project:
    """Append a generated result, preserving every existing track and source file.

    Only successful, validated worker output is published.  A new independent
    filename and source-clip library entry are used; never replace the input.
    """
    from io import BytesIO
    import wave as _wave
    with _wave.open(BytesIO(audio), 'rb') as handle:
        frames = handle.getnframes()
        sample_rate = handle.getframerate()
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        if (frames <= 0 or sample_rate <= 0 or channels <= 0 or
                sample_width not in (1, 2, 3, 4) or
                frames != meta['frames'] or sample_rate != meta['sample_rate'] or
                channels != meta['channels']):
            raise ValueError('AI output WAV metadata mismatch')
        # wave.open checks the header, not whether a truncated data chunk
        # actually contains the samples advertised by that header. Never
        # persist a generated track with a partial PCM payload.
        pcm = handle.readframes(frames)
        if len(pcm) != frames * channels * sample_width:
            raise ValueError('AI output WAV is truncated')
    filename = 'ai-' + (job_id if job_id is not None else uuid.uuid4().hex) + '.wav'
    target = audio_path(project.id, filename)
    # A completed publication cannot be repeated by a replay or stale callback.
    existing_file = target.exists()
    if target.is_symlink():
        raise RuntimeError('Unsafe existing AI output')
    if job_id is not None and (any(t.filename == filename for t in project.tracks) or
        (existing_file and not allow_matching_existing)):
        raise RuntimeError('AI result has already been published for this job')
    if existing_file and (not allow_matching_existing or hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(audio).digest()):
        raise RuntimeError('AI generated WAV conflicts with staged bytes')
    if target.is_symlink() or (existing_file and not target.is_file()):
        raise RuntimeError('Unsafe existing AI output')
    target.parent.mkdir(parents=True, exist_ok=True)
    # Every attempt owns a distinct staging pathname; an interrupted older
    # attempt must never be overwritten or removed by this one.
    temp = target.parent / ('.' + filename + '.' + uuid.uuid4().hex + '.pending')
    duration = round(meta['frames'] * 1000 / meta['sample_rate'])
    name = ('AI Remix' if mode == 'remix' else 'AI Arrangement') + (' · Master' if input_source == 'master' else ' · Track')
    track = Track(id=uuid.uuid4().hex[:12], name=name, filename=filename,
                  duration_ms=duration, sample_rate=meta['sample_rate'],
                  channels=meta['channels'],
                  clips=[Clip(id=uuid.uuid4().hex[:12], source_start_ms=0,
                              source_end_ms=duration, timeline_start_ms=0)])
    old_tracks = list(project.tracks)
    old_library = list(project.clip_library)
    published_identity = None
    try:
        if not existing_file:
            with temp.open('xb') as handle:
                handle.write(audio)
                handle.flush()
                os.fsync(handle.fileno())
            if target.exists() or target.is_symlink():
                raise RuntimeError('AI output appeared before publication')
            os.replace(temp, target)
            published_identity = (target.stat().st_dev, target.stat().st_ino)
            from .storage import _fsync_directory
            _fsync_directory(target.parent)
        project.tracks.append(track)
        _register_track_source_in_library(project, track, 'AI generated audio; original tracks preserved')
        save_project(project)
        return project
    except Exception:
        # save_project can raise *after* its atomic JSON replacement. A replay
        # must preserve media already referenced by that durable project.
        committed = False
        if published_identity is not None:
            try:
                persisted = load_project(project.id)
                committed = any(t.filename == filename for t in persisted.tracks)
            except FileNotFoundError:
                committed = False
            except (OSError, ValueError):
                # Unknown persistence state: preserve media for reconciliation.
                committed = True
        if not committed:
            project.tracks = old_tracks
            project.clip_library = old_library
            if published_identity is not None:
                try:
                    identity = (target.stat(follow_symlinks=False).st_dev,
                                target.stat(follow_symlinks=False).st_ino)
                    if identity == published_identity and not target.is_symlink():
                        target.unlink()
                except FileNotFoundError:
                    pass
        raise
    finally:
        temp.unlink(missing_ok=True)


@app.get('/api/admin/ai-execution/jobs')
def admin_ai_execution_jobs(request: Request):
    require_admin(request)
    return {'jobs': ai_arranger_runtime.list_jobs(), 'max_concurrent_jobs': ai_arranger_runtime._limit(), 'scope': 'shared-ai-admission'}


@app.get('/api/admin/ai-execution/settings')
def admin_ai_execution_settings(request: Request):
    require_admin(request)
    return {'max_concurrent_jobs': ai_arranger_runtime._limit(), 'scope': 'shared-ai-admission'}


@app.put('/api/admin/ai-execution/settings')
def admin_ai_execution_settings_update(request: Request, body: dict):
    require_admin(request)
    try:
        value = ai_arranger_runtime.configure(body['max_concurrent_jobs'])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, 'max_concurrent_jobs must be an integer from 1 to 32') from exc
    return {'max_concurrent_jobs': value, 'note': 'Setting stored in the AI queue SQLite database'}


@app.post('/api/admin/ai-execution/jobs/{job_id}/cancel')
def admin_ai_execution_cancel(job_id: str, request: Request):
    require_admin(request)
    try:
        job = ai_arranger_runtime.cancel(job_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if job is None:
        raise HTTPException(404, 'AI job not found')
    return job


@app.post('/api/admin/ai-execution/jobs/{job_id}/move')
def admin_ai_execution_move(job_id: str, request: Request, body: dict):
    require_admin(request)
    try:
        return ai_arranger_runtime.move(job_id, body['position'])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


def _durable_generation_executor(pid, payload, job_id):
    """Rebuild a queued Arranger/Remix request without capturing HTTP state."""
    if not isinstance(payload, dict) or payload.get('schema_version') != 1:
        raise ValueError('Unsupported persisted generation payload')
    operation = payload.get('adapter')
    if operation == 'arranger':
        body = RearrangeRequest.model_validate(payload['request'])
    elif operation == 'remix':
        body = RemixRequest.model_validate(payload['request'])
    else:
        raise ValueError('Unsupported persistent AI adapter')

    def generate(progress_file, cancel_event):
        project = load_project(pid)
        plan = arranger_plan(project, body) if operation == 'arranger' else prepare_remix_plan(project, body)
        from . import ai_durable_remote_executor
        if ai_durable_remote_executor.configured_remote() is not None:
            audio, meta = ai_durable_remote_executor.execute(
                job_id, plan, project, audio_path, cancel_event=cancel_event)
        else:
            audio, meta = run_worker_with_project_audio(plan, project, audio_path,
                progress_file=progress_file, cancel_event=cancel_event)
        if cancel_event.is_set():
            raise RuntimeError('Cancelled before publishing generated track')
        # Persist trusted direct-child CPU evidence *before* the publication
        # side effect. If accounting is enabled but complete evidence is not
        # available, the terminal gate remains fail-closed.
        usage = meta.pop('_trusted_worker_usage', None)
        source = meta.pop('_trusted_worker_source', None)
        if usage is not None:
            from . import ai_metering_bridge
            if source not in ('worker', 'cgroup'):
                raise ValueError('Trusted worker usage has no verified source')
            ai_metering_bridge.capture(job_id, usage, source)
        # Stable filename provides a publish-once guard for idempotent submissions.
        from . import ai_publish_outbox
        ai_publish_outbox.stage(job_id, pid, audio, {
            'wav': meta, 'mode': operation, 'input_source': plan['input_source']})
        ai_publish_outbox.recover(_publish_durable_generated_audio, job_id=job_id)
    return generate


ai_arranger_runtime.register_restorer('arranger', _durable_generation_executor)
ai_arranger_runtime.register_restorer('remix', _durable_generation_executor)


@app.on_event('startup')
def _restore_persisted_ai_queue():
    try:
        # Finish already-generated audio before admitting another inference.
        publications = _recover_audio_publications()
        LOGGER.info('Recovered %d pending AI audio publications', publications)
        # Resume only settlements explicitly bound to existing billing jobs.
        # Failed delivery must not prevent inference recovery.
        try:
            from . import ai_billing_outbox
            settled = ai_billing_outbox.deliver()
            LOGGER.info('Recovered %d pending AI billing settlements', settled)
        except Exception:
            LOGGER.exception('AI billing settlement delivery remains pending')
        # Reconcile admissions abandoned between scheduler and ledger commits.
        from . import ai_billing
        import json as _json
        with ai_arranger_runtime._db() as con:
            admission_rows = con.execute("SELECT job_id,operation,payload_json FROM jobs WHERE state IN ('queued','blocked') AND operation IN ('arranger','remix') AND payload_json IS NOT NULL").fetchall()
        for admission in admission_rows:
            try:
                saved = _json.loads(admission['payload_json'])
                uid = saved.get('actor_user_id')
                if type(uid) is int and uid > 0:
                    ai_billing.provision_inference_job(admission['job_id'], uid, admission['operation'])
                with ai_arranger_runtime._db() as con:
                    con.execute("UPDATE jobs SET state='queued',phase='queued',message='Admission reconciled' WHERE job_id=? AND state='blocked' AND message='Ledger admission needs reconciliation'", (admission['job_id'],))
            except Exception:
                LOGGER.exception('Deferred ledger admission for %s', admission['job_id'])
                with ai_arranger_runtime._db() as con:
                    con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Ledger admission needs reconciliation' WHERE job_id=? AND state IN ('queued','blocked')", (admission['job_id'],))
        count = ai_arranger_runtime.recover_queued()
        LOGGER.info('Recovered %d queued AI jobs from persistent storage', count)
    except (OSError, ValueError):
        LOGGER.exception('Could not restore queued AI jobs')


@app.get('/api/projects/{pid}/ai-arranger/active-generation')
def ai_arranger_active_generation(pid: str, request: Request):
    _project_for_actor(request, pid)
    return ai_arranger_runtime.inspect(pid)


@app.post('/api/projects/{pid}/ai-arranger/start-generation', status_code=202)
def ai_arranger_start_generation(pid: str, request: Request, body: RearrangeRequest):
    _project_for_actor(request, pid)
    if configured_worker() is None:
        raise HTTPException(503, 'No trusted AI inference executable is configured')
    # Persist the caller's reproducible request separately from the execution closure.
    # Idempotency keys are namespaced per project and operation.
    import hashlib
    replay_header = request.headers.get('Idempotency-Key')
    if replay_header is not None and not (1 <= len(replay_header) <= 128 and replay_header.isascii()):
        raise HTTPException(422, 'Invalid Idempotency-Key header')
    replay_key = hashlib.sha256(f'{pid}:arranger:{replay_header}'.encode()).hexdigest() if replay_header else None
    payload = {'request': body.model_dump(mode='json'), 'adapter': 'arranger', 'schema_version': 1, 'actor_user_id': int(_actor(request)['id'])}
    job_id = uuid.uuid4().hex
    executor = _durable_generation_executor(pid, payload, job_id)
    try:
        accepted, job = ai_arranger_runtime.start(pid, 'arranger', executor, job_id=job_id,
            cancellable=True, payload=payload, idempotency_key=replay_key, defer_spawn=True)
    except ValueError as exc:
        # Reusing a key for different parameters is a client conflict, not an
        # unhandled internal error. The original durable job is unchanged.
        raise HTTPException(409, str(exc)) from exc
    if accepted:
        try:
            from . import ai_billing
            uid = payload['actor_user_id']
            if uid > 0:
                ai_billing.provision_inference_job(job_id, uid, 'arranger')
        except Exception:
            LOGGER.exception('Ledger admission pending for AI job %s', job_id)
            with ai_arranger_runtime._db() as con:
                con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Ledger admission needs reconciliation' WHERE job_id=? AND state='queued'", (job_id,))
            return ai_arranger_runtime.get(job_id)
        ai_arranger_runtime.activate(job_id, executor)
        job = ai_arranger_runtime.get(job_id)
    # A matching idempotency key returns the original job, without a new run.
    return job


@app.post('/api/projects/{pid}/remix/start-generation', status_code=202)
def ai_remix_start_generation(pid: str, request: Request, body: RemixRequest):
    _project_for_actor(request, pid)
    if configured_worker() is None:
        raise HTTPException(503, 'No trusted AI inference executable is configured')
    import hashlib
    replay_header = request.headers.get('Idempotency-Key')
    if replay_header is not None and not (1 <= len(replay_header) <= 128 and replay_header.isascii()):
        raise HTTPException(422, 'Invalid Idempotency-Key header')
    replay_key = hashlib.sha256(f'{pid}:remix:{replay_header}'.encode()).hexdigest() if replay_header else None
    payload = {'request': body.model_dump(mode='json'), 'adapter': 'remix', 'schema_version': 1, 'actor_user_id': int(_actor(request)['id'])}
    job_id = uuid.uuid4().hex
    executor = _durable_generation_executor(pid, payload, job_id)
    try:
        accepted, job = ai_arranger_runtime.start(pid, 'remix', executor, job_id=job_id,
            cancellable=True, payload=payload, idempotency_key=replay_key, defer_spawn=True)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if accepted:
        try:
            from . import ai_billing
            uid = payload['actor_user_id']
            if uid > 0:
                ai_billing.provision_inference_job(job_id, uid, 'remix')
        except Exception:
            LOGGER.exception('Ledger admission pending for AI job %s', job_id)
            with ai_arranger_runtime._db() as con:
                con.execute("UPDATE jobs SET state='blocked',phase='blocked',message='Ledger admission needs reconciliation' WHERE job_id=? AND state='queued'", (job_id,))
            return ai_arranger_runtime.get(job_id)
        ai_arranger_runtime.activate(job_id, executor)
        job = ai_arranger_runtime.get(job_id)
    # A matching idempotency key returns the original job, without a new run.
    return job


@app.post('/api/projects/{pid}/ai-arranger/generate-and-add')
def ai_arranger_generate_and_add(pid: str, request: Request, body: RearrangeRequest):
    project = _project_for_actor(request, pid)
    try:
        plan = arranger_plan(project, body)
        audio, meta = run_worker_with_project_audio(plan, project, audio_path)
        return _append_ai_generated_track(project, audio, meta, mode='arranger',
                                          input_source=plan['input_source'])
    except WorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post('/api/projects/{pid}/remix/generate-and-add')
def ai_remix_generate_and_add(pid: str, request: Request, body: RemixRequest):
    project = _project_for_actor(request, pid)
    try:
        plan = prepare_remix_plan(project, body)
        audio, meta = run_worker_with_project_audio(plan, project, audio_path)
        return _append_ai_generated_track(project, audio, meta, mode='remix',
                                          input_source=plan['input_source'])
    except WorkerUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/projects")
def projects(request: Request):
    actor = _actor(request)
    # Legacy pre-multi-user projects are claimed once by the first persistent
    # administrator that opens the workspace after upgrade.
    if actor["id"] > 0 and actor["role"] == "admin":
        from .ai_project_lock import project_publication_lock
        for legacy in list_projects():
            if legacy.owner_user_id is None:
                with project_publication_lock(legacy.id):
                    # A different writer may have claimed the project while we
                    # waited for the cross-process lock; never steal ownership.
                    current = load_project(legacy.id)
                    if current.owner_user_id is None:
                        current.owner_user_id = actor["id"]
                        save_project(current)
    # Even administrators get their own workspace here; cross-user administration
    # is exposed explicitly through the dump/admin APIs.
    return list_projects(actor["id"] if actor["id"] > 0 else None, include_shared=True, is_admin=False)


@app.post("/api/projects")
def project_new(request: Request, title: str = "Untitled", target: str = "MTA8", sample_rate: int = 44100, audio_storage_mode: str = "wav"):
    actor = _actor(request)
    owner = actor["id"] if actor["id"] > 0 else None
    rate = int(sample_rate) if int(sample_rate) in {44100, 48000, 96000} else 44100
    return create_project(title, target if target in {"MTA8", "MTA16", "DAW"} else "MTA8", owner_user_id=owner, sample_rate=rate, audio_storage_mode=audio_storage_mode)


def _refresh_project_clip_metadata(project: Project, asset: ProjectClip, *, force: bool = False) -> bool:
    """Persist technical/library metadata without exposing host absolute paths."""
    if asset.metadata_scanned and not force:
        return False
    changed = False
    source = audio_path(project.id, asset.filename)
    location = f"audio/{asset.filename}"
    if asset.current_location != location:
        asset.current_location = location
        changed = True
    if not source.is_file():
        return changed
    try:
        info = ffprobe(source)
        stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "audio"), {})
        fmt = info.get("format") or {}
        codec = str(stream.get("codec_name") or "").strip()
        container = str(fmt.get("format_name") or source.suffix.lstrip(".")).strip()
        display_format = " / ".join(part for part in (codec.upper() if codec else "", container) if part)[:160]
        bitrate = 0
        try:
            sample_rate = int(stream.get("sample_rate") or 0)
        except (TypeError, ValueError):
            sample_rate = 0
        for value in (stream.get("bit_rate"), fmt.get("bit_rate")):
            try:
                bitrate = max(bitrate, int(float(value or 0)))
            except (TypeError, ValueError):
                pass
        tags: dict[str, str] = {}
        for scope, values in (("format", fmt.get("tags") or {}), ("audio", stream.get("tags") or {})):
            for key, value in values.items():
                label = f"{scope}.{str(key)[:80]}"
                tags[label] = str(value)[:500]
                if len(tags) >= 64:
                    break
            if len(tags) >= 64:
                break
        size = source.stat().st_size
        updates = {
            "format": display_format,
            "bitrate_bps": bitrate,
            "sample_rate": sample_rate if sample_rate in {44100, 48000, 96000} else 44100,
            "size_bytes": size,
            "embedded_metadata": tags,
            "metadata_scanned": True,
        }
        for key, value in updates.items():
            if getattr(asset, key) != value:
                setattr(asset, key, value)
                changed = True
    except Exception as exc:
        # Keep the browser usable even if an old/temporarily unavailable asset cannot be probed.
        LOGGER.warning("Clip metadata probe failed for %s: %s", source, exc)
    return changed


def _ensure_project_clip_library(project: Project) -> bool:
    """Backfill reusable project audio assets, metadata and stable track-to-asset IDs."""
    changed = False
    by_id = {item.id: item for item in project.clip_library}
    by_filename = {item.filename: item for item in project.clip_library}
    for track in project.tracks:
        asset = by_id.get(track.source_clip_id or "")
        if asset is None:
            asset = by_filename.get(track.filename)
        if asset is None:
            asset = ProjectClip(
                id=uuid.uuid4().hex[:12],
                name=track.name[:200],
                filename=track.filename,
                duration_ms=track.duration_ms,
                type=track.type,
                channels=track.channels,
                channel_layout=track.channel_layout,
            )
            project.clip_library.append(asset)
            by_id[asset.id] = asset
            by_filename[asset.filename] = asset
            changed = True
        if track.source_clip_id != asset.id:
            track.source_clip_id = asset.id
            changed = True
    for asset in project.clip_library:
        if _refresh_project_clip_metadata(project, asset):
            changed = True
    return changed


def _register_track_source_in_library(project: Project, track: Track, provenance: str | None = None) -> ProjectClip:
    existing = next((item for item in project.clip_library if item.id == track.source_clip_id), None)
    if existing is None:
        existing = next((item for item in project.clip_library if item.filename == track.filename), None)
    if existing is not None:
        track.source_clip_id = existing.id
        if provenance and (not existing.provenance or existing.provenance == "Audio del progetto"):
            existing.provenance = provenance[:500]
        _refresh_project_clip_metadata(project, existing)
        return existing
    asset = ProjectClip(
        id=uuid.uuid4().hex[:12],
        name=track.name[:200],
        filename=track.filename,
        duration_ms=track.duration_ms,
        type=track.type,
        channels=track.channels,
        channel_layout=track.channel_layout,
        provenance=(provenance or "Audio del progetto")[:500],
        current_location=f"audio/{track.filename}",
    )
    project.clip_library.append(asset)
    track.source_clip_id = asset.id
    _refresh_project_clip_metadata(project, asset)
    return asset


def _serialized_project_mutation(handler):
    """Serialize read/modify/write routes with AI publication and track import.

    Attach below the FastAPI route decorator to preserve endpoint introspection.
    Acquire before project loading, never inside another project lock.
    """
    from functools import wraps
    import inspect

    if inspect.iscoroutinefunction(handler):
        @wraps(handler)
        async def guarded(pid, *args, **kwargs):
            from .ai_project_lock import project_publication_lock
            with project_publication_lock(pid):
                return await handler(pid, *args, **kwargs)
    else:
        @wraps(handler)
        def guarded(pid, *args, **kwargs):
            from .ai_project_lock import project_publication_lock
            with project_publication_lock(pid):
                return handler(pid, *args, **kwargs)
    return guarded


@app.post("/api/projects/{pid}/migrate-flac")
@_serialized_project_mutation
def project_migrate_flac(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    if project.audio_storage_mode == "flac":
        return {"ok": True, "project": project, "converted": 0, "skipped": []}
    try:
        result = migrate_project_audio_to_flac(project)
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise HTTPException(400, f"Migrazione FLAC non riuscita: {exc}") from exc
    return {"ok": True, "project": project, **result}


@app.get("/api/projects/{pid}")
@_serialized_project_mutation
def project_get(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    # Opening a project is also a safe maintenance boundary: project.json is
    # authoritative, so stale local audio can be removed before the editor uses it.
    maintain_project_storage(pid)
    changed = _ensure_project_clip_library(project)
    if project.base_bpm is None:
        project.base_bpm = project.bpm
        changed = True
    for track in project.tracks:
        ensure_clips(track)
        if track.channels == 0:
            source = audio_path(pid, track.filename)
            if source.exists():
                track.channels, track.channel_layout = _audio_channel_info(source)
                changed = True
    if changed:
        save_project(project)
    return project


@app.put("/api/projects/{pid}")
@_serialized_project_mutation
def project_put(pid: str, project: Project, request: Request):
    current = _project_for_actor(request, pid)
    if pid != project.id:
        raise HTTPException(400, "project id mismatch")
    if int(project.sample_rate) != int(current.sample_rate) and current.tracks:
        raise HTTPException(409, "Il sample rate del progetto può essere modificato solo quando non ci sono tracce attive")
    project.audio_storage_mode = current.audio_storage_mode
    # Ownership/shares and reusable audio assets are managed conservatively.
    project.owner_user_id = current.owner_user_id
    project.shared_with_user_ids = current.shared_with_user_ids
    _ensure_project_clip_library(current)
    known_clip_files = {item.filename for item in project.clip_library}
    for item in current.clip_library:
        if item.filename not in known_clip_files:
            project.clip_library.append(item)
            known_clip_files.add(item.filename)
    _ensure_project_clip_library(project)
    try:
        validate_project_files(project)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    save_project(project)
    return project


@app.delete("/api/projects/{pid}")
@_serialized_project_mutation
def project_delete(pid: str, request: Request):
    _project_for_actor(request, pid, owner_only=True)
    try:
        delete_project(pid)
    except ValueError as exc:
        raise HTTPException(400, "invalid project id") from exc
    return {"ok": True}


@app.get("/api/projects/{pid}/shares")
def project_shares(pid: str, request: Request):
    project = _project_for_actor(request, pid, owner_only=True)
    result = []
    for user_id in project.shared_with_user_ids:
        row = get_user(user_id)
        if row:
            result.append({
                "id": row["id"], "username": row["username"], "display_name": row["display_name"],
                "email": row["email"],
            })
    return result


@app.post("/api/projects/{pid}/shares")
@_serialized_project_mutation
def project_share_add(pid: str, request: Request, body: dict):
    project = _project_for_actor(request, pid, owner_only=True)
    actor = _actor(request)
    row = find_user(str(body.get("identifier", "")))
    if not row or not row["active"] or not row["email_confirmed"]:
        raise HTTPException(404, "Utente attivo e confermato non trovato.")
    if row["id"] == project.owner_user_id:
        raise HTTPException(400, "Il proprietario ha già accesso al progetto.")
    if row["id"] == actor["id"]:
        raise HTTPException(400, "Non puoi condividere il progetto con te stesso.")
    if row["id"] not in project.shared_with_user_ids:
        project.shared_with_user_ids.append(row["id"])
        save_project(project)
    return {"ok": True, "user": {"id": row["id"], "username": row["username"], "email": row["email"]}}


@app.delete("/api/projects/{pid}/shares/{user_id}")
@_serialized_project_mutation
def project_share_remove(pid: str, user_id: int, request: Request):
    project = _project_for_actor(request, pid, owner_only=True)
    project.shared_with_user_ids = [x for x in project.shared_with_user_ids if x != user_id]
    save_project(project)
    return {"ok": True}


@app.get("/api/projects/{pid}/files")
def project_file_list(pid: str, request: Request):
    _project_for_actor(request, pid)
    return project_files(pid)


@app.post("/api/projects/{pid}/files/upload")
async def project_file_upload(pid: str, request: Request, file: UploadFile = File(...)):
    project=_project_for_actor(request, pid)
    _ensure_workspace_capacity(project.owner_user_id, int(request.headers.get("content-length") or 0))
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "upload.bin"
        _copy_limited(file.file, src)
        existing = find_duplicate_project_file(pid, src)
        dst = preserve_original(pid, src, Path(file.filename or "upload.bin").name)
    return {
        "ok": True,
        "category": "original",
        "name": dst.name,
        "size": dst.stat().st_size,
        "duplicate": bool(existing),
    }


@app.get("/api/projects/{pid}/files/{category}/{filename}")
def project_file_download(pid: str, category: str, filename: str, request: Request):
    _project_for_actor(request, pid)
    try:
        path = file_path(pid, category, filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(path, filename=path.name)


@app.delete("/api/projects/{pid}/files/{category}/{filename}")
def project_file_delete(pid: str, category: str, filename: str, request: Request):
    _project_for_actor(request, pid)
    try:
        delete_project_file(pid, category, filename)
    except FileNotFoundError:
        raise HTTPException(404, "file not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}



@app.post("/api/projects/{pid}/files/batch-delete")
def project_files_batch_delete(pid: str, request: Request, body: list[dict]):
    _project_for_actor(request, pid)
    if not body:
        raise HTTPException(400, "Nessun file selezionato.")
    deleted: list[dict] = []
    errors: list[dict] = []
    for item in body:
        category = str(item.get("category", ""))
        filename = str(item.get("name", ""))
        try:
            delete_project_file(pid, category, filename)
            deleted.append({"category": category, "name": filename})
        except (FileNotFoundError, ValueError) as exc:
            errors.append({"category": category, "name": filename, "error": str(exc)})
    if errors:
        return {"ok": False, "deleted": deleted, "errors": errors}
    return {"ok": True, "deleted": deleted, "errors": []}


@app.get("/api/projects/{pid}/archive")
def project_archive_export(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    tmp = Path(tempfile.mkstemp(prefix=f"mta-project-{pid}-", suffix=".maeproj")[1])
    try:
        write_project_archive(pid, tmp)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return FileResponse(
        tmp,
        media_type="application/vnd.mta-audio-editor.project",
        filename=_project_archive_name(project),
        background=BackgroundTask(lambda: tmp.unlink(missing_ok=True)),
    )


@app.post("/api/project-archives/import")
async def project_archive_import(request: Request, file: UploadFile = File(...)):
    actor = _actor(request)
    _ensure_workspace_capacity(actor["id"] if actor["id"] > 0 else None, int(request.headers.get("content-length") or 0))
    if actor["id"] <= 0 and not NATIVE_SINGLE_USER:
        raise HTTPException(400, "L'import completo richiede un account utente persistente.")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "project.maeproj"
        _copy_limited(file.file, src)
        try:
            return import_project_archive(src, actor["id"] if actor["id"] > 0 else None)
        except (ValueError, zipfile.BadZipFile) as exc:
            raise HTTPException(400, f"Archivio progetto non valido: {exc}") from exc


@app.get("/api/projects/{pid}/audio/{filename}")
def project_audio(pid: str, filename: str, request: Request):
    _project_for_actor(request, pid)
    try:
        path = audio_path(pid, filename)
    except ValueError as exc:
        raise HTTPException(400, "invalid audio path") from exc
    if not path.exists():
        raise HTTPException(404, "audio not found")
    return FileResponse(path)




@app.get("/api/projects/{pid}/tracks/{track_id}/sample-editor")
def sample_editor_info(pid: str, track_id: str, request: Request):
    project = _project_for_actor(request, pid)
    track = next((x for x in project.tracks if x.id == track_id), None)
    if track is None:
        raise HTTPException(404, "traccia non trovata")
    src = sample_editor_engine.rendered_source(pid, track)
    rate = sample_editor_engine.sample_rate(src)
    duration = media_duration_ms(src)
    return {"track_id": track.id, "name": track.name, "sample_rate": rate, "duration_ms": duration,
            "total_samples": round(duration / 1000 * rate),
            "audio_url": f"/api/projects/{pid}/tracks/{track_id}/sample-editor/audio",
            "eq_bands": sample_editor_engine.EQ_BANDS, "presets": sample_editor_engine.PRESETS}


@app.get("/api/projects/{pid}/tracks/{track_id}/sample-editor/audio")
def sample_editor_audio(pid: str, track_id: str, request: Request):
    project = _project_for_actor(request, pid)
    track = next((x for x in project.tracks if x.id == track_id), None)
    if track is None:
        raise HTTPException(404, "traccia non trovata")
    src = sample_editor_engine.rendered_source(pid, track)
    return FileResponse(src, media_type="audio/wav", filename=f"{track.name}-sample-editor.wav")


@app.post("/api/projects/{pid}/tracks/{track_id}/sample-editor/edit")
@_serialized_project_mutation
def sample_editor_edit(pid: str, track_id: str, req: SampleEditRequest, request: Request):
    project = _project_for_actor(request, pid)
    track = next((x for x in project.tracks if x.id == track_id), None)
    if track is None:
        raise HTTPException(404, "traccia non trovata")
    try:
        result = sample_editor_engine.edit(project, track, req)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    if req.action == "copy":
        return {"ok": True, **result}
    _register_track_source_in_library(project, track, "Sample editor commit")
    save_project(project)
    return {"ok": True, "project": project, "track": track}


@app.post("/api/projects/{pid}/tracks/{track_id}/sample-editor/effect-preview")
def sample_editor_effect_preview(pid: str, track_id: str, req: SampleEffectRequest, request: Request):
    project = _project_for_actor(request, pid)
    track = next((x for x in project.tracks if x.id == track_id), None)
    if track is None:
        raise HTTPException(404, "traccia non trovata")
    try:
        out = sample_editor_engine.apply_effect(project, track, req, True)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return FileResponse(out, media_type="audio/mpeg", filename="sample-effect-preview.mp3", background=BackgroundTask(lambda: out.unlink(missing_ok=True)))


@app.post("/api/projects/{pid}/tracks/{track_id}/sample-editor/effect-apply")
@_serialized_project_mutation
def sample_editor_effect_apply(pid: str, track_id: str, req: SampleEffectRequest, request: Request):
    project = _project_for_actor(request, pid)
    track = next((x for x in project.tracks if x.id == track_id), None)
    if track is None:
        raise HTTPException(404, "traccia non trovata")
    try:
        out = sample_editor_engine.apply_effect(project, track, req, False)
        sample_editor_engine.commit(project, track, out)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    _register_track_source_in_library(project, track, "Sample editor effect")
    save_project(project)
    return {"ok": True, "project": project, "track": track}

def _copy_limited(src, dst: Path):
    """Copy within the upload limit without ever deleting an existing destination.

    An exclusive-create failure must not unlink the existing file. For a new
    file, flush both contents and directory entry before returning success.
    """
    total = 0
    owned_identity = None
    try:
        with dst.open("xb") as out:
            st = os.fstat(out.fileno())
            owned_identity = (st.st_dev, st.st_ino)
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "upload exceeds configured limit")
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        folder_fd = os.open(str(dst.parent), os.O_RDONLY)
        try:
            os.fsync(folder_fd)
        finally:
            os.close(folder_fd)
    except BaseException:
        if owned_identity is not None:
            try:
                st = dst.lstat()
                if stat.S_ISREG(st.st_mode) and (st.st_dev, st.st_ino) == owned_identity:
                    dst.unlink()
            except FileNotFoundError:
                pass
        raise


def _audio_sample_rate(path: Path) -> int:
    info = ffprobe(path)
    stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "audio"), {})
    try:
        return int(stream.get("sample_rate") or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_audio_to_project_rate(pid: str, filename: str, project_rate: int, *, strict: bool = True) -> tuple[str, Path, int]:
    source = audio_path(pid, filename)
    source_rate = _audio_sample_rate(source)
    if source_rate not in {44100, 48000, 96000}:
        if not strict:
            return filename, source, int(project_rate) if int(project_rate) in {44100, 48000, 96000} else 44100
        raise ValueError(f"sample rate audio non supportato: {source_rate or 'sconosciuto'} Hz; usa 44.1, 48 o 96 kHz")
    target_rate = int(project_rate) if int(project_rate) in {44100, 48000, 96000} else 44100
    if source_rate == target_rate:
        return filename, source, source_rate
    converted_name = f"{Path(filename).stem}-sr{target_rate}.wav"
    converted = audio_path(pid, converted_name)
    tmp = converted.with_name(f".{converted.name}.{uuid.uuid4().hex}.tmp.wav")
    try:
        proc = subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-i", str(source), "-map", "0:a:0",
            "-ar", str(target_rate), "-c:a", "pcm_s24le", str(tmp),
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if proc.returncode or not tmp.is_file():
        tmp.unlink(missing_ok=True)
        raise ValueError(proc.stderr.strip() or "conversione sample rate fallita")
    # Never replace another import's completed destination, even if a
    # filename collision or a stale conversion path exists.
    try:
        os.link(tmp, converted)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.unlink(missing_ok=True)
    source.unlink(missing_ok=True)
    return converted_name, converted, source_rate


def _save_upload(pid: str, file: UploadFile, project_rate: int | None = None):
    """Stage upload safely; roll back media and new originals on failed processing.

    Callers continue to own the final project-commit rollback.  This helper
    guarantees cleanup for errors occurring *before* it returns a media path.
    """
    ext = Path(file.filename or "track.wav").suffix.lower() or ".bin"
    if len(ext) > 12 or not ext.replace(".", "").isalnum():
        raise HTTPException(400, "invalid file extension")
    filename = f"{uuid.uuid4().hex[:10]}{ext}"
    dst = audio_path(pid, filename)
    # Capture the identities of pre-existing destinations.  A failed
    # exclusive conversion must never turn into an unlink of another upload.
    owned_original = None
    target_rate = int(project_rate) if project_rate is not None and int(project_rate) in {44100, 48000, 96000} else None
    owned_audio = {}
    try:
        _copy_limited(file.file, dst)
        owned_audio[filename] = (dst.stat().st_dev, dst.stat().st_ino)
        from .ai_media_identity import record_upload
        record_upload(pid, dst)
        try:
            ffprobe(dst)
        except Exception as exc:
            raise HTTPException(400, "invalid or unsupported audio file") from exc
        duplicate = find_duplicate_project_file(pid, dst)
        if duplicate:
            raise HTTPException(409, f"Il file è già presente nel progetto come {duplicate['category']}/{duplicate['name']}.")
        original_before = {(p.stat().st_dev, p.stat().st_ino) for p in originals_dir(pid).iterdir()
                           if p.is_file() and not p.is_symlink()}
        copied_original = preserve_original(pid, dst, Path(file.filename or filename).name)
        if isinstance(copied_original, Path) and copied_original.is_file() and not copied_original.is_symlink():
            st = copied_original.stat()
            if (st.st_dev, st.st_ino) not in original_before:
                owned_original = (copied_original, st.st_dev, st.st_ino)
                record_upload(pid, copied_original)
        if project_rate is None:
            project_rate = int(load_project(pid).sample_rate)
        target_rate = int(project_rate) if int(project_rate) in {44100, 48000, 96000} else 44100
        converted_name = f"{Path(filename).stem}-sr{target_rate}.wav"
        converted_path = audio_path(pid, converted_name)
        # Do not claim a collision destination: _normalize_audio_to_project_rate
        # uses an exclusive hard link and raises if it already exists.
        converted_before = ((converted_path.stat().st_dev, converted_path.stat().st_ino)
                            if converted_path.exists() else None)
        try:
            filename, dst, _ = _normalize_audio_to_project_rate(pid, filename, project_rate)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if filename == converted_name and converted_before is None:
            owned_audio[filename] = (dst.stat().st_dev, dst.stat().st_ino)
            record_upload(pid, dst)
        duration = media_duration_ms(dst)
        return filename, dst, duration
    except BaseException:
        for name, identity in owned_audio.items():
            path = audio_path(pid, name)
            try:
                st = path.lstat()
                if not stat.S_ISLNK(st.st_mode) and (st.st_dev, st.st_ino) == identity:
                    path.unlink()
            except FileNotFoundError:
                pass
        # Only delete the exact original created by this operation.  Never
        # sweep names observed since the initial snapshot: another writer may
        # have produced them in the meantime.
        if owned_original is not None:
            item, device, inode = owned_original
            try:
                st = item.lstat()
                if stat.S_ISREG(st.st_mode) and (st.st_dev, st.st_ino) == (device, inode):
                    item.unlink()
            except FileNotFoundError:
                pass
        raise



def _rollback_unpublished_upload(pid, path, identity):
    """Delete only our inode, and only when persisted state proves it unreferenced.

    A save may raise after atomic replace (e.g. directory fsync failure). Never
    infer rollback safety from the exception alone. Caller holds project lock.
    """
    try:
        persisted = load_project(pid)
        referenced = {t.filename for t in persisted.tracks} | {c.filename for c in persisted.clip_library}
    except Exception:
        # An unreadable authoritative project is not permission to delete media.
        return
    if path.name in referenced:
        return
    try:
        st = path.lstat()
        if stat.S_ISREG(st.st_mode) and (st.st_dev, st.st_ino) == identity:
            path.unlink()
    except FileNotFoundError:
        pass


def _waveform_revision(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"


def _track_waveform_revision(track: Track, source: Path) -> str:
    """Revision of the audible track output waveform, including insert state/config."""
    payload = {
        "source": _waveform_revision(source),
        "waveform_format": "signed-minmax-v2-4096",
        "inserts": [item.model_dump(mode="json") for item in track.inserts],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:24]


def _audio_channel_info(path: Path) -> tuple[int, str]:
    try:
        info = ffprobe(path)
        stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "audio"), None)
        if not stream:
            return 0, ""
        channels = int(stream.get("channels") or 0)
        layout = str(stream.get("channel_layout") or "").strip()
        if not layout:
            layout = "stereo" if channels == 2 else ("mono" if channels == 1 else "")
        return channels, layout
    except Exception:
        return 0, ""


def _waveform_worker(job_id: str, pid: str, track_id: str) -> None:
    try:
        project = load_project(pid)
        track = next((item for item in project.tracks if item.id == track_id), None)
        if track is None:
            raise ValueError("track not found")
        source = audio_path(pid, track.filename)

        def progress(value: int, message: str) -> None:
            _media_job_update(job_id, progress=max(1, min(99, int(value))), message=message)

        enabled_inserts = any(item.enabled for item in track.inserts)
        if enabled_inserts:
            with tempfile.TemporaryDirectory(prefix="mta-waveform-") as td_raw:
                rendered = Path(td_raw) / "processed.wav"
                progress(10, "Rendering insert per waveform")
                render_track(track, source, rendered, apply_inserts=True)
                peaks = waveform_peaks(rendered, 4096, progress)
        else:
            peaks = waveform_peaks(source, 4096, progress)
        from .ai_project_lock import project_publication_lock
        source_revision = _track_waveform_revision(track, source)
        with project_publication_lock(pid):
            latest = load_project(pid)
            latest_track = next((item for item in latest.tracks if item.id == track_id), None)
            if latest_track is None:
                raise ValueError("track removed while waveform was updating")
            if _track_waveform_revision(latest_track, source) != source_revision:
                raise ValueError("Track changed while waveform was updating; retry")
            latest_track.waveform_peaks = peaks
            latest_track.waveform_revision = source_revision
            save_project(latest)
        _media_job_update(
            job_id,
            status="completed",
            progress=100,
            message="Waveform aggiornata",
            result={"track_id": track_id, "peaks": peaks, "revision": latest_track.waveform_revision},
        )
    except Exception as exc:
        _media_job_update(job_id, status="failed", progress=0, message="Aggiornamento waveform fallito", error=str(exc)[-1200:])


@app.post("/api/projects/{pid}/tracks/{track_id}/waveform-jobs")
def start_waveform_job(pid: str, track_id: str, request: Request, force: bool = False):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if track is None:
        raise HTTPException(404, "track not found")
    source = audio_path(pid, track.filename)
    revision = _track_waveform_revision(track, source)
    if not force and track.waveform_peaks and track.waveform_revision == revision:
        return {
            "id": "",
            "kind": "waveform",
            "project_id": pid,
            "status": "completed",
            "progress": 100,
            "message": "Waveform già aggiornata",
            "created_at": time.time(),
            "updated_at": time.time(),
            "result": {"track_id": track_id, "peaks": track.waveform_peaks, "revision": revision},
            "error": None,
        }

    with MEDIA_JOB_LOCK:
        for item in MEDIA_JOBS.values():
            if (
                item.get("kind") == "waveform"
                and item.get("project_id") == pid
                and item.get("track_id") == track_id
                and item.get("status") not in {"completed", "failed", "cancelled"}
            ):
                return _media_job_public(item)

    now = time.time()
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "kind": "waveform",
        "project_id": pid,
        "track_id": track_id,
        "status": "queued",
        "progress": 2,
        "message": "Waveform in coda",
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    threading.Thread(target=_waveform_worker, args=(job_id, pid, track_id), daemon=True, name=f"waveform-{job_id}").start()
    return _media_job_public(job)


def _track_import_worker(
    job_id: str,
    pid: str,
    filename: str,
    original_name: str,
    name: str,
    track_type: str,
    offset_ms: int,
    sync_mode: str,
    reference_track_id: str,
    estimate_first_bpm: bool,
    provenance: str = "Import audio",
) -> None:
    dst = audio_path(pid, filename)
    committed = False
    upload_identity = None
    try:
        _media_job_update(job_id, status="running", progress=58, message="Validazione della traccia")
        st = dst.lstat()
        upload_identity = (st.st_dev, st.st_ino)
        ffprobe(dst)
        project = load_project(pid)
        filename, dst, _ = _normalize_audio_to_project_rate(pid, filename, project.sample_rate)
        st = dst.lstat()
        upload_identity = (st.st_dev, st.st_ino)
        duration = media_duration_ms(dst)
        channels, channel_layout = _audio_channel_info(dst)
        estimated_tempo = None
        if estimate_first_bpm and not project.tracks:
            def bpm_progress(value: int, message: str) -> None:
                _media_job_update(job_id, progress=60 + int(max(0, min(100, value)) * 0.28), message=message)
            try:
                bpm, signature = estimate_bpm_and_signature(dst, bpm_progress)
                estimated_tempo = (float(round(bpm)), signature)
            except Exception:
                _media_job_update(job_id, progress=87, message="Stima BPM non conclusiva; mantengo il BPM corrente")
        _media_job_update(job_id, progress=88, message="Generazione waveform")
        try:
            peaks = waveform_peaks(dst, 4096, lambda value, message: _media_job_update(
                job_id, progress=88 + int(max(0, min(100, value)) * 0.07), message=message
            ))
        except Exception:
            peaks = []
        allowed = Track.model_fields["type"].annotation.__args__
        track = Track(
            id=uuid.uuid4().hex[:10],
            name=(name or Path(original_name).stem)[:200],
            type=track_type if track_type in allowed else "other",
            filename=filename,
            duration_ms=duration,
            clips=[Clip(
                id=uuid.uuid4().hex[:10],
                source_start_ms=0,
                source_end_ms=duration,
                timeline_start_ms=max(0, offset_ms),
            )],
            waveform_peaks=peaks,
            waveform_revision="",
            channels=channels,
            channel_layout=channel_layout,
            sample_rate=int(project.sample_rate),
        )
        track.waveform_revision = _track_waveform_revision(track, dst) if peaks else ""
        _media_job_update(job_id, progress=91, message="Aggiunta della traccia al progetto")
        # All expensive decoding / waveform / BPM work finishes before this lock.
        # Load the current project *inside* the lock to avoid lost updates from
        # concurrent editor requests, imports and AI publishers.
        from .ai_project_lock import project_publication_lock
        with project_publication_lock(pid):
            latest = load_project(pid)
            from .ai_media_identity import record
            from .ai_async_track_transaction import _receipt
            record(_receipt(pid, job_id), dst)
            if int(latest.sample_rate) != int(project.sample_rate):
                raise ValueError("Project sample rate changed during import; retry")
            if any(item.filename == filename for item in latest.tracks):
                raise ValueError("Track has already been imported")
            if estimated_tempo is not None and not latest.tracks:
                latest.bpm, latest.time_signature = estimated_tempo
                latest.base_bpm = latest.bpm
            if sync_mode == "auto" and latest.tracks:
                ref = next((item for item in latest.tracks if item.id == reference_track_id), latest.tracks[0])
                shift_track(track, auto_align_ms(audio_path(pid, ref.filename), dst))
            latest.tracks.append(track)
            _register_track_source_in_library(latest, track, provenance)
            save_project(latest)
            committed = True
            project = latest
        _media_job_update(
            job_id,
            status="completed",
            progress=100,
            message="Import completato",
            result={"project_id": pid, "track_id": track.id, "bpm": project.bpm},
        )
    except Exception as exc:
        if not committed:
            if upload_identity is not None:
                from .ai_project_lock import project_publication_lock
                with project_publication_lock(pid):
                    _rollback_unpublished_upload(pid, dst, upload_identity)
        _media_job_update(job_id, status="failed", progress=0, message="Import fallito", error=str(exc)[-1200:])
    finally:
        try:
            from .ai_async_track_transaction import reconcile as finish_async_track
            from .ai_project_lock import project_publication_lock
            with project_publication_lock(pid):
                finish_async_track(pid, job_id)
        except Exception:
            LOGGER.exception('Async track receipt could not be finalized for %s', job_id)


@app.post("/api/projects/{pid}/track-import-jobs")
async def start_track_import_job(
    pid: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = "",
    type: str = "other",
    offset_ms: int = 0,
    sync_mode: str = "manual",
    reference_track_id: str = "",
):
    if sync_mode not in {"manual", "auto"}:
        raise HTTPException(400, "invalid sync mode")
    project = _project_for_actor(request, pid)
    _ensure_workspace_capacity(project.owner_user_id, int(request.headers.get("content-length") or 0))
    ext = Path(file.filename or "track.wav").suffix.lower() or ".bin"
    if len(ext) > 12 or not ext.replace(".", "").isalnum():
        raise HTTPException(400, "invalid file extension")
    filename = f"{uuid.uuid4().hex[:10]}{ext}"
    job_id = uuid.uuid4().hex[:16]
    from .ai_async_track_transaction import begin as begin_async_track, reconcile as finish_async_track
    from .ai_project_lock import project_publication_lock
    with project_publication_lock(pid):
        begin_async_track(pid, job_id, filename)
    dst = audio_path(pid, filename)
    try:
        _copy_limited(file.file, dst)
        from .ai_media_identity import record
        from .ai_async_track_transaction import _receipt
        with project_publication_lock(pid):
            record(_receipt(pid, job_id), dst)
        duplicate = find_duplicate_project_file(pid, dst)
    except Exception:
        with project_publication_lock(pid):
            finish_async_track(pid, job_id)
        raise
    if duplicate:
        with project_publication_lock(pid):
            finish_async_track(pid, job_id)
        raise HTTPException(
            409,
            f"Il file è già presente nel progetto come {duplicate['category']}/{duplicate['name']}.",
        )
    try:
        from .ai_async_track_transaction import preserve_job_original
        with project_publication_lock(pid):
            preserve_job_original(pid, job_id, dst, Path(file.filename or filename).name)
    except Exception:
        with project_publication_lock(pid):
            finish_async_track(pid, job_id)
        raise
    now = time.time()
    first_track = len(project.tracks) == 0 and ext == ".mp3"
    job = {
        "id": job_id,
        "kind": "track-import",
        "project_id": pid,
        "status": "queued",
        "progress": 55,
        "message": "Upload completato",
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    try:
        threading.Thread(
            target=_track_import_worker,
            args=(job_id, pid, filename, Path(file.filename or filename).name, name, type, offset_ms, sync_mode, reference_track_id, first_track),
            daemon=True,
            name=f"track-import-{job_id}",
        ).start()
    except Exception as exc:
        with project_publication_lock(pid):
            finish_async_track(pid, job_id)
        _media_job_update(job_id, status="failed", progress=0, message="Import fallito", error=str(exc)[-1200:])
        raise HTTPException(503, "track import worker could not start") from exc
    return _media_job_public(job)



def _shift_timed_events(events, offset_ms: int):
    shifted=[]
    for event in events:
        payload=event.model_dump()
        payload["time_ms"]=int(payload.get("time_ms") or 0)+int(offset_ms)
        if payload.get("end_ms") is not None:
            payload["end_ms"]=int(payload["end_ms"])+int(offset_ms)
        for word in payload.get("words") or []:
            word["start_ms"]=int(word.get("start_ms") or 0)+int(offset_ms)
            word["end_ms"]=int(word.get("end_ms") or 0)+int(offset_ms)
            for syllable in word.get("syllables") or []:
                syllable["start_ms"]=int(syllable.get("start_ms") or 0)+int(offset_ms)
                syllable["end_ms"]=int(syllable.get("end_ms") or 0)+int(offset_ms)
        shifted.append(type(event)(**payload))
    return shifted


def _replace_timed_range(existing, replacement, start_ms: int, end_ms: int):
    kept=[item for item in (existing or []) if not (int(start_ms) <= int(getattr(item,"time_ms",0) or 0) < int(end_ms))]
    return sorted([*kept, *replacement], key=lambda item:int(getattr(item,"time_ms",0) or 0))


def _native_remote_infer(kind: str, source: Path, options: dict | None = None):
    """Convert project audio to WAV only for explicit remote inference."""
    from . import native_ai_routing
    with tempfile.TemporaryDirectory(prefix='mta-native-ai-upload-') as td:
        wav = Path(td) / 'input.wav'
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(source),'-acodec','pcm_s16le',wav.as_posix()],check=True)
        return native_ai_routing.infer(kind, wav, options)


def _text_music_worker(job_id: str, pid: str, track_id: str, kind: str, model_or_engine: str = "", advanced_alignment: bool = False, chord_options: dict | None = None, range_start_ms: int | None = None, range_end_ms: int | None = None) -> None:
    range_tmp = None
    try:
        from .ai_project_lock import project_publication_lock
        project = load_project(pid)
        track = next((item for item in project.tracks if item.id == track_id), None)
        if track is None:
            raise ValueError("track not found")
        source = audio_path(pid, track.filename)
        range_mode = range_start_ms is not None and range_end_ms is not None and int(range_end_ms) > int(range_start_ms)
        if range_mode and kind in {"lyrics", "chords"}:
            _media_job_update(job_id, status="running", progress=2, message="Preparazione intervallo selezionato")
            tmp_dir = Path(tempfile.mkdtemp(prefix=f"mta-{kind}-range-"))
            rendered = tmp_dir / "track.wav"
            clipped = tmp_dir / "range.wav"
            render_track(track, source, rendered, apply_inserts=True, sample_rate=int(getattr(project,"sample_rate",44100) or 44100))
            start_s=max(0,int(range_start_ms))/1000.0
            duration_s=max(0.001,(int(range_end_ms)-int(range_start_ms))/1000.0)
            subprocess.run(["ffmpeg","-y","-v","error","-ss",f"{start_s:.6f}","-t",f"{duration_s:.6f}","-i",str(rendered),"-vn","-acodec","pcm_s16le",str(clipped)],check=True)
            source = clipped
            range_tmp = tmp_dir
        _media_job_update(job_id, status="running", progress=3, message="Preparazione analisi e verifica sorgente")
        if kind == "lyrics":
            selected_model=model_or_engine or lyrics_catalog(native=NATIVE_SINGLE_USER)["default_model"]
            _media_job_update(job_id, progress=5, message=f"Verifica modello lyrics · OpenAI Whisper · {selected_model}")
            cancel_event=MEDIA_JOBS[job_id].get("cancel_event")
            def lyrics_progress(pct, items, message):
                # Do not expose incremental transcript text while Whisper is running:
                # it may encourage chunk stitching artefacts (repeated/missing phrases).
                _media_job_update(job_id,progress=pct,message=message,partial={"kind":"lyrics","items":[]})
            from . import native_ai_routing as _native_ai
            if NATIVE_SINGLE_USER and _native_ai.is_remote('whisper'):
                payload, remote_id = _native_remote_infer('whisper', source, {'model':selected_model,'advanced_alignment':advanced_alignment})
                from .models import LyricLine
                doc = payload['json'].get('transcript.json')
                if not isinstance(doc, dict) or not isinstance(doc.get('lines'), list):
                    raise ValueError('Remote Whisper response missing transcript.json/lines')
                events = [LyricLine.model_validate(item) for item in doc['lines']]
                _media_job_update(job_id, remote_job_id=remote_id, progress=90, message='Remote Whisper completed')
            elif getattr(extract_lyrics,"__module__","") != "app.music_text":
                try: events=extract_lyrics(source,model_name=selected_model)
                except TypeError: events=extract_lyrics(source)
                lyrics_progress(90,events,"Trascrizione lyrics completa")
            else:
                events=extract_lyrics_progressive(
                    source,model_name=selected_model,progress=lyrics_progress,
                    cancelled=(lambda: bool(cancel_event and cancel_event.is_set())),
                    advanced_alignment=advanced_alignment,
                )
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Lyrics extraction cancelled")
            _media_job_update(job_id, progress=96, message="Sincronizzazione lyrics sulla timeline")
            mapped = _shift_timed_events(events, int(range_start_ms)) if range_mode else map_source_events_to_timeline(track, events)
            # AI inference stays outside the project lock. Refuse to overwrite
            # annotations that changed while the expensive job was running.
            with project_publication_lock(pid):
                latest = load_project(pid)
                if latest.lyrics != project.lyrics:
                    raise RuntimeError("lyrics changed during analysis; result not published")
                latest.lyrics = _replace_timed_range(latest.lyrics, mapped, int(range_start_ms), int(range_end_ms)) if range_mode else mapped
                latest.lyrics_engine = "OpenAI Whisper"
                latest.lyrics_model = selected_model
                _media_job_update(job_id, progress=98, message="Salvataggio lyrics nel progetto")
                save_project(latest)
            _media_job_update(
                job_id, status="completed", progress=100, message="Lyrics estratte e sincronizzate",
                result={"kind": "lyrics", "count": len(mapped), "engine": "OpenAI Whisper", "model": selected_model, "advanced_alignment": advanced_alignment, "range_start_ms": range_start_ms if range_mode else None, "range_end_ms": range_end_ms if range_mode else None},
            )
            return
        if kind == "chords":
            selected_engine=model_or_engine or chords_catalog(native=NATIVE_SINGLE_USER)["default_engine"]
            engine_info=next((x for x in chords_catalog(native=NATIVE_SINGLE_USER)["engines"] if x["id"]==selected_engine),None)
            if not engine_info:
                raise ValueError("unsupported chord extraction engine")
            selected_model=str(engine_info.get("model_id") or "")
            _media_job_update(job_id, progress=5, message=f"Preparazione chords · {engine_info['display_name']}" + (f" · {selected_model}" if selected_model else ""))
            cancel_event=MEDIA_JOBS[job_id].get("cancel_event")
            def chords_progress(pct, items, message):
                # Do not expose inline chord guesses while analysis is running.
                # Chunk/partial labels are unstable and can create many transient
                # intermediate chords that disappear in the final full-pass result.
                _media_job_update(job_id,progress=pct,message=message,partial={"kind":"chords","items":[]})
            from . import native_ai_routing as _native_ai
            if NATIVE_SINGLE_USER and _native_ai.is_remote('chords-ml'):
                payload,remote_id = _native_remote_infer('chords-ml',source,{'engine':selected_engine, **(chord_options or {})})
                from .models import Chord
                doc = payload['json'].get('chords.json')
                if not isinstance(doc,dict) or not isinstance(doc.get('chords'),list):
                    raise ValueError('Remote chords response missing chords.json/chords')
                events = [Chord.model_validate(item) for item in doc['chords']]
                _media_job_update(job_id,remote_job_id=remote_id,progress=90,message='Remote chord analysis completed')
            elif getattr(extract_chords,"__module__","") != "app.music_text":
                try: events=extract_chords(source,engine=selected_engine)
                except TypeError: events=extract_chords(source)
                chords_progress(90,events,"Analisi chords")
            else:
                events=extract_chords_progressive(
                    source,engine=selected_engine,progress=chords_progress,
                    cancelled=(lambda: bool(cancel_event and cancel_event.is_set())),
                    options=chord_options, bpm=float(project.bpm or 120.0),
                    beat_origin_ms=(-int(getattr(track, "delay_ms", 0) or 0)),
                )
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Chord extraction cancelled")
            _media_job_update(job_id, progress=96, message="Sincronizzazione chords sulla timeline")
            mapped = _shift_timed_events(events, int(range_start_ms)) if range_mode else map_source_events_to_timeline(track, events)
            # AI inference stays outside the project lock. Refuse to overwrite
            # annotations that changed while the expensive job was running.
            with project_publication_lock(pid):
                latest = load_project(pid)
                if latest.chords != project.chords:
                    raise RuntimeError("chords changed during analysis; result not published")
                latest.chords = _replace_timed_range(latest.chords, mapped, int(range_start_ms), int(range_end_ms)) if range_mode else mapped
                latest.chords_engine = selected_engine
                latest.chords_model = selected_model
                _media_job_update(job_id, progress=98, message="Salvataggio chords nel progetto")
                save_project(latest)
            _media_job_update(
                job_id, status="completed", progress=100, message="Chords estratti e sincronizzati",
                result={"kind": "chords", "count": len(mapped), "engine": selected_engine, "model": selected_model, "engine_display_name": engine_info["display_name"], "range_start_ms": range_start_ms if range_mode else None, "range_end_ms": range_end_ms if range_mode else None},
            )
            return
        if kind == "markers":
            cancel_event=MEDIA_JOBS[job_id].get("cancel_event")
            def markers_progress(pct, items, message):
                _media_job_update(job_id,progress=pct,message=message,partial={"kind":"markers","items":[]})
            events=extract_markers(source,progress=markers_progress,cancelled=(lambda: bool(cancel_event and cancel_event.is_set())))
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Marker extraction cancelled")
            mapped=map_source_events_to_timeline(track,events)
            with project_publication_lock(pid):
                latest=load_project(pid)
                # Preserve existing/manual markers and only add structural markers that
                # are not already represented nearby. This makes repeated extraction
                # idempotent and avoids destroying user edits.
                existing=list(latest.markers or [])
                merged=list(existing)
                added=0
                for marker in mapped:
                    near=any(abs(int(item.time_ms)-int(marker.time_ms)) < 2500 for item in merged if not getattr(item,"deleted",False))
                    if near:
                        continue
                    merged.append(marker); added += 1
                latest.markers=sorted(merged,key=lambda item:int(item.time_ms))
                save_project(latest)
            # In case of concurrent edits, merge against freshly loaded markers.
            _media_job_update(job_id,status="completed",progress=100,message="Marker/sezioni estratti e sincronizzati",result={"kind":"markers","count":len(mapped),"added":added,"total":len(latest.markers),"engine":"MTA structural analysis"})
            return
        raise ValueError("unsupported analysis kind")
    except InterruptedError as exc:
        _media_job_update(job_id,status="cancelled",message="Estrazione annullata",error=str(exc),result=None)
    except Exception as exc:
        LOGGER.exception("Text/music analysis job %s failed", job_id)
        _media_job_update(job_id, status="failed", progress=0, message="Analisi fallita", error=str(exc)[-1200:])
    finally:
        if range_tmp is not None:
            shutil.rmtree(range_tmp, ignore_errors=True)


def _start_text_music_job(pid: str, track_id: str, request: Request, kind: str, model_or_engine: str = "", advanced_alignment: bool = False, chord_options: dict | None = None, range_start_ms: int | None = None, range_end_ms: int | None = None):
    project = _project_for_actor(request, pid)
    if not any(item.id == track_id for item in project.tracks):
        raise HTTPException(404, "track not found")
    if kind == "lyrics":
        if not (NATIVE_SINGLE_USER and __import__('app.native_ai_routing',fromlist=['is_remote']).is_remote('whisper')) and not lyrics_engine_available():
            raise HTTPException(409, "Motore lyrics Whisper non disponibile in questo runtime")
        allowed={x["id"] for x in lyrics_catalog(native=NATIVE_SINGLE_USER)["models"]}
        if model_or_engine and model_or_engine not in allowed:
            raise HTTPException(400, "Modello lyrics non supportato")
    if kind == "chords":
        selected=model_or_engine or chords_catalog(native=NATIVE_SINGLE_USER)["default_engine"]
        engines={x["id"]:x for x in chords_catalog(native=NATIVE_SINGLE_USER)["engines"]}
        if selected not in engines:
            raise HTTPException(400, "Motore chords non supportato")
        if not (NATIVE_SINGLE_USER and __import__('app.native_ai_routing',fromlist=['is_remote']).is_remote('chords-ml')) and not chord_engine_available(selected):
            raise HTTPException(409, f"Motore chords {engines[selected]['display_name']} non disponibile in questo runtime")
    if (range_start_ms is None) != (range_end_ms is None):
        raise HTTPException(400, "Specificare entrambi i limiti dell’intervallo")
    if range_start_ms is not None:
        if int(range_start_ms) < 0 or int(range_end_ms) <= int(range_start_ms):
            raise HTTPException(400, "Intervallo di estrazione non valido")
    now = time.time()
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id, "kind": f"extract-{kind}", "project_id": pid,
        "status": "queued", "progress": 1,
        "message": "Creazione job di estrazione", "created_at": now, "updated_at": now,
        "result": None, "error": None, "partial": None, "cancel_event": threading.Event(),
    }
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    payload = {
        "schema_version": 1, "kind": kind, "project_id": pid,
        "track_id": track_id, "model_or_engine": model_or_engine,
        "advanced_alignment": bool(advanced_alignment),
        "chord_options": chord_options, "range_start_ms": range_start_ms,
        "range_end_ms": range_end_ms,
    }
    _enqueue_existing_ai_job(job, lambda: _text_music_worker(
        job_id, pid, track_id, kind, model_or_engine, advanced_alignment,
        chord_options, range_start_ms, range_end_ms), durable_payload=payload)
    return _media_job_public(job)


@app.post("/api/projects/{pid}/tracks/{track_id}/extract-lyrics-jobs")
def start_lyrics_extraction(pid: str, track_id: str, request: Request, model: str = "", advanced_alignment: bool = False, range_start_ms: int | None = None, range_end_ms: int | None = None):
    return _start_text_music_job(pid, track_id, request, "lyrics", model, advanced_alignment, range_start_ms=range_start_ms, range_end_ms=range_end_ms)


@app.post("/api/projects/{pid}/tracks/{track_id}/extract-chords-jobs")
def start_chord_extraction(
    pid: str, track_id: str, request: Request, engine: str = "", preset: str = "balanced",
    sensitivity: int | None = None, harmonic_refinement: bool | None = None,
    detect_sevenths: bool | None = None, detect_sus: bool | None = None,
    detect_dim_aug: bool | None = None, detect_slash_bass: bool | None = None,
    temporal_smoothing: bool | None = None, beat_sync: bool | None = None,
    min_chord_ms: int | None = None, max_changes_per_minute: int | None = None,
    range_start_ms: int | None = None, range_end_ms: int | None = None,
):
    if preset == "default-complete":
        preset = "balanced"
    if preset not in {"stable", "balanced", "detailed", "raw"}:
        raise HTTPException(400, "Profilo chords non supportato")
    if sensitivity is not None and not 0 <= sensitivity <= 100:
        raise HTTPException(400, "Sensibilità chords fuori intervallo 0..100")
    options = {
        "preset": preset, "sensitivity": sensitivity, "harmonic_refinement": harmonic_refinement,
        "detect_sevenths": detect_sevenths, "detect_sus": detect_sus, "detect_dim_aug": detect_dim_aug,
        "detect_slash_bass": detect_slash_bass, "temporal_smoothing": temporal_smoothing,
        "beat_sync": beat_sync, "min_chord_ms": min_chord_ms,
        "max_changes_per_minute": max_changes_per_minute,
    }
    return _start_text_music_job(pid, track_id, request, "chords", engine, chord_options=options, range_start_ms=range_start_ms, range_end_ms=range_end_ms)


@app.post("/api/projects/{pid}/tracks/{track_id}/extract-markers-jobs")
def start_marker_extraction(pid: str, track_id: str, request: Request):
    return _start_text_music_job(pid, track_id, request, "markers")


@app.post("/api/projects/{pid}/lyrics/reset")
@_serialized_project_mutation
def reset_project_lyrics(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    project.lyrics = []
    project.lyrics_engine = ""
    project.lyrics_model = ""
    save_project(project)
    return {"ok": True, "lyrics": [], "lyrics_engine": "", "lyrics_model": ""}


@app.post("/api/projects/{pid}/chords/reset")
@_serialized_project_mutation
def reset_project_chords(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    project.chords = []
    project.chords_engine = ""
    project.chords_model = ""
    save_project(project)
    return {"ok": True, "chords": [], "chords_engine": "", "chords_model": ""}


@app.get("/api/projects/{pid}/lyrics.txt")
def download_project_lyrics(pid: str, request: Request, chords: bool = False):
    project = _project_for_actor(request, pid)
    if chords:
        body = synchronized_plain_text(project.lyrics, transpose_chords(project.chords, project.pitch_semitones))
    else:
        body = "\n".join(item.text for item in sorted(project.lyrics, key=lambda x: x.time_ms)) + ("\n" if project.lyrics else "")
    filename = _download_name(project.title or "lyrics", "txt")
    return Response(
        body.encode("utf-8"), media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/projects/{pid}/lyrics.chordpro")
def download_project_chordpro(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    if not project.lyrics:
        raise HTTPException(409, "Il progetto non contiene lyrics")
    body = build_chordpro(
        title=project.title,
        artist=project.artist,
        key=transpose_key_name(project.key, project.pitch_semitones),
        bpm=project.bpm,
        lyrics=project.lyrics,
        chords=transpose_chords(project.chords, project.pitch_semitones),
        authors=project.authors,
        rights_records=project.rights_records,
    )
    filename = _download_name(project.title or "lyrics", "cho")
    return Response(
        body.encode("utf-8"), media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _build_project_lyrics_pdf(project: Project, chord_color: str) -> Path:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", chord_color):
        raise HTTPException(400, "Colore accordi non valido")
    tmp = Path(tempfile.mkstemp(prefix=f"mta-lyrics-{project.id}-", suffix=".pdf")[1])
    build_lyrics_pdf(
        tmp, title=project.title, artist=project.artist,
        lyrics=project.lyrics, chords=transpose_chords(project.chords, project.pitch_semitones), chord_color=chord_color,
        key=transpose_key_name(project.key, project.pitch_semitones), bpm=project.bpm, time_signature=project.time_signature,
        rights_records=project.rights_records, markers=project.markers,
        pdf_style=project.lyrics_pdf_style.model_dump(),
    )
    return tmp


@app.get("/api/projects/{pid}/lyrics.pdf")
def download_project_lyrics_pdf(pid: str, request: Request, chord_color: str = "#7B1FA2", preview: bool = False):
    project = _project_for_actor(request, pid)
    if not project.lyrics:
        raise HTTPException(409, "Il progetto non contiene lyrics")
    tmp = _build_project_lyrics_pdf(project, chord_color)
    filename = _download_name(project.title or "lyrics", "pdf")
    if preview:
        return FileResponse(
            tmp, media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
            background=BackgroundTask(lambda: tmp.unlink(missing_ok=True)),
        )
    return FileResponse(
        tmp, media_type="application/pdf", filename=filename,
        background=BackgroundTask(lambda: tmp.unlink(missing_ok=True)),
    )


@app.get("/api/projects/{pid}/lyrics.pdf.preview")
def preview_project_lyrics_pdf_exact(pid: str, request: Request, chord_color: str = "#7B1FA2"):
    """Render the actual exported PDF pages for native-safe, pixel-faithful preview."""
    project = _project_for_actor(request, pid)
    if not project.lyrics:
        raise HTTPException(409, "Il progetto non contiene lyrics")
    pdf_path = _build_project_lyrics_pdf(project, chord_color)
    try:
        import fitz  # PyMuPDF: rasterizes the exact generated PDF, not a parallel HTML layout.

        doc = fitz.open(pdf_path)
        pages = []
        matrix = fitz.Matrix(1.45, 1.45)
        for number, page in enumerate(doc, start=1):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            pages.append(
                f'<figure class="pdf-page"><img alt="Pagina {number}" src="data:image/png;base64,{encoded}">'
                f'<figcaption>Pagina {number} / {doc.page_count}</figcaption></figure>'
            )
        doc.close()
        html = (
            '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>html,body{margin:0;background:#4f5963;color:#eef8ff;font-family:system-ui,sans-serif}'
            '.pages{padding:12px;display:grid;gap:14px;justify-items:center}.pdf-page{margin:0;max-width:100%}'
            '.pdf-page img{display:block;max-width:100%;height:auto;background:#fff;box-shadow:0 2px 12px #0008}'
            '.pdf-page figcaption{text-align:center;font-size:12px;padding:5px 0 0;color:#d6e4ee}</style></head>'
            f'<body><main class="pages">{"".join(pages)}</main></body></html>'
        )
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})
    except ImportError as exc:
        raise HTTPException(500, "Renderer anteprima PDF non disponibile") from exc
    finally:
        pdf_path.unlink(missing_ok=True)


@app.post("/api/projects/{pid}/metadata-search")
def api_project_metadata_search(pid: str, request: Request, body: dict):
    project = _project_for_actor(request, pid)
    title = str(body.get("title") or project.title or "").strip()
    artist = str(body.get("artist") or project.artist or "").strip()
    if not title:
        raise HTTPException(400, "Inserisci il titolo del brano")
    try:
        results = search_musicbrainz_metadata(title=title, artist=artist, limit=25)
    except Exception as exc:
        LOGGER.warning("MusicBrainz metadata search failed: %s", exc)
        raise HTTPException(502, f"Ricerca metadata online non riuscita: {exc}") from exc
    return {
        "query": {"title": title, "artist": artist},
        "results": results,
        "catalogs": [
            {"id": "MUSICBRAINZ", "name": "MusicBrainz", "mode": "api", "portal_url": "https://musicbrainz.org/"},
            {"id": "SIAE", "name": "SIAE", "mode": "portal", "portal_url": "https://www.siae.it/it/repertorio/"},
            {"id": "SOUNDREEF", "name": "Soundreef / LEA", "mode": "portal", "portal_url": "https://www.soundreef.com/"},
        ],
    }


@app.get("/api/projects/{pid}/metadata-resolve/{mbid}")
def api_project_metadata_resolve(pid: str, mbid: str, request: Request):
    _project_for_actor(request, pid)
    try:
        return resolve_musicbrainz_metadata(mbid)
    except Exception as exc:
        LOGGER.warning("MusicBrainz metadata resolve failed: %s", exc)
        raise HTTPException(502, f"Risoluzione metadata online non riuscita: {exc}") from exc


@app.get("/api/rights-providers")
def api_rights_providers(request: Request):
    require_user(request)
    return {"providers": rights_provider_catalog(), "default_active": ["SIAE", "SOUNDREEF"]}


@app.post("/api/projects/{pid}/rights-search")
def api_project_rights_search(pid: str, request: Request, body: dict):
    project = _project_for_actor(request, pid)
    societies = [str(x).upper() for x in (body.get("societies") or project.rights_societies or ["SIAE", "SOUNDREEF"]) if str(x).strip()]
    title = str(body.get("title") or project.title or "").strip()
    original_title = str(body.get("original_title") or project.original_title or "").strip()
    artist = str(body.get("artist") or project.artist or "").strip()
    authors = body.get("authors") or project.authors
    if isinstance(authors, str):
        authors = [x.strip() for x in authors.replace(";", ",").split(",") if x.strip()]
    authors = [str(x).strip() for x in (authors or []) if str(x).strip()]
    if not any([title, original_title, artist, authors]):
        raise HTTPException(400, "Inserisci almeno titolo, titolo originale, autore o interprete")
    providers: list[dict] = []
    results: list[dict] = []
    for society in societies:
        try:
            data = search_rights_provider(society, title=title, original_title=original_title, artist=artist, authors=authors)
            providers.append({k: v for k, v in data.items() if k != "results"})
            results.extend(data.get("results") or [])
        except ValueError as exc:
            providers.append({"provider": society, "mode": "error", "results": [], "message": str(exc), "portal_url": ""})
        except Exception as exc:
            LOGGER.warning("Rights provider %s search failed: %s", society, exc)
            providers.append({"provider": society, "mode": "error", "results": [], "message": str(exc), "portal_url": ""})
    return {"query": {"title": title, "original_title": original_title, "artist": artist, "authors": authors}, "providers": providers, "results": results}


@app.put("/api/projects/{pid}/rights-records")
@_serialized_project_mutation
def api_project_rights_records(pid: str, request: Request, body: dict):
    project = _project_for_actor(request, pid)
    raw_records = body.get("records") or []
    if not isinstance(raw_records, list) or len(raw_records) > 32:
        raise HTTPException(400, "Elenco risultati repertorio non valido")
    try:
        project.rights_records = [RightsRecord(**item) for item in raw_records]
        raw_societies = body.get("societies")
        if raw_societies is not None:
            if not isinstance(raw_societies, list) or len(raw_societies) > 16:
                raise ValueError("Elenco società non valido")
            societies = []
            for value in raw_societies:
                society = str(value).strip().upper()
                if society and society not in societies:
                    societies.append(society)
            project.rights_societies = societies
    except Exception as exc:
        raise HTTPException(400, f"Dati repertorio non validi: {exc}") from exc
    save_project(project)
    return {
        "ok": True,
        "rights_records": [item.model_dump(mode="json") for item in project.rights_records],
        "rights_societies": project.rights_societies,
    }





YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}


def _validated_youtube_url(value: str) -> str:
    url = str(value or "").strip()
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        raise ValueError("URL YouTube non valido") from exc
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or host not in YOUTUBE_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Sono accettati solo URL HTTPS di YouTube")
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif parsed.path == "/watch":
        video_id = (parse_qs(parsed.query).get("v") or [""])[0]
    else:
        parts = [p for p in parsed.path.split("/") if p]
        video_id = parts[1] if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed"} else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,20}", video_id or ""):
        raise ValueError("L'URL deve identificare un singolo video YouTube")
    return url


def _youtube_import_worker(
    job_id: str,
    pid: str,
    url: str,
    requested_name: str,
    track_type: str,
    offset_ms: int,
    sync_mode: str,
    reference_track_id: str,
) -> None:
    try:
        from yt_dlp import YoutubeDL

        project = load_project(pid)
        _media_job_update(job_id, status="running", progress=4, message="Connessione a YouTube")
        with tempfile.TemporaryDirectory(prefix="mta-youtube-") as td:
            work = Path(td)
            def hook(data: dict) -> None:
                status = data.get("status")
                if status == "downloading":
                    total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                    done = data.get("downloaded_bytes") or 0
                    pct = int(done * 45 / total) if total else 12
                    _media_job_update(job_id, progress=max(6, min(48, 6 + pct)), message="Download audio da YouTube")
                elif status == "finished":
                    _media_job_update(job_id, progress=52, message="Download completato")

            options = {
                "format": "bestaudio/best",
                "outtmpl": str(work / "source.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "socket_timeout": 20,
                "retries": 3,
                "max_filesize": MAX_UPLOAD_BYTES,
                "progress_hooks": [hook],
                "restrictfilenames": True,
            }
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    raise ValueError("YouTube non ha restituito informazioni sul video")
                requested = info.get("requested_downloads") or []
                source = Path(requested[0].get("filepath")) if requested and requested[0].get("filepath") else Path(ydl.prepare_filename(info))
            if not source.is_file():
                candidates = [p for p in work.iterdir() if p.is_file() and not p.name.endswith(('.part', '.ytdl'))]
                if not candidates:
                    raise ValueError("Traccia audio scaricata non trovata")
                source = max(candidates, key=lambda p: p.stat().st_size)
            size = source.stat().st_size
            if size <= 0 or size > MAX_UPLOAD_BYTES:
                raise ValueError("La traccia YouTube supera il limite di import configurato")
            _ensure_workspace_capacity(project.owner_user_id, size)
            ffprobe(source)
            duplicate = find_duplicate_project_file(pid, source)
            if duplicate:
                raise ValueError(f"Il contenuto è già presente nel progetto come {duplicate['category']}/{duplicate['name']}")
            ext = source.suffix.lower()
            if len(ext) > 12 or not ext.replace('.', '').isalnum():
                ext = ".m4a"
            filename = f"{uuid.uuid4().hex[:10]}{ext}"
            dst = audio_path(pid, filename)
            shutil.copy2(source, dst)
            title = str(info.get("title") or requested_name or "YouTube audio").strip()[:200]
            safe_title = SAFE_DOWNLOAD_RE.sub("_", title).strip(" ._")[:120] or "youtube-audio"
            preserve_original(pid, dst, safe_title + ext)
        first_track = len(project.tracks) == 0
        _media_job_update(job_id, progress=55, message="Import della traccia nel progetto")
        _track_import_worker(
            job_id, pid, filename, safe_title + ext, requested_name or title,
            track_type, offset_ms, sync_mode, reference_track_id, first_track,
            f"YouTube: {url}",
        )
    except Exception as exc:
        LOGGER.exception("YouTube import job %s failed", job_id)
        _media_job_update(job_id, status="failed", progress=0, message="Import YouTube fallito", error=str(exc)[-1200:])


@app.post("/api/projects/{pid}/youtube-import-jobs")
def start_youtube_import_job(pid: str, request: Request, body: dict):
    _project_for_actor(request, pid)
    if body.get("confirm_rights") is not True:
        raise HTTPException(400, "Conferma di disporre dei diritti necessari per importare questo contenuto")
    try:
        url = _validated_youtube_url(str(body.get("url", "")))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    sync_mode = str(body.get("sync_mode", "manual"))
    if sync_mode not in {"manual", "auto"}:
        raise HTTPException(400, "sync_mode non valido")
    try:
        offset_ms = int(body.get("offset_ms", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(400, "offset_ms non valido") from exc
    now = time.time()
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "kind": "youtube-import",
        "project_id": pid,
        "status": "queued",
        "progress": 2,
        "message": "Import YouTube in coda",
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    threading.Thread(
        target=_youtube_import_worker,
        args=(
            job_id, pid, url, str(body.get("name", ""))[:200], str(body.get("type", "other")),
            offset_ms, sync_mode, str(body.get("reference_track_id", ""))[:64],
        ),
        daemon=True,
        name=f"youtube-import-{job_id}",
    ).start()
    return _media_job_public(job)


def _rehydrate_persisted_text_job(job_id: str):
    """Read-only status recovery for durable text-analysis jobs after restart.

    Never start inference or replay side effects merely by polling a status.
    """
    row = ai_arranger_runtime.get(job_id)
    if not row or row.get("operation") not in ("extract-lyrics", "extract-chords", "extract-markers", "download-lyrics-model", "download-chords-model"):
        return None
    payload = ai_arranger_runtime.read_payload(job_id)
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return None
    if row["operation"].startswith("download-"):
        if row.get("project_id") != "server-models" or payload.get("kind") != row["operation"].removeprefix("download-").removesuffix("-model"):
            return None
        if not isinstance(payload.get("model_id"), str):
            return None
    elif payload.get("project_id") != row.get("project_id") or payload.get("kind") != row["operation"].removeprefix("extract-"):
        return None
    state = row.get("state", "interrupted")
    now = time.time()
    return {"id": job_id, "kind": row["operation"],
        "project_id": None if row["operation"].startswith("download-") else row["project_id"],
        "status": state, "progress": row.get("progress_percent") or 0,
        "message": row.get("message") or "Persistent AI job", "created_at": row.get("created_at") or now,
        "updated_at": row.get("completed_at") or now, "result": None,
        "error": None, "partial": None, "cancel_event": threading.Event()}


@app.get("/api/media-jobs/{job_id}")
def media_job_status(job_id: str, request: Request):
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.get(job_id)
        snapshot = dict(job) if job is not None else None
    if snapshot is None:
        snapshot = _rehydrate_persisted_text_job(job_id)
    if snapshot is None:
        raise HTTPException(404, "Job non trovato")
    if snapshot.get("project_id"):
        _project_for_actor(request, snapshot["project_id"])
    else:
        _actor(request)
    return _media_job_public(snapshot)


@app.post("/api/media-jobs/{job_id}/cancel")
def cancel_media_job(job_id: str, request: Request):
    # Authorize BEFORE touching the cancellation event or queue state.
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.get(job_id)
        if job is None:
            job = _rehydrate_persisted_text_job(job_id)
        if job is None:
            raise HTTPException(404, "Job non trovato")
        project_id = job.get("project_id")
    if project_id:
        _project_for_actor(request, project_id)
    else:
        _actor(request)
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.get(job_id)
        if job is None:
            job = _rehydrate_persisted_text_job(job_id)
        if job is None:
            raise HTTPException(404, "Job non trovato")
        event = job.get("cancel_event")
        if event is None:
            raise HTTPException(409, "Questo job non supporta l'annullamento")
        # A queued job is removed from the transactional queue before it can start.
        queue_row = ai_arranger_runtime.get(job_id)
        if queue_row and job_id not in MEDIA_JOBS and queue_row["state"] != "queued":
            raise HTTPException(409, "Il job non è più in attesa: impossibile annullarlo da questo processo")
        if queue_row and queue_row["state"] == "queued":
            ai_arranger_runtime.cancel(job_id)
            job["status"] = "cancelled"
            job["message"] = "Annullato prima dell'esecuzione"
        else:
            job["message"] = "Annullamento richiesto…"
        event.set()
        job["updated_at"] = time.time()
    return _media_job_public(job)


@app.post("/api/projects/{pid}/tracks")
async def add_track(
    pid: str,
    request: Request,
    file: UploadFile = File(...),
    name: str = "",
    type: str = "other",
    offset_ms: int = 0,
    sync_mode: str = "manual",
    reference_track_id: str = "",
):
    from .ai_project_lock import project_publication_lock
    with project_publication_lock(pid):
        return await _add_track_under_project_lock(pid, request, file, name=name, type=type, offset_ms=offset_ms, sync_mode=sync_mode, reference_track_id=reference_track_id)


async def _add_track_under_project_lock(
    pid: str, request: Request, file: UploadFile, name: str = "",
    type: str = "other", offset_ms: int = 0, sync_mode: str = "manual",
    reference_track_id: str = "", recovery_receipt: str = "",
):
    if sync_mode not in {"manual", "auto"}:
        raise HTTPException(400, "invalid sync mode")
    project = _project_for_actor(request, pid)
    from .ai_upload_transaction import begin as begin_upload
    begin_upload(pid)
    filename, dst, duration = _save_upload(pid, file)
    upload_stat = dst.lstat()
    upload_identity = (upload_stat.st_dev, upload_stat.st_ino)
    allowed = Track.model_fields["type"].annotation.__args__
    track = Track(
        id=uuid.uuid4().hex[:10],
        name=(name or Path(file.filename or filename).stem)[:200],
        type=type if type in allowed else "other",
        filename=filename,
        duration_ms=duration,
        sample_rate=int(project.sample_rate),
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
            _rollback_unpublished_upload(pid, dst, upload_identity)
            raise HTTPException(400, "automatic sync failed") from exc
    try:
        project.tracks.append(track)
        _register_track_source_in_library(project, track, f"Import file: {Path(file.filename or filename).name}")
        if recovery_receipt:
            if recovery_receipt in project.recovered_ai_imports:
                raise HTTPException(409, "This remote result was already imported")
            project.recovered_ai_imports.append(recovery_receipt)
        save_project(project)
    except BaseException:
        _rollback_unpublished_upload(pid, dst, upload_identity)
        raise
    from .ai_upload_transaction import finish as finish_upload
    finish_upload(pid)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/replace")
@_serialized_project_mutation
async def replace_track(
    pid: str,
    track_id: str,
    request: Request,
    file: UploadFile = File(...),
    sync_mode: str = "keep",
    offset_ms: int = 0,
    reference_track_id: str = "",
):
    if sync_mode not in {"manual", "auto", "keep"}:
        raise HTTPException(400, "invalid sync mode")
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    ensure_clips(track)
    previous_offset = track.clips[0].timeline_start_ms if track.clips else 0
    old = audio_path(pid, track.filename)
    old_stat = old.lstat() if old.exists() else None
    old_identity = (old_stat.st_dev, old_stat.st_ino) if old_stat else None
    from .ai_upload_transaction import begin as begin_upload
    begin_upload(pid)
    filename, dst, duration = _save_upload(pid, file)
    upload_stat = dst.lstat()
    upload_identity = (upload_stat.st_dev, upload_stat.st_ino)

    track.filename = filename
    track.duration_ms = duration
    track.channels, track.channel_layout = _audio_channel_info(dst)
    track.sample_rate = int(project.sample_rate)
    track.waveform_peaks = []
    track.waveform_revision = ""
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
        _rollback_unpublished_upload(pid, dst, upload_identity)
        raise
    except Exception as exc:
        _rollback_unpublished_upload(pid, dst, upload_identity)
        raise HTTPException(400, "automatic sync failed") from exc

    try:
        _register_track_source_in_library(project, track)
        save_project(project)
    except BaseException:
        _rollback_unpublished_upload(pid, dst, upload_identity)
        raise
    library_files = {item.filename for item in project.clip_library} | {item.filename for item in project.tracks}
    if old_identity is not None and old.name != filename and old.name not in library_files:
        _rollback_unpublished_upload(pid, old, old_identity)
    from .ai_upload_transaction import finish as finish_upload
    finish_upload(pid)
    return project



@app.patch("/api/projects/{pid}/clip-library/{clip_id}")
@_serialized_project_mutation
def update_project_clip(pid: str, clip_id: str, req: UpdateProjectClipRequest, request: Request):
    project = _project_for_actor(request, pid)
    _ensure_project_clip_library(project)
    asset = next((item for item in project.clip_library if item.id == clip_id), None)
    if asset is None:
        raise HTTPException(404, "clip di libreria non trovata")
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(400, "nome clip non valido")
        asset.name = name[:200]
    if req.notes is not None:
        asset.notes = req.notes[:4000]
    _refresh_project_clip_metadata(project, asset)
    save_project(project)
    return {"project": project, "clip": asset}


@app.post("/api/projects/{pid}/clip-library/{clip_id}/instantiate")
@_serialized_project_mutation
def instantiate_project_clip(pid: str, clip_id: str, req: InstantiateProjectClipRequest, request: Request):
    project = _project_for_actor(request, pid)
    try:
        _ensure_project_clip_library(project)
    except ValueError as exc:
        raise HTTPException(400, "percorso audio della clip non sicuro") from exc
    asset = next((item for item in project.clip_library if item.id == clip_id), None)
    if asset is None:
        raise HTTPException(404, "clip di libreria non trovata")
    source = audio_path(pid, asset.filename)
    # A clip asset is immutable. Never instantiate a link or an unsafe inode.
    source_stat = source.lstat() if source.exists() or source.is_symlink() else None
    if source_stat is None or not stat.S_ISREG(source_stat.st_mode):
        raise HTTPException(404, "file audio della clip non disponibile")
    track_filename = asset.filename
    track_source = source
    owned = []
    try:
        try:
            source_rate = _audio_sample_rate(source)
        except Exception:
            # Some legacy clips carry valid sample-rate metadata but an audio
            # probe is not possible; retain historic no-conversion behavior.
            source_rate = int(getattr(asset, "sample_rate", 44100) or 44100)
            if source_rate != int(project.sample_rate):
                raise HTTPException(400, "impossibile verificare il sample rate della clip")
        if source_rate not in {44100, 48000, 96000}:
            raise HTTPException(400, "sample rate della clip non supportato")
        if source_rate != int(project.sample_rate):
            # Unique staging name prevents collision with another conversion.
            working_name = f"{uuid.uuid4().hex[:16]}{source.suffix.lower() or '.wav'}"
            working = audio_path(pid, working_name)
            with source.open("rb") as incoming, working.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            owned.append((working, (working.stat().st_dev, working.stat().st_ino)))
            track_filename, track_source, _ = _normalize_audio_to_project_rate(
                pid, working_name, project.sample_rate
            )
            owned.append((track_source, (track_source.stat().st_dev, track_source.stat().st_ino)))
        track = Track(
            id=uuid.uuid4().hex[:10],
            name=asset.name[:200],
            type=asset.type,
            filename=track_filename,
            source_clip_id=asset.id,
            duration_ms=asset.duration_ms,
            clips=[Clip(
                id=uuid.uuid4().hex[:10],
                source_start_ms=0,
                source_end_ms=asset.duration_ms,
                timeline_start_ms=req.timeline_start_ms,
            )],
            channels=asset.channels,
            channel_layout=asset.channel_layout,
            sample_rate=int(project.sample_rate),
        )
        try:
            track.waveform_peaks = waveform_peaks(track_source, 4096)
            track.waveform_revision = _track_waveform_revision(track, track_source)
        except Exception:
            track.waveform_peaks = []
            track.waveform_revision = ""
        project.tracks.append(track)
        save_project(project)
    except BaseException:
        # A failed save can occur *after* the project was durably committed.
        # Only roll back media whose names are absent from persisted metadata.
        for path, identity in reversed(owned):
            _rollback_unpublished_upload(pid, path, identity)
        raise
    return {"project": project, "track": track, "clip": asset}


def _disposable_generated_track(track: Track) -> bool:
    name = str(getattr(track, "name", "") or "").strip().lower()
    filename = str(getattr(track, "filename", "") or "").lower()
    return (
        str(getattr(track, "type", "") or "").lower() == "click"
        or "metronom" in name
        or filename.startswith("metronome-")
        or name in {"chords", "accordi", "chords piano", "accordi piano"}
        or filename.startswith("chords-piano-")
    )


@app.post("/api/projects/{pid}/delete-tracks")
@_serialized_project_mutation
def delete_tracks(pid: str, req: DeleteTracksRequest | list[str], request: Request):
    persisted = _project_for_actor(request, pid)
    snapshot = req.project if isinstance(req, DeleteTracksRequest) else None
    requested_ids = req.track_ids if isinstance(req, DeleteTracksRequest) else req
    project = snapshot.model_copy(deep=True) if snapshot is not None else persisted.model_copy(deep=True)
    if project.id != pid:
        raise HTTPException(400, "project id mismatch")
    # Preserve security-owned fields and durable reusable clip assets from the authoritative copy.
    project.owner_user_id = persisted.owner_user_id
    project.shared_with_user_ids = persisted.shared_with_user_ids
    _ensure_project_clip_library(persisted)
    known_clip_files = {item.filename for item in project.clip_library}
    for item in persisted.clip_library:
        if item.filename not in known_clip_files:
            project.clip_library.append(item)
            known_clip_files.add(item.filename)
    _ensure_project_clip_library(project)

    wanted = {str(track_id) for track_id in requested_ids}
    if not wanted:
        raise HTTPException(400, "no tracks selected")
    known = {track.id for track in project.tracks}
    if not wanted <= known:
        raise HTTPException(400, "unknown track id")
    removed = [track for track in project.tracks if track.id in wanted]
    project.tracks = [track for track in project.tracks if track.id not in wanted]

    # Generated guide tracks are disposable assets; imported/project clips remain reusable.
    remaining_files = {track.filename for track in project.tracks}
    disposable_asset_ids = {track.source_clip_id for track in removed if track.source_clip_id and _disposable_generated_track(track)}
    disposable_files = {track.filename for track in removed if _disposable_generated_track(track)}
    project.clip_library = [
        item for item in project.clip_library
        if not (
            item.filename not in remaining_files
            and (item.id in disposable_asset_ids or item.filename in disposable_files)
        )
    ]

    try:
        validate_project_files(project)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    # Logical delete is the transaction boundary: commit project.json first.
    save_project(project)
    # Physical cleanup is durable, retryable and intentionally outside request latency.
    schedule_project_gc(pid, {track.filename for track in removed if track.filename})
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/delay")
@_serialized_project_mutation
def set_track_delay(pid: str, track_id: str, req: TrackDelayRequest, request: Request):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    track.delay_ms = int(req.delay_ms)
    save_project(project)
    return {"project": project, "track_id": track.id, "delay_ms": track.delay_ms}


@app.post("/api/projects/{pid}/tracks/{track_id}/sync-metronome")
@_serialized_project_mutation
def sync_metronome_to_track(pid: str, track_id: str, request: Request):
    project = _project_for_actor(request, pid)
    reference = next((item for item in project.tracks if item.id == track_id), None)
    if not reference:
        raise HTTPException(404, "track not found")
    metronome = next((item for item in project.tracks if item.id != track_id and (item.type == "click" or "metronom" in item.name.lower() or "metronome" in item.name.lower() or "click" in item.name.lower())), None)
    if not metronome:
        raise HTTPException(400, "Traccia metronomo non trovata")
    try:
        delta = auto_align_ms(audio_path(pid, reference.filename), audio_path(pid, metronome.filename))
    except Exception as exc:
        raise HTTPException(400, "Sincronizzazione metronomo fallita") from exc
    metronome.delay_ms = int(getattr(metronome, "delay_ms", 0) or 0) + int(delta)
    save_project(project)
    return {"project": project, "reference_track_id": reference.id, "metronome_track_id": metronome.id, "delta_ms": int(delta), "delay_ms": metronome.delay_ms}


@app.post("/api/projects/{pid}/tracks/{track_id}/move")
@_serialized_project_mutation
def move_track(pid: str, track_id: str, req: MoveTrackRequest, request: Request):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    shift_track(track, req.offset_ms)
    save_project(project)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/autosync")
@_serialized_project_mutation
def autosync_track(pid: str, track_id: str, request: Request, reference_track_id: str = ""):
    project = _project_for_actor(request, pid)
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


@app.post("/api/projects/{pid}/auto-mix")
@_serialized_project_mutation
def project_auto_mix(pid: str, req: AutoMixRequest, request: Request):
    project = _project_for_actor(request, pid)
    if req.enabled:
        enable_auto_mix(project, req.style)
    else:
        disable_auto_mix(project)
    save_project(project)
    return project


@app.post("/api/projects/{pid}/delete-range")
@_serialized_project_mutation
def edit_delete_range(pid: str, req: DeleteRangeRequest, request: Request):
    project = _project_for_actor(request, pid)
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



def _mta_import_worker(job_id: str, pid: str, source_name: str) -> None:
    try:
        src = pdir(pid) / "source.mta"
        _media_job_update(job_id, status="running", progress=58, message="Validazione MTA")
        ffprobe(src)
        _media_job_update(job_id, progress=68, message="Analisi contenitore MTA")
        # import_mta writes audio, attachments and project.json. Hold the shared
        # cross-process lock for this whole publication, not just save_project.
        from .ai_project_lock import project_publication_lock
        with project_publication_lock(pid):
            project = load_project(pid)
            imported = import_mta(src, project)
            _media_job_update(job_id, progress=92, message="Salvataggio progetto importato")
            save_project(imported)
        _media_job_update(
            job_id,
            status="completed",
            progress=100,
            message="Import MTA completato",
            result={"project_id": imported.id, "title": imported.title, "track_count": len(imported.tracks)},
        )
    except Exception as exc:
        delete_project(pid)
        _media_job_update(
            job_id,
            status="failed",
            progress=0,
            message="Import MTA fallito",
            error=str(exc)[-1200:],
        )


@app.post("/api/import-jobs")
async def start_mta_import_job(request: Request, file: UploadFile = File(...)):
    actor = _actor(request)
    _ensure_workspace_capacity(actor["id"] if actor["id"] > 0 else None, int(request.headers.get("content-length") or 0))
    owner = actor["id"] if actor["id"] > 0 else None
    project = create_project(Path(file.filename or "Imported").stem[:200], owner_user_id=owner)
    src = pdir(project.id) / "source.mta"
    try:
        _copy_limited(file.file, src)
        preserve_original(project.id, src, Path(file.filename or "source.mta").name)
    except Exception:
        delete_project(project.id)
        raise

    now = time.time()
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "kind": "mta-import",
        "project_id": project.id,
        "status": "queued",
        "progress": 55,
        "message": "Upload MTA completato",
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    threading.Thread(
        target=_mta_import_worker,
        args=(job_id, project.id, Path(file.filename or "source.mta").name),
        daemon=True,
        name=f"mta-import-{job_id}",
    ).start()
    return _media_job_public(job)


@app.post("/api/import")
async def import_file(request: Request, file: UploadFile = File(...)):
    actor = _actor(request)
    _ensure_workspace_capacity(actor["id"] if actor["id"] > 0 else None, int(request.headers.get("content-length") or 0))
    owner = actor["id"] if actor["id"] > 0 else None
    project = create_project(Path(file.filename or "Imported").stem[:200], owner_user_id=owner)
    src = pdir(project.id) / "source.mta"
    _copy_limited(file.file, src)
    preserve_original(project.id, src, Path(file.filename or "source.mta").name)
    try:
        from .ai_project_lock import project_publication_lock
        with project_publication_lock(project.id):
            # Reload only after acquiring the shared publication lock.
            return import_mta(src, load_project(project.id))
    except Exception as exc:
        delete_project(project.id)
        raise HTTPException(400, "MTA import failed") from exc


def _download_name(title: str, ext: str) -> str:
    clean = SAFE_DOWNLOAD_RE.sub("_", title).strip(" ._")[:120] or "project"
    return f"{clean}.{ext}"


def _split_lead_backing_vocals(vocal_stem: Path, output_dir: Path, *, model_id: str | None = None, cancel_event=None) -> tuple[Path, Path, str]:
    from . import native_ai_routing as _remote
    if NATIVE_SINGLE_USER and _remote.is_remote('backing-vocals'):
        result, remote_id = _native_remote_infer('backing-vocals', vocal_stem, {'model':model_id or LEAD_BACKING_DEFAULT_MODEL})
        files=list(result['audio'].values())
        if len(files)!=2: raise ValueError('Remote backing vocal split must return exactly two stems')
        output_dir.mkdir(parents=True,exist_ok=True)
        lead_data=next((data for name,data in result['audio'].items() if 'lead' in name.lower() or 'vocal' in name.lower()),files[0])
        backing_data=next((data for name,data in result['audio'].items() if 'back' in name.lower() or 'instrument' in name.lower()),None)
        if backing_data is None: backing_data=next((x for x in files if x is not lead_data),None)
        if backing_data is None: raise ValueError('Missing backing-vocal stem')
        lead=output_dir/'lead_vocals.wav';backing=output_dir/'backing_vocals.wav'
        lead.write_bytes(lead_data);backing.write_bytes(backing_data)
        return lead,backing,'remote:'+remote_id
    """Split an isolated vocal stem into lead and backing vocals using a selectable AI karaoke model.

    Models are downloaded on demand. In server/web mode they are cached on the server;
    in native single-user mode the same cache is local to the desktop application.
    The legacy center/side DSP path is only used when explicitly selected.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    lead = output_dir / "lead_vocals.wav"
    backing = output_dir / "backing_vocals.wav"
    command_template = os.getenv("MTA_LEAD_BACKING_COMMAND", "").strip()
    if command_template:
        values = {"input": str(vocal_stem), "lead": str(lead), "backing": str(backing), "output_dir": str(output_dir)}
        command = [part.format(**values) for part in shlex.split(command_template)]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                proc.terminate()
                raise RuntimeError("stem separation cancelled")
            time.sleep(0.1)
        output = proc.stdout.read() if proc.stdout else ""
        if proc.returncode or not lead.exists() or not backing.exists():
            raise RuntimeError((output or "lead/backing vocal separator failed")[-3000:])
        return lead, backing, os.getenv("MTA_LEAD_BACKING_MODEL", "configured-ai").strip() or "configured-ai"
    selected = (model_id or LEAD_BACKING_DEFAULT_MODEL).strip()
    if selected == "ffmpeg-center-side":
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg is required for lead/backing vocal fallback separation")
        filter_graph = (
            "[0:a]asplit=2[a][b];"
            "[a]pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1[lead];"
            "[b]pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c1-0.5*c0[backing]"
        )
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(vocal_stem), "-filter_complex", filter_graph, "-map", "[lead]", "-c:a", "pcm_s24le", str(lead), "-map", "[backing]", "-c:a", "pcm_s24le", str(backing)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip() or "lead/backing vocal fallback separation failed")
        return lead, backing, "ffmpeg-center-side"

    info = _lead_backing_model_info(selected)
    if not info["installed"]:
        info = _download_lead_backing_model(selected)
    try:
        from audio_separator.separator import Separator
    except ImportError as exc:
        raise RuntimeError("audio-separator is required for AI lead/backing vocal separation") from exc
    try:
        import torch
        from torchvision.ops import nms
        # Validate the compiled torchvision extension; importing torchvision is not sufficient.
        nms(torch.empty((0, 4)), torch.empty((0,)), 0.5)
    except (ImportError, RuntimeError, OSError) as exc:
        raise RuntimeError(
            "Incompatible PyTorch/torchvision native operators (torchvision::nms). "
            "Reinstall matching PyTorch and torchvision builds for your OS/architecture."
        ) from exc
    separator = Separator(model_file_dir=str(LEAD_BACKING_MODEL_DIR), output_dir=str(output_dir), output_format="WAV")
    try:
        separator.load_model(model_filename=info["filename"])
    except Exception as exc:
        if "beartype" in str(exc).lower() and ("callable" in str(exc).lower() or "pep" in str(exc).lower()):
            raise RuntimeError(
                "RoFormer model cannot be loaded with the installed beartype validator. "
                "Install a compatible beartype >= 0.22.2 build, then restart MTA Audio Editor. "
                f"Original error: {exc}"
            ) from exc
        raise
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("stem separation cancelled")
    # audio-separator may return bare filenames even when output_dir is configured.
    # Never resolve those against the server's current working directory.
    raw_outputs = separator.separate(str(vocal_stem)) or []
    outputs = []
    for item in raw_outputs:
        path = Path(item)
        if not path.is_absolute():
            # Some versions return a relative path including output_dir; others
            # return only the filename. Prefer the actual job output directory.
            candidates = (output_dir / path, output_dir / path.name)
            path = next((candidate for candidate in candidates if candidate.is_file()), candidates[0])
        if path.is_file() and path.parent.resolve() == output_dir.resolve():
            outputs.append(path)
    vocal_output = next((x for x in outputs if "vocal" in x.name.lower() and "back" not in x.name.lower()), None)
    backing_output = next((x for x in outputs if any(k in x.name.lower() for k in ("instrumental", "karaoke", "backing"))), None)
    if vocal_output is None or backing_output is None or vocal_output == backing_output:
        raise RuntimeError(
            "AI separator did not produce both lead and backing stems in its output directory: "
            f"{[str(x) for x in outputs]} (returned: {[str(x) for x in raw_outputs]})"
        )
    shutil.move(str(vocal_output), lead)
    shutil.move(str(backing_output), backing)
    return lead, backing, f"audio-separator:{selected}"


def _split_drums_percussions(drums_stem: Path, output_dir: Path) -> tuple[Path, Path]:
    """Use transient/tonal spectral masks to create two complementary drum stems.

    Percussion is the predominantly transient portion of the original drums stem;
    the residual retains the drum kit body.  It is a signal-processing estimate,
    not instrument-level source separation.
    """
    import numpy as np
    import soundfile as sf
    from scipy import signal
    from scipy.ndimage import median_filter

    output_dir.mkdir(parents=True, exist_ok=True)
    audio, rate = sf.read(str(drums_stem), dtype="float32", always_2d=True)
    if not len(audio):
        raise RuntimeError("Empty drums audio")
    percussion = np.zeros_like(audio)
    for ch in range(audio.shape[1]):
        _, _, stft = signal.stft(audio[:, ch], fs=rate, nperseg=2048, noverlap=1536,
                                  boundary="zeros", padded=True)
        magnitudes = np.abs(stft)
        # Median filters across time/frequency approximate harmonic/percussive masks.
        time_smooth = median_filter(magnitudes, size=(1, 17))
        freq_smooth = median_filter(magnitudes, size=(17, 1))
        mask = np.square(freq_smooth) / (np.square(time_smooth) + np.square(freq_smooth) + 1e-9)
        _, separated = signal.istft(stft * mask, fs=rate, nperseg=2048, noverlap=1536,
                                    input_onesided=True, boundary=True)
        percussion[:, ch] = separated[:len(audio)]
    # Complementary residual ensures drums+percussion reconstruct the parent stem.
    drums_only = audio - percussion
    drums_file = output_dir / "drums_without_percussions.wav"
    percussion_file = output_dir / "percussions.wav"
    sf.write(str(drums_file), drums_only, rate, subtype="PCM_24")
    sf.write(str(percussion_file), percussion, rate, subtype="PCM_24")
    return drums_file, percussion_file



# Optional gated SAM Audio backend. It is intentionally isolated from the DAW's
# PyTorch runtime because SAM checkpoints and dependencies have separate constraints.
_SAM_AUDIO_MODELS = {"sam-audio-small", "sam-audio-base", "sam-audio-large"}
_PERCUSSION_METHODS = {"dsp", "drumsep-onnx", "sam-audio-small", "sam-audio-base", "sam-audio-large"}
_SAM_PROMPTS = {
    "percussions": "congas bongos shakers tambourines maracas cowbells claves hand percussion",
    "kick": "kick drum",
    "snare": "snare drum",
    "toms": "tom drums",
    "cymbals": "cymbals hi hats ride crash cymbals",
}


def _sam_audio_extract(source: Path, output_dir: Path, model_id: str, target: str, anchors: list | None = None) -> Path:
    from . import native_ai_routing as _remote
    if NATIVE_SINGLE_USER and _remote.is_remote('sam-audio'):
        result, _ = _native_remote_infer('sam-audio',source,{'model':model_id,'prompt':_SAM_PROMPTS.get(target,'singing voice'),'anchors':anchors or []})
        if len(result['audio'])!=1: raise ValueError('Remote SAM Audio must return one WAV')
        output_dir.mkdir(parents=True,exist_ok=True)
        destination=output_dir/(target+'.wav')
        destination.write_bytes(next(iter(result['audio'].values())))
        return destination
    """Run real SAM inference in an optional separate Python environment.

    The user must obtain licensed, gated checkpoints and install SAM themselves;
    no weights or Hugging Face credentials are bundled in the release.
    """
    import subprocess
    if model_id not in _SAM_AUDIO_MODELS or (target not in _SAM_PROMPTS and not re.fullmatch(r"singer_[1-8]", target)):
        raise ValueError("Unsupported SAM Audio model or instrument")
    python_binary = os.environ.get("MTA_SAM_AUDIO_PYTHON", "").strip()
    if not python_binary:
        raise RuntimeError("SAM Audio needs an isolated Python environment: set MTA_SAM_AUDIO_PYTHON to its Python executable and accept the checkpoint license on Hugging Face")
    runner = Path(__file__).with_name("sam_audio_worker.py")
    output_dir.mkdir(parents=True, exist_ok=True)
    result = output_dir / f"{target}.wav"
    args = [python_binary, str(runner), "--source", str(source), "--output", str(result), "--model", f"facebook/{model_id}", "--prompt", _SAM_PROMPTS.get(target, "singing voice")]
    if anchors:
        args.extend(["--anchors-json", json.dumps(anchors, separators=(",", ":"))])
    run = subprocess.run(args, capture_output=True, text=True, timeout=7200, check=False)
    if run.returncode != 0 or not result.is_file() or result.stat().st_size < 44:
        raise RuntimeError("SAM Audio inference failed: " + (run.stderr or run.stdout or "no WAV was generated")[-1600:])
    return result


def _requested_sam_target(target: str) -> str:
    return target if target in _SAM_PROMPTS else "percussions"

_STEM_TARGETS = {"all", "lead_vocals", "percussions", "drums_without_percussions", "other", "kick", "snare", "toms", "cymbals"}

_SINGER_MODEL_IDS = _SAM_AUDIO_MODELS


def _parse_singers_json(value: str, model: str, selected: str = "all") -> tuple[list[dict], str]:
    """Validate multiple singer anchors independently of the source format.

    Reference ranges are seconds measured from the beginning of the *original*
    track/song. Each range must contain primarily one singer. SAM uses the other
    singer ranges as negative anchors, reducing the risk of voice swaps.
    """
    if model not in _SINGER_MODEL_IDS:
        raise ValueError("Unsupported SAM Audio singer model")
    try:
        items = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid singer reference JSON") from exc
    if not isinstance(items, list) or not 2 <= len(items) <= 8:
        raise ValueError("Specify 2 to 8 singers with one solo reference interval each")
    names = set()
    result = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError("Invalid singer reference")
        name = str(item.get("name") or "").strip()
        if not 1 <= len(name) <= 80 or name.casefold() in names:
            raise ValueError("Singer names must be unique and 1-80 characters long")
        names.add(name.casefold())
        try:
            start = float(item["start"])
            end = float(item["end"])
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError("Singer reference must contain numeric start/end seconds") from exc
        if not (float("-inf") < start < float("inf") and float("-inf") < end < float("inf") and 0 <= start < end <= 86400 and 0.5 <= end - start <= 60):
            raise ValueError("Each singer needs a reference interval of 0.5-60 seconds")
        result.append({"id": f"singer_{index}", "name": name, "start": start, "end": end})
    for i, singer in enumerate(result):
        for other in result[i + 1:]:
            if singer["start"] < other["end"] and other["start"] < singer["end"]:
                raise ValueError("Solo singer reference intervals cannot overlap")
    allowed = {"all"} | {entry["id"] for entry in result}
    if selected not in allowed:
        raise ValueError("Selected singer is not defined")
    return result, selected


def _extract_singer_stems(source: Path, output_dir: Path, model: str, singers: list[dict], selected: str = "all") -> list[Path]:
    """Run singer-conditioned SAM span prompts independently at song time zero.

    This is experimental prompt-based separation, not the distinct Singer-Informed
    embedding model; independent targets can bleed into one another.
    """
    from . import native_ai_routing as _remote
    if NATIVE_SINGLE_USER and _remote.is_remote('singer-separation'):
        result,remote_id=_native_remote_infer('singer-separation',source,{'model':model,'singers':singers,'selected':selected})
        requested={person['id'] for person in singers if selected in ('all',person['id'])}
        output_dir.mkdir(parents=True,exist_ok=True)
        files=[]
        for singer_id in sorted(requested):
            data=next((wav for name,wav in result['audio'].items() if singer_id in name),None)
            if data is None: raise ValueError('Remote singer separation missing '+singer_id)
            dst=output_dir/singer_id/(singer_id+'.wav')
            dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes(data)
            files.append(dst)
        return files
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for singer in singers:
        if selected != "all" and selected != singer["id"]:
            continue
        anchors = [["+", singer["start"], singer["end"]]]
        anchors.extend(["-", other["start"], other["end"]] for other in singers if other["id"] != singer["id"])
        results.append(_sam_audio_extract(source, output_dir / singer["id"], model, singer["id"], anchors=anchors))
    return results



def _stem_split_worker(job_id: str, source: Path, keep_original_track: bool) -> None:
    with STEM_JOB_LOCK:
        job = STEM_JOBS[job_id]
        cancel_event = job["cancel_event"]
        project_id = job["project_id"]
        model = job["model"]
        estimate_project_bpm = bool(job.get("estimate_bpm"))
        stem_name_prefix = str(job.get("stem_name_prefix") or "").strip()
        extract_lyrics_after = bool(job.get("extract_lyrics"))
        extract_chords_after = bool(job.get("extract_chords"))
        split_backing_vocals = bool(job.get("split_backing_vocals"))
        stem_targets = set(job.get("stem_targets") or ["all"])
        percussion_method = str(job.get("percussion_method") or "dsp")
        split_percussions = bool(job.get("split_percussions")) or bool(stem_targets & {"percussions", "drums_without_percussions", "kick", "snare", "toms", "cymbals"})
        backing_vocal_model = str(job.get("backing_vocal_model") or LEAD_BACKING_DEFAULT_MODEL)
        singer_mode = bool(job.get("singer_mode"))
        singers = list(job.get("singers") or [])
        singer_model = str(job.get("singer_model") or "sam-audio-small")
        singer_target = str(job.get("singer_target") or "all")
        stem_count = int(job.get("stem_count") or 0)

    def progress(value: int, message: str) -> None:
        _stem_job_update(job_id, progress=max(1, min(99, int(value))), message=message)

    added_track_ids: list[str] = []
    added_files: list[Path] = []
    obsolete_files: list[Path] = []
    stems_published = False
    try:
        _stem_job_update(job_id, status="running", progress=12, message="Analisi del brano completo")
        ffprobe(source)
        if estimate_project_bpm:
            def bpm_progress(value: int, message: str) -> None:
                progress(12 + int(max(0, min(100, value)) * 0.12), message)
            try:
                estimated_bpm, estimated_signature = estimate_bpm_and_signature(source, bpm_progress)
                from .ai_project_lock import project_publication_lock
                with project_publication_lock(project_id):
                    project_for_bpm = load_project(project_id)
                    project_for_bpm.bpm = float(round(estimated_bpm))
                    project_for_bpm.time_signature = estimated_signature
                    project_for_bpm.base_bpm = project_for_bpm.bpm
                    save_project(project_for_bpm)
            except Exception:
                progress(24, "Stima BPM non conclusiva; continuo con il BPM corrente")
        if cancel_event.is_set():
            raise RuntimeError("stem separation cancelled")
        with tempfile.TemporaryDirectory(prefix=f"mta-stems-{job_id}-") as td_raw:
            td = Path(td_raw)
            from . import native_ai_routing as _native_ai
            if NATIVE_SINGLE_USER and _native_ai.is_remote('demucs'):
                result, remote_id = _native_remote_infer('demucs',source,{'model':model,'stem_count':stem_count})
                if not result['audio']:
                    raise ValueError('Remote Demucs returned no WAV stems')
                outdir=td/'stems';outdir.mkdir(parents=True,exist_ok=True)
                stems=[]
                for name, data in result['audio'].items():
                    target=outdir/Path(name).name.replace('stem_','',1)
                    target.write_bytes(data)
                    stems.append(target)
                _stem_job_update(job_id, remote_job_id=remote_id)
            else:
                stems = STEM_SPLITTER.split(
                    source,
                    td / "stems",
                    model=model,
                    stem_count=stem_count,
                    progress=progress,
                    cancel_event=cancel_event,
                )
            if cancel_event.is_set():
                raise RuntimeError("stem separation cancelled")
            vocal_split_method = None
            if singer_mode:
                vocal_stem = next((Path(stem) for stem in stems if Path(stem).stem.lower() in {"vocals", "vocal"}), None)
                if vocal_stem is None:
                    raise RuntimeError("Singer separation requires a vocals stem from Demucs")
                progress(85, f"Separazione di {len(singers)} cantanti con {singer_model}")
                # Time anchors are absolute with respect to the original track;
                # reject out-of-bounds references rather than silently extracting
                # the wrong singer.
                vocal_duration = media_duration_ms(vocal_stem) / 1000.0
                if any(singer["end"] > vocal_duration + 0.2 for singer in singers):
                    raise RuntimeError("Singer reference interval exceeds the source audio duration")
                singer_outputs = _extract_singer_stems(vocal_stem, td / "singers", singer_model, singers, singer_target)
                # A singer-specific run imports ONLY the requested voice. An all-
                # singers run replaces Vocals but retains the instrumental stems.
                stems = ([stem for stem in stems if Path(stem) != vocal_stem] if singer_target == "all" else []) + singer_outputs
            if (not singer_mode) and (split_backing_vocals or "lead_vocals" in stem_targets):
                vocal_stem = next((Path(stem) for stem in stems if Path(stem).stem.lower() in {"vocals", "vocal"}), None)
                if vocal_stem is None:
                    raise RuntimeError("Il modello selezionato non ha prodotto uno stem vocals da separare")
                method_label = ("DSP FFmpeg center/side" if backing_vocal_model == "ffmpeg-center-side"
                                else next((x["display_name"] for x in LEAD_BACKING_MODELS if x["id"] == backing_vocal_model), backing_vocal_model))
                progress(86, f"Separazione lead/backing vocals: {method_label}")
                lead_vocal, backing_vocal, vocal_split_method = _split_lead_backing_vocals(
                    vocal_stem, td / "lead-backing", model_id=backing_vocal_model, cancel_event=cancel_event
                )
                stems = [stem for stem in stems if Path(stem) != vocal_stem] + [lead_vocal, backing_vocal]
                _stem_job_update(job_id, vocal_split_method=vocal_split_method)
            if split_percussions:
                drums_stem = next((Path(stem) for stem in stems if Path(stem).stem.lower() == "drums"), None)
                if drums_stem is None:
                    raise RuntimeError("The selected model did not produce a drums stem")
                if percussion_method not in _PERCUSSION_METHODS:
                    raise RuntimeError("Unsupported percussion separation method")
                progress(87, f"Separating drums/percussions with {percussion_method}")
                if percussion_method == "dsp":
                    if stem_targets & {"kick", "snare", "toms", "cymbals"}:
                        raise RuntimeError("Individual kit elements need SAM Audio; DSP only supports drums/percussions")
                    drum_body, percussion = _split_drums_percussions(drums_stem, td / "drums-percussions")
                    stems = [stem for stem in stems if Path(stem) != drums_stem] + [drum_body, percussion]
                elif percussion_method == "drumsep-onnx":
                    # DrumSep only separates the kit. Non-kit percussions need SAM Audio.
                    if "percussions" in stem_targets or "all" in stem_targets:
                        raise RuntimeError("DrumSep extracts kick, snare, toms and cymbals only. For non-kit percussions select SAM Audio as the percussion method.")
                    results = _drumsep_extract(drums_stem, td / "drumsep", stem_targets | ({"all"} if "drums_without_percussions" in stem_targets else set()))
                    if "drums_without_percussions" in stem_targets:
                        # The kit is the sum of the four specialised DrumSep outputs,
                        # not an unchanged copy of the Demucs drums stem.
                        import soundfile as _sf
                        import numpy as _np
                        kit_parts = []
                        for instrument in ("kick", "snare", "cymbals", "toms"):
                            sound, sr = _sf.read(td / "drumsep" / f"{instrument}.wav", dtype="float32", always_2d=True)
                            kit_parts.append(sound)
                        kit_path = td / "drumsep" / "drums_without_percussions.wav"
                        _sf.write(kit_path, _np.sum(kit_parts, axis=0), sr, subtype="PCM_24")
                        results.append(kit_path)
                    stems = [stem for stem in stems if Path(stem) != drums_stem] + results
                else:
                    # Non-kit percussion is prompted against the original mix,
                    # not the Demucs drums stem (which may exclude hand percussion).
                    instrument_targets = ({"percussions", "kick", "snare", "toms", "cymbals"} if "all" in stem_targets else stem_targets & {"percussions", "kick", "snare", "toms", "cymbals"})
                    results = []
                    for target in sorted(instrument_targets):
                        input_audio = source if target == "percussions" else drums_stem
                        results.append(_sam_audio_extract(input_audio, td / "sam-audio" / target, percussion_method, target))
                    if "drums_without_percussions" in stem_targets or "all" in stem_targets:
                        # Demucs drums is the core drum kit. SAM non-kit percussion
                        # cannot be assumed to live entirely inside this stem.
                        kit_path = td / "sam-audio" / "drums_without_percussions.wav"
                        kit_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(drums_stem, kit_path)
                        results.append(kit_path)
                    stems = [stem for stem in stems if Path(stem) != drums_stem] + results
            if "all" not in stem_targets and not singer_mode:
                stems = [stem for stem in stems if Path(stem).stem.lower() in stem_targets]
                if not stems:
                    raise RuntimeError("The separation model produced none of the requested stems")
            progress(90, "Importazione delle tracce nel progetto")
            from .ai_project_lock import project_publication_lock
            with project_publication_lock(project_id):
                project = load_project(project_id)
                mapping = {
                    "drums": "drums",
                    "bass": "bass",
                    "guitar": "guitars",
                    "piano": "keyboards",
                    "vocals": "melody",
                    "lead_vocals": "melody",
                    "backing_vocals": "melody",
                    "percussions": "drums",
                    "drums_without_percussions": "drums",
                    "kick": "drums", "snare": "drums", "toms": "drums", "cymbals": "drums",
                    "other": "other",
                }
                for index, stem in enumerate(stems, start=1):
                    if cancel_event.is_set():
                        raise RuntimeError("stem separation cancelled")
                    stem_name = stem.stem.lower()
                    kind = "melody" if stem_name.startswith("singer_") else mapping.get(stem_name, "other")
                    filename = f"{uuid.uuid4().hex[:10]}.wav"
                    dst = audio_path(project.id, filename)
                    # Register the new asset before copying or converting it: a
                    # failed conversion must not leave an untracked audio orphan.
                    added_files.append(dst)
                    shutil.copyfile(stem, dst)
                    filename, dst, _ = _normalize_audio_to_project_rate(project.id, filename, project.sample_rate, strict=False)
                    if dst not in added_files:
                        added_files.append(dst)
                    duration = media_duration_ms(dst)
                    channels, channel_layout = _audio_channel_info(dst)
                    display_name = {"lead_vocals": "Lead Vocals", "backing_vocals": "Backing Vocals", "percussions": "Percussions", "drums_without_percussions": "Drums (no percussions)", "kick": "Kick", "snare": "Snare", "toms": "Toms", "cymbals": "Cymbals"}.get(stem_name, stem.stem.title())
                    if stem_name.startswith("singer_"):
                        display_name = next((entry["name"] for entry in singers if entry["id"] == stem_name), display_name)
                    if stem_name_prefix:
                        display_name = f"{stem_name_prefix} · {display_name}"[:200]
                    new_track = Track(
                            id=uuid.uuid4().hex[:10],
                            name=display_name,
                            type=kind,
                            filename=filename,
                            duration_ms=duration,
                            channels=channels,
                            channel_layout=channel_layout,
                            sample_rate=int(project.sample_rate),
                            clips=[
                                Clip(
                                    id=uuid.uuid4().hex[:10],
                                    source_start_ms=0,
                                    source_end_ms=duration,
                                    timeline_start_ms=0,
                                )
                            ],
                        )
                    # Selective repeat runs replace the matching derived stem instead
                    # of duplicating it. Preserve its identity and mixer settings.
                    original_track_id = str(job.get("source_track_id") or "")
                    existing_output = None
                    if original_track_id and ("all" not in stem_targets or (singer_mode and singer_target != "all")):
                        existing_output = next((item for item in project.tracks
                            if item.id != original_track_id and item.name == display_name), None)
                    if existing_output is not None:
                        old_filename = existing_output.filename
                        existing_output.filename = new_track.filename
                        existing_output.duration_ms = new_track.duration_ms
                        existing_output.channels = new_track.channels
                        existing_output.channel_layout = new_track.channel_layout
                        existing_output.sample_rate = new_track.sample_rate
                        existing_output.clips = new_track.clips
                        if old_filename and old_filename != filename:
                            obsolete_files.append(audio_path(project.id, old_filename))
                    else:
                        project.tracks.append(new_track)
                        added_track_ids.append(new_track.id)
                    progress(90 + int(index / max(1, len(stems)) * 8), f"Preparata traccia {stem.stem.title()}")

                # All audio assets are prepared before the project references any of
                # them. One atomic project.json replacement publishes the entire stem
                # batch, never an observable prefix of the tracks.
                if cancel_event.is_set():
                    raise RuntimeError("stem separation cancelled")
                save_project(project)
                stems_published = True
            # A completed project.json is authoritative. Enqueue old sources
            # for durable GC rather than unlinking them in the request thread.
            # In FLAC mode save_project may also rewrite filenames: GC checks
            # the final on-disk project before removing any candidate.
            if obsolete_files:
                schedule_project_gc(project_id, {path.name for path in obsolete_files})

            # Optional musical-text analysis is intentionally non-fatal: a successful
            # stem separation must remain usable even if Whisper/Chordino is unavailable.
            analysis: dict[str, dict[str, object]] = {}
            if extract_lyrics_after:
                progress(98, "Estrazione lyrics ad alta accuratezza")
                vocal_stem = next((Path(stem) for stem in stems if Path(stem).stem.lower() in {"vocals", "vocal"}), None)
                lyric_source = vocal_stem or source
                try:
                    selected_lyrics_model = str(job.get("lyrics_model") or lyrics_catalog(native=NATIVE_SINGLE_USER)["default_model"])
                    # Inference happens outside the project publication lock. The
                    # commit reloads the latest state and refuses to overwrite
                    # lyrics modified while the model was running.
                    from .models import LyricLine
                    if NATIVE_SINGLE_USER and _native_ai.is_remote('whisper'):
                        remote_result, remote_id = _native_remote_infer('whisper', lyric_source, {'model': selected_lyrics_model})
                        remote_doc = remote_result['json'].get('transcript.json', {})
                        if not isinstance(remote_doc.get('lines'), list):
                            raise ValueError('Remote transcript not returned')
                        extracted_lyrics = [LyricLine.model_validate(item) for item in remote_doc['lines']]
                        analysis.setdefault('remote_jobs', {})['whisper'] = remote_id
                    else:
                        extracted_lyrics = extract_lyrics(lyric_source, model_name=selected_lyrics_model)
                    from .ai_project_lock import project_publication_lock
                    with project_publication_lock(project_id):
                        project = load_project(project_id)
                        if project.lyrics:
                            raise RuntimeError('Lyrics changed during analysis; existing lyrics preserved')
                        project.lyrics = extracted_lyrics
                        project.lyrics_engine = 'OpenAI Whisper'
                        project.lyrics_model = selected_lyrics_model
                        save_project(project)
                    analysis['lyrics'] = {'ok': True, 'count': len(extracted_lyrics), 'source': 'vocals' if vocal_stem else 'mix', 'engine': 'OpenAI Whisper', 'model': selected_lyrics_model}
                except Exception as analysis_exc:
                    LOGGER.exception('Lyrics extraction after stem separation failed')
                    analysis['lyrics'] = {'ok': False, 'error': str(analysis_exc)[-500:]}
                _stem_job_update(job_id, analysis=dict(analysis))
            if extract_chords_after:
                progress(99, 'Analisi chords ad alta accuratezza')
                try:
                    selected_chords_engine = str(job.get('chords_engine') or chords_catalog(native=NATIVE_SINGLE_USER)['default_engine'])
                    chord_info = next((x for x in chords_catalog(native=NATIVE_SINGLE_USER)['engines'] if x['id'] == selected_chords_engine), {})
                    from .models import Chord
                    if NATIVE_SINGLE_USER and _native_ai.is_remote('chords-ml'):
                        remote_result, remote_id = _native_remote_infer('chords-ml', source, {'engine': selected_chords_engine})
                        remote_doc = remote_result['json'].get('chords.json', {})
                        if not isinstance(remote_doc.get('chords'), list):
                            raise ValueError('Remote chords not returned')
                        extracted_chords = [Chord.model_validate(item) for item in remote_doc['chords']]
                        analysis.setdefault('remote_jobs', {})['chords-ml'] = remote_id
                    else:
                        extracted_chords = extract_chords(source, engine=selected_chords_engine)
                    from .ai_project_lock import project_publication_lock
                    with project_publication_lock(project_id):
                        project = load_project(project_id)
                        if project.chords:
                            raise RuntimeError('Chords changed during analysis; existing chords preserved')
                        project.chords = extracted_chords
                        project.chords_engine = selected_chords_engine
                        project.chords_model = str(chord_info.get('model_id') or '')
                        save_project(project)
                    analysis['chords'] = {'ok': True, 'count': len(extracted_chords), 'source': 'mix', 'engine': selected_chords_engine, 'model': str(chord_info.get('model_id') or ''), 'engine_display_name': chord_info.get('display_name', selected_chords_engine)}
                except Exception as analysis_exc:
                    LOGGER.exception('Chord extraction after stem separation failed')
                    analysis['chords'] = {'ok': False, 'error': str(analysis_exc)[-500:]}
                _stem_job_update(job_id, analysis=dict(analysis))
        if not keep_original_track:
            source.unlink(missing_ok=True)
        _stem_job_update(job_id, status="completed", progress=100, message="Separazione completata")
    except Exception as exc:
        # Before publication, no track reference has changed. Deleting only
        # newly staged files preserves existing tracks and their mixer settings.
        # After publication, never roll back an already-visible batch because
        # optional enrichment or a late cancellation failed.
        if not stems_published:
            # Failed staging can leave both the original WAV and its converted
            # counterpart. Queue anything we know about for crash-safe GC; the
            # GC always rechecks live project references before deleting.
            abandoned = {path.name for path in added_files}
            if abandoned:
                schedule_project_gc(project_id, abandoned)
        if (cancel_event.is_set() or "cancelled" in str(exc).lower()) and not stems_published:
            _stem_job_update(job_id, status="cancelled", progress=0, message="Separazione annullata", error=None)
        else:
            LOGGER.exception("Stem separation job %s failed", job_id)
            _stem_job_update(job_id, status="failed", progress=0, message="Separazione fallita", error=str(exc)[-1200:])



def _mobile_demucs_inventory(directory: Path, extension: str, route_prefix: str) -> tuple[list[int], dict[str, dict[str, object]]]:
    """Discover every valid demucs-N model instead of assuming 2/4/6/8."""
    available: list[int] = []
    models: dict[str, dict[str, object]] = {}
    if not directory.is_dir():
        return available, models
    pattern = re.compile(rf"^demucs-(\d+)\{extension}$")
    for model in sorted(directory.glob(f"demucs-*{extension}")):
        match = pattern.match(model.name)
        if not match:
            continue
        count = int(match.group(1))
        if count < 2 or count > 64:
            continue
        payload = model.read_bytes()
        available.append(count)
        meta_path = model.with_suffix(model.suffix + ".json")
        metadata: dict[str, object] = {}
        if meta_path.is_file():
            try:
                parsed = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    metadata = parsed
            except (OSError, ValueError):
                pass
        model_id = str(metadata.get("id") or metadata.get("model") or f"demucs-{count}")
        if model_id in demucs_blacklist():
            continue
        models[str(count)] = {
            "id": model_id,
            "stem_count": count,
            "filename": model.name,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
            "updated_at": int(model.stat().st_mtime),
            "url": f"{route_prefix}/{count}",
            "version": str(metadata.get("version", "")),
            "stem_labels": metadata.get("stem_labels", []),
        }
    return sorted(set(available)), models


@app.get("/api/mobile/demucs-coreml/status")
def mobile_demucs_coreml_status(request: Request):
    _actor(request)
    available, models = _mobile_demucs_inventory(COREML_DEMUCS_MODEL_DIR, ".mlmodel", "/api/mobile/demucs-coreml/models")
    return {
        "available_stem_counts": available,
        "default_stem_count": 4,
        "models": models,
        "format": "CoreML mlmodel",
        "runtime": "on-device",
        "model_driven": True,
        "max_stem_count": max(available, default=4),
    }


@app.get("/api/mobile/demucs-coreml/bootstrap")
def mobile_demucs_coreml_bootstrap(request: Request):
    """Authenticated baseline model used to bootstrap iOS/iPadOS local separation.

    Only the configured 4-stem baseline is exposed here. Server-side model
    inventory and optional 2/6/8-stem models remain authenticated.
    """
    require_model_read(request)
    if not COREML_DEMUCS_MODEL_DIR:
        raise HTTPException(404, "Repository modelli Core ML non configurato")
    model = COREML_DEMUCS_MODEL_DIR / "demucs-4.mlmodel"
    if not model.is_file():
        raise HTTPException(404, "Modello locale predefinito non disponibile")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    return FileResponse(
        model,
        media_type="application/octet-stream",
        filename="demucs-default-4.mlmodel",
        headers={"X-MTA-Model-SHA256": digest, "Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/mobile/demucs-coreml/models/{stem_count}")
def mobile_demucs_coreml_model(stem_count: int, request: Request):
    require_model_read(request)
    if stem_count < 2 or stem_count > 64:
        raise HTTPException(404, "Modello locale non disponibile")
    if not COREML_DEMUCS_MODEL_DIR:
        raise HTTPException(404, "Repository modelli Core ML non configurato")
    model = COREML_DEMUCS_MODEL_DIR / f"demucs-{stem_count}.mlmodel"
    if not model.is_file():
        raise HTTPException(404, "Modello locale non disponibile")
    return FileResponse(model, media_type="application/octet-stream", filename=model.name)


@app.get("/api/mobile/demucs-onnx/status")
def mobile_demucs_onnx_status(request: Request):
    _actor(request)
    available, models = _mobile_demucs_inventory(ONNX_DEMUCS_MODEL_DIR, ".onnx", "/api/mobile/demucs-onnx/models")
    return {"available_stem_counts": available, "default_stem_count": 4, "models": models, "format": "ONNX", "runtime": "on-device", "model_driven": True, "max_stem_count": max(available, default=4)}


@app.get("/api/mobile/demucs-onnx/bootstrap")
def mobile_demucs_onnx_bootstrap(request: Request):
    require_model_read(request)
    model=ONNX_DEMUCS_MODEL_DIR/"demucs-4.onnx"
    if not model.is_file(): raise HTTPException(404,"Modello Android locale predefinito non disponibile")
    digest=hashlib.sha256(model.read_bytes()).hexdigest()
    return FileResponse(model,media_type="application/octet-stream",filename="demucs-default-4.onnx",headers={"X-MTA-Model-SHA256":digest,"Cache-Control":"public, max-age=3600"})

@app.get("/api/mobile/demucs-onnx/models/{stem_count}")
def mobile_demucs_onnx_model(stem_count:int,request:Request):
    require_model_read(request)
    if stem_count < 2 or stem_count > 64: raise HTTPException(404,"Modello locale non disponibile")
    model=ONNX_DEMUCS_MODEL_DIR/f"demucs-{stem_count}.onnx"
    if not model.is_file(): raise HTTPException(404,"Modello locale non disponibile")
    return FileResponse(model,media_type="application/octet-stream",filename=model.name)

@app.post("/api/models/token")
def issue_model_access_token(request: Request):
    user = require_user(request)
    label = request.headers.get("x-mta-client", "client")[:120]
    return create_model_access_token(int(user["id"]), label=label, scopes=("models:read",))


@app.delete("/api/models/tokens")
def revoke_my_model_access_tokens(request: Request):
    user = require_user(request)
    return {"ok": True, "revoked": revoke_model_access_tokens(int(user["id"]))}


@app.get("/api/models/catalog")
def demucs_model_catalog(platform: str = ""):
    return demucs_public_catalog(platform or None)

@app.get("/api/models/native/{model_id}")
def demucs_native_model_download(model_id: str, request: Request):
    require_model_read(request)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", model_id) or model_id in demucs_blacklist():
        raise HTTPException(404, "Model unavailable")
    bundle = demucs_native_bundle(model_id)
    if bundle is None:
        # Requesting a model also acts as an on-demand server refresh.
        update_mobile_demucs_models({model_id}, force=False)
        bundle = demucs_native_bundle(model_id)
    if bundle is None:
        raise HTTPException(404, "Native model bundle unavailable")
    return FileResponse(bundle, media_type="application/zip", filename=bundle.name)

@app.get("/api/models/coreml/{model_id}")
def demucs_coreml_model_by_id(model_id: str, request: Request):
    require_model_read(request)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", model_id) or model_id in demucs_blacklist(): raise HTTPException(404,"Model unavailable")
    for item in demucs_public_catalog("ios").get("models",[]):
        if item.get("id") == model_id:
            from .model_updater import COREML_DIR
            candidates=list(COREML_DIR.glob(f"{model_id}.mlmodel"))
            if not candidates: update_mobile_demucs_models({model_id}, force=False); candidates=list(COREML_DIR.glob(f"{model_id}.mlmodel"))
            if candidates:return FileResponse(candidates[0],media_type="application/octet-stream",filename=candidates[0].name)
    raise HTTPException(404,"Model unavailable")

@app.get("/api/models/onnx/{model_id}")
def demucs_onnx_model_by_id(model_id: str, request: Request):
    require_model_read(request)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", model_id) or model_id in demucs_blacklist(): raise HTTPException(404,"Model unavailable")
    for item in demucs_public_catalog("android").get("models",[]):
        if item.get("id") == model_id:
            from .model_updater import ONNX_DIR
            candidates=list(ONNX_DIR.glob(f"{model_id}.onnx"))
            if not candidates:update_mobile_demucs_models({model_id},force=False);candidates=list(ONNX_DIR.glob(f"{model_id}.onnx"))
            if candidates:return FileResponse(candidates[0],media_type="application/octet-stream",filename=candidates[0].name)
    raise HTTPException(404,"Model unavailable")

@app.post("/api/admin/demucs-mobile-models/update")
def admin_update_demucs_mobile_models(request:Request):
    require_admin(request)
    return update_mobile_demucs_models()

@app.get("/api/admin/demucs-models")
def admin_demucs_models(request: Request):
    require_admin(request)
    return demucs_server_inventory()

@app.post("/api/admin/demucs-models/update")
def admin_demucs_models_update(request: Request):
    require_admin(request)
    return update_mobile_demucs_models(force=True, prefetch_server=True)

@app.post("/api/admin/demucs-models/{model_id}/update")
def admin_demucs_model_update(model_id: str, request: Request):
    require_admin(request)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", model_id):
        raise HTTPException(400, "Invalid model id")
    return update_mobile_demucs_models({model_id}, force=True, prefetch_server=True)

@app.post("/api/admin/demucs-models/{model_id}/blacklist")
def admin_demucs_model_blacklist(model_id: str, request: Request):
    require_admin(request)
    return blacklist_demucs_model(model_id)

@app.delete("/api/admin/demucs-models/{model_id}/blacklist")
def admin_demucs_model_unblacklist(model_id: str, request: Request):
    require_admin(request)
    return unblacklist_demucs_model(model_id)


@app.delete("/api/admin/demucs-models/{model_id}/local")
def admin_demucs_model_delete_local(model_id: str, request: Request):
    require_admin(request)
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", model_id):
        raise HTTPException(400, "Invalid model id")
    return delete_local_demucs_model(model_id)


@app.get("/api/ai-models")
def managed_ai_models(request: Request):
    _actor(request)
    return ai_catalog(native=NATIVE_SINGLE_USER)

@app.post("/api/ai-models/lyrics/{model_id}/download")
def managed_lyrics_model_download(model_id: str, request: Request):
    _actor(request)
    try: return download_lyrics_model(model_id, native=NATIVE_SINGLE_USER)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Lyrics model download failed")
        raise HTTPException(502, f"Download modello lyrics fallito: {exc}") from exc

def _ai_model_download_worker(job_id: str, kind: str, model_id: str) -> None:
    try:
        _media_job_update(job_id,status="running",progress=8,message="Preparazione download modello")
        if kind=="lyrics":
            _media_job_update(job_id,progress=-1,message="Download / verifica modello Whisper")
            result=download_lyrics_model(model_id,native=NATIVE_SINGLE_USER)
        else:
            _media_job_update(job_id,progress=-1,message="Download / verifica modello Chords")
            result=download_chord_model(model_id,native=NATIVE_SINGLE_USER)
        _media_job_update(job_id,status="completed",progress=100,message="Modello pronto",result=result)
    except Exception as exc:
        LOGGER.exception("AI model download job %s failed",job_id)
        _media_job_update(job_id,status="failed",progress=0,message="Download modello fallito",error=str(exc)[-1200:])


def _restore_model_download_job(pid, payload, job_id):
    """Recover queued catalog downloads without replaying interrupted work."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("Unsupported model download payload")
    kind, model_id = payload.get("kind"), payload.get("model_id")
    if kind not in ("lyrics", "chords") or pid != "server-models":
        raise ValueError("Invalid model download operation")
    if not isinstance(model_id, str) or not re.fullmatch(r"[A-Za-z0-9._/-]{1,128}", model_id):
        raise ValueError("Invalid model download id")
    operation = "download-" + kind + "-model"
    catalog = lyrics_catalog if kind == "lyrics" else chords_catalog
    if not any(item.get("id") == model_id for item in catalog(native=NATIVE_SINGLE_USER).get("models", [])):
        raise ValueError("Model no longer exists in catalog")
    now = time.time()
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.setdefault(job_id, {
            "id": job_id, "kind": operation, "project_id": None,
            "status": "queued", "progress": 3, "message": "Recovered queued model download",
            "created_at": now, "updated_at": now, "result": None,
            "error": None, "cancel_event": threading.Event(),
        })
    def execute(_progress_path, stop):
        job["cancel_event"] = stop
        if stop.is_set():
            job["status"] = "cancelled"
            return
        _ai_model_download_worker(job_id, kind, model_id)
        if job.get("status") == "failed":
            raise RuntimeError(str(job.get("error") or "Model download failed")[:300])
    return execute


for _download_kind in ("lyrics", "chords"):
    ai_arranger_runtime.register_restorer("download-" + _download_kind + "-model", _restore_model_download_job)


def _start_ai_model_download_job(kind: str, model_id: str, request: Request):
    _actor(request)
    now=time.time();job_id=uuid.uuid4().hex[:16]
    job={"id":job_id,"kind":f"download-{kind}-model","project_id":None,"status":"queued","progress":3,"message":"Download modello in coda","created_at":now,"updated_at":now,"result":None,"error":None,"cancel_event":threading.Event()}
    with MEDIA_JOB_LOCK: MEDIA_JOBS[job_id]=job
    _enqueue_existing_ai_job(job, lambda: _ai_model_download_worker(job_id,kind,model_id),
        durable_payload={"schema_version":1,"kind":kind,"model_id":model_id})
    return _media_job_public(job)


@app.post("/api/ai-models/lyrics/{model_id}/download-jobs")
def managed_lyrics_model_download_job(model_id: str, request: Request):
    if not any(x["id"]==model_id for x in lyrics_catalog(native=NATIVE_SINGLE_USER)["models"]):
        raise HTTPException(404,"unsupported lyrics model")
    return _start_ai_model_download_job("lyrics",model_id,request)


@app.post("/api/ai-models/chords/{model_id}/download-jobs")
def managed_chord_model_download_job(model_id: str, request: Request):
    if not any(x["id"]==model_id for x in chords_catalog(native=NATIVE_SINGLE_USER)["models"]):
        raise HTTPException(404,"unsupported chord model")
    return _start_ai_model_download_job("chords",model_id,request)


@app.delete("/api/ai-models/lyrics/{model_id}")
def managed_lyrics_model_delete(model_id: str, request: Request):
    _actor(request)
    try: return delete_lyrics_model(model_id, native=NATIVE_SINGLE_USER)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc

@app.post("/api/ai-models/chords/{model_id}/download")
def managed_chord_model_download(model_id: str, request: Request):
    _actor(request)
    try: return download_chord_model(model_id, native=NATIVE_SINGLE_USER)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        LOGGER.exception("Chords model download failed")
        raise HTTPException(502, f"Download modello chords fallito: {exc}") from exc

@app.delete("/api/ai-models/chords/{model_id}")
def managed_chord_model_delete(model_id: str, request: Request):
    _actor(request)
    try: return delete_chord_model(model_id, native=NATIVE_SINGLE_USER)
    except ValueError as exc: raise HTTPException(404, str(exc)) from exc



# DrumSep ONNX: optional local 4-stem separation, no SAM/CUDA dependency.
_DRUMSEP_URL = "https://huggingface.co/gridshiftstudio/drumsep-onnx/resolve/main/drumsep.onnx"
_DRUMSEP_SHA256 = "ecb8509383ccd437d84e12c216b002a00a2d4e88601e29f2711ea581f207c92a"
_DRUMSEP_DIR = Path(os.getenv("MTA_DRUMSEP_MODEL_DIR", str(STORAGE_ROOT / ".cache" / "drumsep-models"))).expanduser().resolve()
_DRUMSEP_PATH = _DRUMSEP_DIR / "drumsep.onnx"


def _drumsep_catalog() -> dict:
    return {"id": "drumsep-onnx", "name": "DrumSep ONNX (Kick/Snare/Cymbals/Toms)",
            "path": str(_DRUMSEP_PATH), "installed": _DRUMSEP_PATH.is_file(),
            "size_bytes": _DRUMSEP_PATH.stat().st_size if _DRUMSEP_PATH.is_file() else 0,
            "source": _DRUMSEP_URL, "sha256": _DRUMSEP_SHA256,
            "location": "local" if NATIVE_SINGLE_USER else "server"}


def _download_drumsep_model() -> dict:
    _DRUMSEP_DIR.mkdir(parents=True, exist_ok=True)
    import tempfile as _tmp
    fd, name = _tmp.mkstemp(prefix=".drumsep-", suffix=".onnx", dir=str(_DRUMSEP_DIR))
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as output, https_urlopen(_DRUMSEP_URL, timeout=60) as response:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk: break
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if digest.hexdigest() != _DRUMSEP_SHA256:
            raise RuntimeError("DrumSep download SHA256 mismatch")
        os.replace(name, _DRUMSEP_PATH)
    finally:
        Path(name).unlink(missing_ok=True)
    return _drumsep_catalog()


def _drumsep_extract(source: Path, output_dir: Path, targets: set[str]) -> list[Path]:
    from . import native_ai_routing as _remote
    if NATIVE_SINGLE_USER and _remote.is_remote('drumsep'):
        result, _ = _native_remote_infer('drumsep',source,{'targets':sorted(targets)})
        if not result['audio']: raise ValueError('Remote DrumSep returned no WAV stems')
        output_dir.mkdir(parents=True,exist_ok=True)
        files=[]
        for name,data in result['audio'].items():
            stem=next((item for item in ('kick','snare','toms','cymbals') if item in name.lower()),None)
            if stem and ('all' in targets or stem in targets):
                dest=output_dir/(stem+'.wav');dest.write_bytes(data);files.append(dest)
        if not files: raise ValueError('No requested DrumSep stems returned')
        return files
    """Execute validated DrumSep ONNX adapter in a worker; input is Demucs drums."""
    import sys
    output_dir.mkdir(parents=True, exist_ok=True)
    if not _DRUMSEP_PATH.is_file():
        raise RuntimeError(f"DrumSep ONNX not installed: {_DRUMSEP_PATH}. Download it in Models first.")
    runner = Path(__file__).with_name("drumsep_onnx_worker.py")
    args = [sys.executable, str(runner), "--source", str(source), "--output", str(output_dir),
            "--model", str(_DRUMSEP_PATH)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=7200, check=False)
    if result.returncode:
        raise RuntimeError("DrumSep ONNX failed: " + (result.stderr or result.stdout)[-1600:])
    return [output_dir / f"{stem}.wav" for stem in ("kick", "snare", "toms", "cymbals")
            if ("all" in targets or stem in targets) and (output_dir / f"{stem}.wav").is_file()]


@app.get("/api/drumsep/models")
def drumsep_models(request: Request):
    _actor(request)
    return _drumsep_catalog()


@app.post("/api/drumsep/models/download")
def drumsep_model_download(request: Request):
    _actor(request)
    try: return _download_drumsep_model()
    except Exception as exc: raise HTTPException(503, str(exc)) from exc


@app.delete("/api/drumsep/models")
def drumsep_model_delete(request: Request):
    _actor(request)
    _DRUMSEP_PATH.unlink(missing_ok=True)
    return _drumsep_catalog()

@app.get("/api/vocal-separation/models")
def lead_backing_models(request: Request):
    _actor(request)
    return _lead_backing_catalog()

@app.delete("/api/vocal-separation/models/{model_id}")
def lead_backing_model_delete(model_id: str, request: Request):
    _actor(request)
    try:
        info = _lead_backing_model_info(model_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    # Only remove known files within the dedicated model directory.
    path = LEAD_BACKING_MODEL_DIR / info["filename"]
    path.unlink(missing_ok=True)
    return {"ok": True, "model": model_id, "path": str(path)}

@app.post("/api/vocal-separation/models/{model_id}/download")
def lead_backing_model_download(model_id: str, request: Request):
    _actor(request)
    try:
        return _download_lead_backing_model(model_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

@app.post("/api/stems/jobs")
async def stem_job_start(
    request: Request,
    file: UploadFile = File(...),
    project_id: str = "",
    project_title: str = "",
    target: str = "MTA8",
    model: str = "htdemucs_6s",
    stem_count: int = 0,
    keep_original_track: bool = True,
    extract_lyrics: bool = False,
    extract_chords: bool = False,
    lyrics_model: str = "",
    chords_engine: str = "",
    split_backing_vocals: bool = False,
    backing_vocal_model: str = LEAD_BACKING_DEFAULT_MODEL,
    split_percussions: bool = False,
    percussion_method: str = "dsp",
    stem_targets: str = "all",
    singers_json: str = "",
    singer_model: str = "sam-audio-small",
    singer_target: str = "all",
):
    requested_targets = {value.strip().lower() for value in stem_targets.split(",") if value.strip()}
    if not requested_targets or not requested_targets <= _STEM_TARGETS or ("all" in requested_targets and len(requested_targets) > 1):
        raise HTTPException(400, "Invalid stem selection")
    if singers_json:
        try:
            singers, singer_target = _parse_singers_json(singers_json, singer_model, singer_target)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if requested_targets != {"all"} or split_backing_vocals or split_percussions:
            raise HTTPException(400, "Singer separation cannot be combined with other selective splitting")
    else:
        singers = []
    if "lead_vocals" in requested_targets:
        split_backing_vocals = True
    if requested_targets & {"percussions", "drums_without_percussions", "kick", "snare", "toms", "cymbals"}:
        split_percussions = True
    if percussion_method not in _PERCUSSION_METHODS:
        raise HTTPException(400, "Unknown percussion model")
    if Path(file.filename or "").suffix.lower() != ".mp3":
        raise HTTPException(400, "La separazione strumenti accetta attualmente file MP3.")
    from . import native_ai_routing as _native_ai
    remote_demucs = NATIVE_SINGLE_USER and _native_ai.is_remote('demucs')
    if not remote_demucs and not STEM_SPLITTER.available():
        raise HTTPException(503, "Il plugin Demucs non è installato in questo runtime.")
    status = STEM_SPLITTER.status()
    supported_counts = [int(value) for value in status.get("supported_stem_counts", [])]
    if stem_count != 0 and (stem_count < 2 or stem_count > 64):
        raise HTTPException(400, "Numero di stem non valido. Usa Auto oppure una cardinalità tra 2 e 64.")
    if stem_count and stem_count not in supported_counts and not remote_demucs:
        raise HTTPException(400, f"Nessun modello configurato fornisce {stem_count} stem.")
    if stem_count == 2:
        model = "htdemucs" if model not in {"htdemucs", "htdemucs_ft"} else model
    elif stem_count:
        profiles = [item for item in status.get("model_profiles", []) if int(item.get("stem_count", 0)) == stem_count]
        if profiles and (model not in status["models"] or next((int(item.get("stem_count", 0)) for item in status.get("model_profiles", []) if item.get("model") == model), -1) != stem_count):
            model = str(profiles[0]["model"])
    if model not in status["models"] and not remote_demucs:
        raise HTTPException(400, "Modello di separazione non supportato.")

    if split_backing_vocals and backing_vocal_model != "ffmpeg-center-side":
        try:
            _lead_backing_model_info(backing_vocal_model)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    actor = _actor(request)
    if project_id:
        project = _project_for_actor(request, project_id)
        _ensure_workspace_capacity(project.owner_user_id, int(request.headers.get("content-length") or 0))
    else:
        title = (project_title.strip() or Path(file.filename or "Nuovo progetto").stem)[:200]
        project = create_project(
            title,
            target if target in {"MTA8", "MTA16", "DAW"} else "MTA8",
            owner_user_id=actor["id"] if actor["id"] > 0 else None,
        )

    with STEM_JOB_LOCK:
        busy = any(
            item["project_id"] == project.id and item["status"] not in {"completed", "failed", "cancelled"}
            for item in STEM_JOBS.values()
        )
    if busy:
        raise HTTPException(409, "È già in corso una separazione strumenti per questo progetto.")

    estimate_bpm_for_project = len(project.tracks) == 0

    # Import/persist the complete song immediately before background separation.
    # For an existing project, a byte-identical file is deliberately reused instead
    # of rejected. It may live only in Originals/files and does not need to already
    # be represented by a timeline track.
    audio_name = f"{uuid.uuid4().hex[:10]}.mp3"
    uploaded_source = audio_path(project.id, audio_name)
    _copy_limited(file.file, uploaded_source)
    duplicate = find_duplicate_project_file(project.id, uploaded_source) if project_id else None
    source = uploaded_source
    source_audio_name = audio_name
    source_already_on_timeline = False
    if duplicate:
        uploaded_source.unlink(missing_ok=True)
        try:
            source = file_path(project.id, duplicate["category"], duplicate["name"])
        except ValueError as exc:
            raise HTTPException(400, "La copia esistente del file non è riutilizzabile.") from exc
        if duplicate["category"] == "audio":
            source_audio_name = duplicate["name"]
            source_already_on_timeline = any(track.filename == source_audio_name for track in project.tracks)
    try:
        ffprobe(source)
    except Exception as exc:
        if not duplicate:
            uploaded_source.unlink(missing_ok=True)
        if not project_id:
            delete_project(project.id)
        raise HTTPException(400, "File MP3 non valido o non supportato.") from exc

    if duplicate:
        original = source
    else:
        original = preserve_original(project.id, source, Path(file.filename or "source.mp3").name)
    duration = media_duration_ms(source)
    channels, channel_layout = _audio_channel_info(source)
    if keep_original_track and not source_already_on_timeline:
        # Tracks reference files from audio/. If the reusable copy exists only in
        # Originals, create only the timeline working copy while keeping the original
        # storage object untouched and using it directly for the split job.
        if duplicate and duplicate["category"] != "audio":
            source_audio_name = f"{uuid.uuid4().hex[:10]}.mp3"
            shutil.copyfile(source, audio_path(project.id, source_audio_name))
        original_track = Track(
            id=uuid.uuid4().hex[:10],
            name="Original Mix",
            type="other",
            filename=source_audio_name,
            duration_ms=duration,
            channels=channels,
            channel_layout=channel_layout,
            clips=[
                Clip(
                    id=uuid.uuid4().hex[:10],
                    source_start_ms=0,
                    source_end_ms=duration,
                    timeline_start_ms=0,
                )
            ],
        )
        project.tracks.append(original_track)
    save_project(project)

    job_id = uuid.uuid4().hex[:16]
    cancel_event = threading.Event()
    now = time.time()
    job = {
        "id": job_id,
        "project_id": project.id,
        "status": "queued",
        "progress": 5,
        "message": "Brano importato e progetto salvato",
        "model": model,
        "stem_count": stem_count,
        "filename": Path(file.filename or original.name).name,
        "created_at": now,
        "updated_at": now,
        "cancel_event": cancel_event,
        "error": None,
        "estimate_bpm": estimate_bpm_for_project,
        "source_track_id": None,
        "stem_name_prefix": "",
        "extract_lyrics": bool(extract_lyrics),
        "extract_chords": bool(extract_chords),
        "lyrics_model": lyrics_model or lyrics_catalog(native=NATIVE_SINGLE_USER)["default_model"],
        "chords_engine": chords_engine or chords_catalog(native=NATIVE_SINGLE_USER)["default_engine"],
        "split_backing_vocals": bool(split_backing_vocals),
        "split_percussions": bool(split_percussions),
        "percussion_method": percussion_method,
        "stem_targets": sorted(requested_targets),
        "singer_mode": bool(singers), "singers": singers,
        "singer_model": singer_model, "singer_target": singer_target,
        "backing_vocal_model": backing_vocal_model,
        "vocal_split_method": None,
        "analysis": {},
    }
    with STEM_JOB_LOCK:
        STEM_JOBS[job_id] = job
    _enqueue_existing_ai_job(job, lambda: _stem_split_worker(job_id, source, keep_original_track),
        durable_payload=_stem_durable_payload(job, source, keep_original_track))
    return {"job": _stem_job_public(job), "project": project}


@app.get("/api/stems/jobs/{job_id}")
def stem_job_status(job_id: str, request: Request):
    with STEM_JOB_LOCK:
        job = STEM_JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "Job non trovato.")
        snapshot = dict(job)
    _project_for_actor(request, snapshot["project_id"])
    return _stem_job_public(snapshot)


@app.post("/api/stems/jobs/{job_id}/cancel")
def stem_job_cancel(job_id: str, request: Request):
    with STEM_JOB_LOCK:
        job = STEM_JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "Job non trovato.")
        project_id = job["project_id"]
    _project_for_actor(request, project_id)
    with STEM_JOB_LOCK:
        current_job = STEM_JOBS[job_id]
        if current_job["status"] in {"completed", "failed", "cancelled"}:
            return _stem_job_public(current_job)
        try:
            queue_row = ai_arranger_runtime.cancel(job_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if queue_row is not None and queue_row["state"] == "cancelled":
            current_job["status"] = "cancelled"
            current_job["message"] = "Separazione annullata prima dell'esecuzione"
        else:
            current_job["status"] = "cancelling"
            current_job["message"] = "Annullamento in corso…"
        current_job["cancel_event"].set()
        current_job["updated_at"] = time.time()
        return _stem_job_public(current_job)


# Backward-compatible synchronous endpoint retained for API clients.
@app.post("/api/stems/split")
async def split_stems_compat(
    request: Request,
    file: UploadFile = File(...),
    project_id: str = "",
    target: str = "MTA8",
    model: str = "htdemucs_6s",
):
    if Path(file.filename or "").suffix.lower() != ".mp3":
        raise HTTPException(400, "stem separation currently accepts MP3 input")
    if not STEM_SPLITTER.available():
        raise HTTPException(503, "Demucs stem plugin is not installed in this runtime")
    actor = _actor(request)
    from .ai_project_lock import project_publication_lock
    from contextlib import nullcontext
    # Existing-project writes must coordinate with every other project writer.
    with project_publication_lock(project_id) if project_id else nullcontext():
        if project_id:
            existing_project=_project_for_actor(request, project_id)
            _ensure_workspace_capacity(existing_project.owner_user_id, int(request.headers.get("content-length") or 0))
        else:
            _ensure_workspace_capacity(actor["id"] if actor["id"] > 0 else None, int(request.headers.get("content-length") or 0))
        project = existing_project if project_id else create_project(
            Path(file.filename or "Stems").stem[:200],
            target if target in {"MTA8", "MTA16", "DAW"} else "MTA8",
            owner_user_id=actor["id"] if actor["id"] > 0 else None,
        )
        with tempfile.TemporaryDirectory() as td_raw:
            td = Path(td_raw)
            source = td / "source.mp3"
            _copy_limited(file.file, source)
            preserve_original(project.id, source, Path(file.filename or "source.mp3").name)
            try:
                ffprobe(source)
                stems = STEM_SPLITTER.split(source, td / "stems", model=model)
            except Exception as exc:
                raise HTTPException(400, "stem separation failed") from exc
            mapping = {
                "drums": "drums", "bass": "bass", "guitar": "guitars", "piano": "keyboards",
                "vocals": "melody", "other": "other",
            }
            for stem in stems:
                filename = f"{uuid.uuid4().hex[:10]}.wav"
                dst = audio_path(project.id, filename)
                shutil.copyfile(stem, dst)
                filename, dst, _ = _normalize_audio_to_project_rate(project.id, filename, project.sample_rate, strict=False)
                duration = media_duration_ms(dst)
                project.tracks.append(Track(
                    id=uuid.uuid4().hex[:10],
                    name=stem.stem.title(),
                    type=mapping.get(stem.stem.lower(), "other"),
                    filename=filename,
                    duration_ms=duration,
                    sample_rate=int(project.sample_rate),
                    clips=[Clip(id=uuid.uuid4().hex[:10], source_start_ms=0, source_end_ms=duration, timeline_start_ms=0)],
                ))
        save_project(project)
        return project



@app.post("/api/projects/{pid}/tracks/{track_id}/stem-jobs")
def start_track_stem_job(
    pid: str,
    track_id: str,
    request: Request,
    model: str = "htdemucs_6s",
    stem_count: int = 0,
    split_backing_vocals: bool = False,
    backing_vocal_model: str = LEAD_BACKING_DEFAULT_MODEL,
    split_percussions: bool = False,
    percussion_method: str = "dsp",
    stem_targets: str = "all",
    singers_json: str = "",
    singer_model: str = "sam-audio-small",
    singer_target: str = "all",
):
    project = _project_for_actor(request, pid)
    if not STEM_SPLITTER.available():
        raise HTTPException(503, "Demucs stem plugin is not installed in this runtime")
    stem_status = STEM_SPLITTER.status()
    supported_counts = [int(value) for value in stem_status.get("supported_stem_counts", [])]
    if stem_count != 0 and (stem_count < 2 or stem_count > 64):
        raise HTTPException(400, "Unsupported stem count")
    if stem_count and stem_count not in supported_counts:
        raise HTTPException(400, f"No configured model provides {stem_count} stems")
    if stem_count == 2:
        model = "htdemucs" if model not in {"htdemucs", "htdemucs_ft"} else model
    elif stem_count:
        profiles = [item for item in stem_status.get("model_profiles", []) if int(item.get("stem_count", 0)) == stem_count]
        if profiles and (model not in stem_status["models"] or next((int(item.get("stem_count", 0)) for item in stem_status.get("model_profiles", []) if item.get("model") == model), -1) != stem_count):
            model = str(profiles[0]["model"])
    status = STEM_SPLITTER.status()
    if model not in status["models"]:
        raise HTTPException(400, "Modello di separazione non supportato.")
    requested_targets = {item.strip().lower() for item in stem_targets.split(",") if item.strip()}
    if not requested_targets or not requested_targets <= _STEM_TARGETS or ("all" in requested_targets and len(requested_targets) > 1):
        raise HTTPException(400, "Invalid stem selection")
    if singers_json:
        try:
            singers, singer_target = _parse_singers_json(singers_json, singer_model, singer_target)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if requested_targets != {"all"} or split_backing_vocals or split_percussions:
            raise HTTPException(400, "Singer separation cannot be combined with other selective splitting")
    else:
        singers = []
    if "lead_vocals" in requested_targets:
        split_backing_vocals = True
    if requested_targets & {"percussions", "drums_without_percussions", "kick", "snare", "toms", "cymbals"}:
        split_percussions = True
    if percussion_method not in _PERCUSSION_METHODS:
        raise HTTPException(400, "Unknown percussion model")
    if split_backing_vocals and backing_vocal_model != "ffmpeg-center-side":
        try:
            _lead_backing_model_info(backing_vocal_model)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    track = next((item for item in project.tracks if item.id == track_id), None)
    if track is None:
        raise HTTPException(404, "track not found")

    with STEM_JOB_LOCK:
        busy = any(
            item["project_id"] == pid and item["status"] not in {"completed", "failed", "cancelled"}
            for item in STEM_JOBS.values()
        )
    if busy:
        raise HTTPException(409, "È già in corso una separazione strumenti per questo progetto.")

    source = audio_path(pid, track.filename)
    if not source.is_file():
        raise HTTPException(404, "File audio della traccia non trovato.")
    try:
        ffprobe(source)
    except Exception as exc:
        raise HTTPException(400, "La traccia selezionata non contiene audio separabile.") from exc

    job_id = uuid.uuid4().hex[:16]
    now = time.time()
    job = {
        "id": job_id,
        "project_id": pid,
        "source_track_id": track.id,
        "status": "queued",
        "progress": 5,
        "message": f"Separazione della traccia {track.name} in coda",
        "model": model,
        "stem_count": stem_count,
        "split_backing_vocals": bool(split_backing_vocals),
        "split_percussions": bool(split_percussions),
        "percussion_method": percussion_method,
        "stem_targets": sorted(requested_targets),
        "singer_mode": bool(singers), "singers": singers,
        "singer_model": singer_model, "singer_target": singer_target,
        "backing_vocal_model": backing_vocal_model,
        "vocal_split_method": None,
        "filename": track.name,
        "created_at": now,
        "updated_at": now,
        "cancel_event": threading.Event(),
        "error": None,
        "estimate_bpm": False,
        "stem_name_prefix": track.name,
    }
    with STEM_JOB_LOCK:
        STEM_JOBS[job_id] = job
    _enqueue_existing_ai_job(job, lambda: _stem_split_worker(job_id, source, True),
        durable_payload=_stem_durable_payload(job, source, True))
    return _stem_job_public(job)



def _limit_metronome_wav(path: Path, start_ms: int, stop_ms: int | None) -> None:
    """Mute outside [start, stop) without shifting the generated beat timeline."""
    if start_ms == 0 and stop_ms is None:
        return
    with wave.open(str(path), "rb") as src:
        params = src.getparams()
        if params.comptype != "NONE":
            raise ValueError("Metronome WAV must be uncompressed PCM")
        rate, count = src.getframerate(), src.getnframes()
        start = max(0, min(count, round(start_ms * rate / 1000)))
        stop = count if stop_ms is None else max(start, min(count, round(stop_ms * rate / 1000)))
        if start == 0 and stop == count:
            return
        sample_width = params.nchannels * params.sampwidth
        replacement = path.with_name(path.name + ".window.wav")
        try:
            with wave.open(str(replacement), "wb") as dest:
                dest.setparams(params)
                block = 32768
                for i in range(0, count, block):
                    n = min(block, count - i)
                    raw = bytearray(src.readframes(n))
                    if i < start:
                        zero_to = min(n, start - i)
                        raw[:zero_to * sample_width] = b"\x00" * (zero_to * sample_width)
                    if i + n > stop:
                        zero_from = max(0, stop - i)
                        raw[zero_from * sample_width:] = b"\x00" * ((n-zero_from) * sample_width)
                    dest.writeframesraw(raw)
            os.replace(replacement, path)
        finally:
            replacement.unlink(missing_ok=True)


@app.post("/api/projects/{pid}/metronome-track")
@_serialized_project_mutation
def create_metronome_track(pid: str, request: Request, mode: str = "fixed", track_id: str = "", sensitivity: float = 0.35):
    with METRONOME_TRACK_LOCK:
        return _create_metronome_track_locked(pid, request, mode=mode, track_id=track_id, sensitivity=sensitivity)


def _create_metronome_track_locked(pid: str, request: Request, mode: str = "fixed", track_id: str = "", sensitivity: float = 0.35):
    project = _project_for_actor(request, pid)
    duration_ms = project_duration_ms(project)
    if duration_ms <= 0:
        raise HTTPException(400, "Il progetto non ha ancora una durata. Importa almeno una traccia audio prima di creare il metronomo.")

    def is_metronome_track(item: Track) -> bool:
        name = str(getattr(item, "name", "") or "").lower()
        return str(getattr(item, "type", "") or "").lower() == "click" or "metronom" in name

    existing = [item for item in project.tracks if is_metronome_track(item)]
    track = existing[0] if existing else None
    reused = track is not None

    # Enforce the invariant at persistence level as well: one project, one metronome.
    # Old duplicates are removed together with their generated audio files.
    if len(existing) > 1:
        duplicate_ids = {item.id for item in existing[1:]}
        for item in existing[1:]:
            if item.filename:
                audio_path(pid, item.filename).unlink(missing_ok=True)
        project.tracks = [item for item in project.tracks if item.id not in duplicate_ids]

    mode = str(mode or "fixed").strip().lower()
    if mode not in {"fixed", "zones", "adaptive"}:
        raise HTTPException(400, "Tipo metronomo non valido")
    filename = track.filename if track and track.filename else f"metronome-{uuid.uuid4().hex[:10]}.wav"
    target_out = audio_path(pid, filename)
    out = target_out.with_name(f".{target_out.stem}.{uuid.uuid4().hex}.tmp.wav")
    tempo_points = []
    project.metronome_sensitivity = max(0.0, min(1.0, float(sensitivity)))
    reference_track = None
    if track_id:
        reference_track = next((item for item in project.tracks if item.id == track_id), None)
        if reference_track is None:
            raise HTTPException(404, "Traccia di riferimento non trovata")
        if is_metronome_track(reference_track):
            raise HTTPException(400, "La traccia metronomo non può essere usata come riferimento ritmico")
        if not reference_track.filename:
            raise HTTPException(400, "La traccia di riferimento non contiene audio")
    try:
        beat_times_ms = []
        if mode == "adaptive" or (reference_track is not None and mode == "fixed"):
            # Every adaptive request and every track-referenced request performs a
            # fresh rhythmic analysis. No previous beat/tempo map is reused.
            with tempfile.TemporaryDirectory() as td:
                analysis_audio = Path(td) / ("reference-track.wav" if reference_track is not None else "adaptive-source.wav")
                if reference_track is not None:
                    render_track(reference_track, audio_path(pid, reference_track.filename), analysis_audio, sample_rate=int(project.sample_rate))
                else:
                    analysis_project = project.model_copy(deep=True)
                    analysis_project.tracks = [item for item in analysis_project.tracks if not is_metronome_track(item)]
                    if not analysis_project.tracks:
                        raise ValueError("nessuna traccia musicale disponibile per l'analisi adattiva")
                    render_mix(analysis_project, audio_path, analysis_audio, fmt="wav", sample_rate=int(project.sample_rate), wav_bit_depth=16)
                beat_times_ms, tempo_points = estimate_adaptive_tempo_map(analysis_audio)

        if mode == "adaptive":
            beat_times_ms = stabilize_adaptive_beats(beat_times_ms, project.metronome_sensitivity)
            # Keep the transport's tempo map aligned to the actual generated clicks.
            tempo_points = [point.model_copy(update={"time_ms": beat_times_ms[i]}) for i, point in enumerate(tempo_points) if i < len(beat_times_ms)]
            duration_ms = generate_adaptive_metronome_wav(project, out, beat_times_ms)
            project.adaptive_tempo_map = tempo_points
            project.metronome_mode = "adaptive"
            project.metronome_shift_ms = 0
            project.metronome_grid_origin_ms = int(beat_times_ms[0]) if beat_times_ms else 0
        elif mode == "zones":
            boundaries = [0] + sorted({int(m.time_ms) for m in project.markers if not m.disabled and not m.deleted and 0 < m.time_ms < duration_ms}) + [duration_ms]
            zone_bpms = dict(project.metronome_zone_bpms or {})
            keyed_boundaries = _metronome_zone_boundaries(project, duration_ms)
            if reference_track is not None:
                with tempfile.TemporaryDirectory() as td:
                    rendered = Path(td) / "reference.wav"
                    render_track(reference_track, audio_path(pid, reference_track.filename), rendered, sample_rate=int(project.sample_rate))
                    with wave.open(str(rendered), "rb") as source:
                        rate = source.getframerate()
                        for start, end in zip(boundaries, boundaries[1:]):
                            manual_bpm = _metronome_manual_for_zone(project, keyed_boundaries[boundaries.index(start)][1], keyed_boundaries[boundaries.index(start)+1][1])
                            if manual_bpm is not None:
                                zone_bpms[str(start)] = manual_bpm
                                continue
                            if end-start < 1800:
                                zone_bpms[str(start)] = float(project.bpm)
                                continue
                            source.setpos(min(source.getnframes(), int(start * rate / 1000)))
                            length = min(source.getnframes()-source.tell(), int((end-start)*rate/1000))
                            excerpt = Path(td) / f"zone-{start}.wav"
                            with wave.open(str(excerpt), "wb") as segment:
                                segment.setparams(source.getparams())
                                segment.writeframes(source.readframes(max(0,length)))
                            try:
                                bpm, _ = estimate_bpm_and_signature(excerpt)
                                zone_bpms[str(start)] = bpm
                            except (ValueError, RuntimeError, OSError):
                                zone_bpms[str(start)] = float(project.bpm)
            project.metronome_zone_bpms = {str(start): float(_metronome_manual_for_zone(project, keyed_boundaries[i][1], keyed_boundaries[i+1][1]) or zone_bpms.get(str(start), project.bpm)) for i,start in enumerate(boundaries[:-1])}
            beat_times_ms = zoned_metronome_beats(project, duration_ms, project.metronome_zone_bpms)
            zone_starts = sorted(m.time_ms for m in project.markers if not m.disabled and not m.deleted and 0 < m.time_ms < duration_ms)
            duration_ms = generate_adaptive_metronome_wav(project, out, beat_times_ms, accent_reset_ms=zone_starts)
            project.metronome_mode = "zones"
            project.metronome_grid_origin_ms = 0
            project.metronome_shift_ms = 0
            project.adaptive_tempo_map = []
        elif reference_track is not None:
            # For a fixed metronome referenced to one track, use the freshly
            # detected beat phase and a single robust BPM (median local tempo).
            bpms = sorted(float(point.bpm) for point in tempo_points if float(point.bpm) > 0)
            if not bpms or not beat_times_ms:
                raise ValueError("tempo non rilevabile dalla traccia di riferimento")
            ref_bpm = bpms[len(bpms)//2]
            project.bpm = round(ref_bpm, 1)
            project.base_bpm = project.bpm
            interval_ms = 60000.0 / max(1.0, project.bpm)
            seed = float(beat_times_ms[0])
            while seed - interval_ms >= 0:
                seed -= interval_ms
            fixed_beats = []
            value = seed
            while value <= duration_ms:
                fixed_beats.append(max(0, int(round(value))))
                value += interval_ms
            duration_ms = generate_adaptive_metronome_wav(project, out, fixed_beats)
            project.metronome_mode = "fixed"
            project.metronome_grid_origin_ms = int(round(seed))
            project.metronome_shift_ms = 0
            project.adaptive_tempo_map = []
        else:
            duration_ms = generate_metronome_wav(project, out)
            project.metronome_mode = "fixed"
            project.metronome_grid_origin_ms = 0
            project.metronome_shift_ms = 0
            project.adaptive_tempo_map = []
        project.metronome_reference_track_id = reference_track.id if reference_track is not None else ""
        project.metronome_reference_track_name = reference_track.name if reference_track is not None else ""
        _limit_metronome_wav(out, project.metronome_start_ms, project.metronome_stop_ms)
        peaks = waveform_peaks(out)
    except Exception as exc:
        if not reused:
            out.unlink(missing_ok=True)
        raise HTTPException(400, f"Creazione metronomo fallita: {str(exc)[:300]}") from exc

    if track is None:
        track = Track(
            id=uuid.uuid4().hex[:10],
            name=("Metronomo adattivo" if mode == "adaptive" else ("Metronomo a zone" if mode == "zones" else "Metronomo")),
            type="click",
            filename=filename,
            duration_ms=duration_ms,
            channels=1,
            channel_layout="mono",
            sample_rate=int(project.sample_rate),
            volume_db=0.0,
            waveform_peaks=peaks,
            waveform_revision="",
            clips=[
                Clip(
                    id=uuid.uuid4().hex[:10],
                    source_start_ms=0,
                    source_end_ms=duration_ms,
                    timeline_start_ms=0,
                )
            ],
        )
        project.tracks.append(track)
    else:
        track.name = "Metronomo adattivo" if mode == "adaptive" else ("Metronomo a zone" if mode == "zones" else "Metronomo")
        track.type = "click"
        track.filename = filename
        track.duration_ms = duration_ms
        track.channels = 1
        track.channel_layout = "mono"
        track.sample_rate = int(project.sample_rate)
        track.volume_db = 0.0
        track.waveform_peaks = peaks
        track.clips = [
            Clip(
                id=(track.clips[0].id if track.clips else uuid.uuid4().hex[:10]),
                source_start_ms=0,
                source_end_ms=duration_ms,
                timeline_start_ms=0,
            )
        ]
    # Never overwrite the previously valid WAV with a partial render.
    try:
        with out.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(out, target_out)
        track.waveform_revision = _track_waveform_revision(track, target_out) if peaks else ""
        save_project(project)
    finally:
        out.unlink(missing_ok=True)
    return {"project": project, "track": track, "reused": reused, "mode": mode, "tempo_map": tempo_points if mode == "adaptive" else [], "reference_track_id": project.metronome_reference_track_id, "reference_track_name": project.metronome_reference_track_name}


def _metronome_zone_boundaries(project: Project, duration: int):
    marks = sorted((m for m in project.markers if not m.disabled and not m.deleted and 0 < m.time_ms < duration), key=lambda m: m.time_ms)
    return [(0, "START"), *((int(m.time_ms), m.id) for m in marks), (duration, "END")]


def _metronome_manual_for_zone(project: Project, left: str, right: str):
    # Match exact boundaries first, then a surviving boundary when a single marker changes.
    manual = project.metronome_manual_zone_bpms or {}
    # Zones survive a moved boundary because keys use marker identity, not time.
    exact = f"{left}|{right}"
    if exact in manual:
        return float(manual[exact])
    candidates = [(key, value) for key, value in manual.items() if key.split("|")[0] == left or key.split("|")[-1] == right]
    if len(candidates) == 1:
        return float(candidates[0][1])
    return None


def _update_metronome_zone_locked(pid: str, request: Request, time_ms: int, track_id: str):
    """Analyze one marker zone, replace only its PCM and envelope bins atomically."""
    import numpy as np
    project = _project_for_actor(request, pid)
    if project.metronome_mode != "zones":
        return _create_metronome_track_locked(pid, request, mode=project.metronome_mode,
            track_id=track_id or project.metronome_reference_track_id, sensitivity=project.metronome_sensitivity)
    duration = project_duration_ms(project)
    marks = sorted({int(m.time_ms) for m in project.markers if not m.disabled and not m.deleted and 0 < m.time_ms < duration})
    boundaries = [0, *marks, duration]
    start, end = next(((a, b) for a,b in zip(boundaries, boundaries[1:]) if a <= time_ms < b), (boundaries[-2], duration))
    keyed_boundaries = _metronome_zone_boundaries(project, duration)
    present_ids = {identifier for _, identifier in keyed_boundaries}
    project.metronome_manual_zone_bpms = {key: value for key, value in project.metronome_manual_zone_bpms.items()
        if len(key.split("|")) == 2 and any(identifier in present_ids for identifier in key.split("|"))}
    zone_index = boundaries.index(start)
    left_id, right_id = keyed_boundaries[zone_index][1], keyed_boundaries[zone_index+1][1]
    manual_bpm = _metronome_manual_for_zone(project, left_id, right_id)
    click_track = next((t for t in project.tracks if t.type == "click"), None)
    if click_track is None:
        raise HTTPException(400, "Traccia metronomo assente")
    reference_id = track_id or project.metronome_reference_track_id
    reference = next((t for t in project.tracks if t.id == reference_id and t.type != "click" and t.filename), None)
    if track_id and reference is None:
        raise HTTPException(400, "Selezionare una traccia audio di riferimento valida")
    bpm = float(manual_bpm if manual_bpm is not None else project.bpm)
    if manual_bpm is None and reference is not None and end-start >= 1800:
        try:
            with tempfile.TemporaryDirectory() as td:
                rendered=Path(td)/"source.wav"; excerpt=Path(td)/"zone.wav"
                render_track(reference, audio_path(pid, reference.filename), rendered, sample_rate=int(project.sample_rate))
                with wave.open(str(rendered), "rb") as source:
                    rate=source.getframerate(); source.setpos(min(source.getnframes(), int(start*rate/1000)))
                    data=source.readframes(max(0, min(source.getnframes()-source.tell(), int((end-start)*rate/1000))))
                    with wave.open(str(excerpt), "wb") as segment:
                        segment.setparams(source.getparams()); segment.writeframes(data)
                bpm,_=estimate_bpm_and_signature(excerpt)
        except (ValueError, RuntimeError, OSError):
            bpm=float(project.bpm)
    original=audio_path(pid,click_track.filename)
    if not original.exists():
        raise HTTPException(409,"Audio metronomo non trovato")
    temp=original.with_name(f".{original.stem}.{uuid.uuid4().hex}.tmp.wav")
    try:
        with wave.open(str(original), "rb") as source:
            if source.getnchannels()!=1 or source.getsampwidth()!=2 or source.getcomptype()!="NONE":
                raise HTTPException(409,"Metronomo non compatibile con refresh parziale")
            rate=source.getframerate(); frames=source.getnframes()
            lo=max(0,min(frames,round(start*rate/1000))); hi=max(lo,min(frames,round(end*rate/1000)))
            length=hi-lo
            pcm=np.zeros(length,dtype=np.int16)
            click_len=max(1,round(.045*rate))
            tone_t=np.arange(click_len,dtype=np.float64)/rate
            tick_num=max(1,int(str(project.time_signature or "4/4").split("/")[0]))
            step=60000.0/max(1.0,float(bpm))
            for index in range(max(0,int((end-start)/step)+2)):
                local=round(index*step*rate/1000)
                if local>=length:break
                freq=1320.0 if index%tick_num==0 else 880.0
                tone=np.sin(2*np.pi*freq*tone_t)*np.exp(-tone_t*55.0)
                count=min(click_len,length-local)
                pcm[local:local+count]=np.asarray(np.clip(tone[:count],-1,1)*32767,dtype=np.int16)
            with wave.open(str(temp),"wb") as output:
                output.setparams(source.getparams())
                source.setpos(0)
                remaining=lo
                while remaining:
                    chunk=min(65536,remaining);output.writeframesraw(source.readframes(chunk));remaining-=chunk
                output.writeframesraw(pcm.tobytes())
                source.setpos(hi);remaining=frames-hi
                while remaining:
                    chunk=min(65536,remaining);output.writeframesraw(source.readframes(chunk));remaining-=chunk
                output.writeframes(b"")
        # Build metadata before atomic replacement; preserve old WAV on any failure.
        new_peaks=waveform_peaks(temp)
        with temp.open('rb') as fd:os.fsync(fd.fileno())
        os.replace(temp,original)
        project.metronome_zone_bpms[str(start)] = round(float(bpm),1)
        if reference is not None:
            project.metronome_reference_track_id=reference.id
            project.metronome_reference_track_name=reference.name
        click_track.waveform_peaks=new_peaks
        click_track.waveform_revision=_track_waveform_revision(click_track,original)
        save_project(project)
    finally:
        temp.unlink(missing_ok=True)
    return {"project":project,"track":click_track,"zone_start_ms":start,"zone_end_ms":end,
        "refresh_scope":"zone_atomic","zone_bpm":bpm}


@app.post("/api/projects/{pid}/metronome-zone-bpm")
@_serialized_project_mutation
def set_metronome_zone_bpm(pid: str, request: Request, time_ms: int = 0, bpm: float | None = None, automatic: bool = False):
    with METRONOME_TRACK_LOCK:
        project = _project_for_actor(request, pid)
        if project.metronome_mode != "zones":
            raise HTTPException(400, "Metronome must be in zone mode")
        duration = project_duration_ms(project)
        points = _metronome_zone_boundaries(project, duration)
        zone = next((i for i in range(len(points)-1) if points[i][0] <= time_ms < points[i+1][0]), len(points)-2)
        left, right = points[zone][1], points[zone+1][1]
        key = f"{left}|{right}"
        if automatic:
            for oldkey in list(project.metronome_manual_zone_bpms):
                a,b = oldkey.split("|",1)
                if a == left or b == right:
                    del project.metronome_manual_zone_bpms[oldkey]
        else:
            if bpm is None or not 20 <= bpm <= 400:
                raise HTTPException(400, "BPM must be between 20 and 400")
            project.metronome_manual_zone_bpms[key] = round(float(bpm), 2)
        save_project(project)
        return _update_metronome_zone_locked(pid, request, time_ms, "")


@app.post("/api/projects/{pid}/metronome-track/refresh")
@_serialized_project_mutation
def refresh_metronome_at_playhead(pid: str, request: Request, time_ms: int = 0, track_id: str = ""):
    project = _project_for_actor(request, pid)
    mode = project.metronome_mode
    # Reuses the stored mode/settings. Zones are selected by the playhead;
    # the renderer currently regenerates the complete WAV atomically.
    markers = sorted(m.time_ms for m in project.markers if not m.deleted and not m.disabled)
    bounds = [0] + [t for t in markers if t < project_duration_ms(project)] + [project_duration_ms(project)]
    zone = next(((a, b) for a, b in zip(bounds, bounds[1:]) if a <= time_ms < b), (0, project_duration_ms(project)))
    with METRONOME_TRACK_LOCK:
        if mode == "zones":
            return _update_metronome_zone_locked(pid, request, time_ms, track_id)
        result = _create_metronome_track_locked(pid, request, mode=mode, track_id=track_id or project.metronome_reference_track_id, sensitivity=project.metronome_sensitivity)
    result["zone_start_ms"], result["zone_end_ms"] = zone
    result["refresh_scope"] = "full_atomic"
    return result


@app.post("/api/projects/{pid}/metronome-shift")
@_serialized_project_mutation
def shift_adaptive_metronome(pid: str, request: Request, value: float = 0.0, unit: str = "ms"):
    project = _project_for_actor(request, pid)
    if project.metronome_mode != "adaptive" or not project.adaptive_tempo_map:
        raise HTTPException(400, "Lo shift in beat/ms richiede un metronomo adattivo con tempo map")
    unit = str(unit or "ms").strip().lower()
    if unit not in {"ms", "beat", "beats"}:
        raise HTTPException(400, "Unità shift non valida")
    shift_ms = float(value)
    if unit in {"beat", "beats"}:
        times = [int(p.time_ms) for p in project.adaptive_tempo_map]
        intervals = [b-a for a,b in zip(times, times[1:]) if b>a]
        if not intervals:
            raise HTTPException(400, "Tempo map insufficiente per lo shift in beat")
        intervals.sort()
        beat_ms = float(intervals[len(intervals)//2])
        shift_ms = float(value) * beat_ms
    project.metronome_shift_ms = max(-3600000, min(3600000, int(round(shift_ms))))
    beat_times = [max(0, int(p.time_ms) + project.metronome_shift_ms) for p in project.adaptive_tempo_map]
    beat_times = sorted(set(beat_times))
    track = next((t for t in project.tracks if str(getattr(t,"type","")).lower()=="click" or "metronom" in str(getattr(t,"name","")).lower()), None)
    if track is None or not track.filename:
        raise HTTPException(400, "Traccia metronomo non trovata")
    out = audio_path(pid, track.filename)
    staged = out.with_name(f".{out.stem}.{uuid.uuid4().hex}.tmp.wav")
    try:
        duration_ms = generate_adaptive_metronome_wav(project, staged, beat_times)
        peaks = waveform_peaks(staged)
        os.replace(staged, out)
    finally:
        staged.unlink(missing_ok=True)
    track.duration_ms = duration_ms
    track.waveform_peaks = peaks
    track.waveform_revision = _track_waveform_revision(track, out) if track.waveform_peaks else ""
    track.clips = [Clip(id=(track.clips[0].id if track.clips else uuid.uuid4().hex[:10]), source_start_ms=0, source_end_ms=duration_ms, timeline_start_ms=0)]
    save_project(project)
    return {"project": project, "track": track, "shift_ms": project.metronome_shift_ms}

@app.post("/api/projects/{pid}/transport-time-mode")
@_serialized_project_mutation
def set_transport_time_mode(pid: str, request: Request, mode: str = "time"):
    project = _project_for_actor(request, pid)
    mode = str(mode or "time").strip().lower()
    if mode not in {"time", "musical"}:
        raise HTTPException(400, "Modalità transport non valida")
    project.transport_time_mode = mode
    save_project(project)
    return {"project": project}


@app.post("/api/projects/{pid}/chords-track")
@_serialized_project_mutation
def create_chords_track(pid: str, request: Request):
    with CHORDS_TRACK_LOCK:
        return _create_chords_track_locked(pid, request)


@app.post("/api/projects/{pid}/chords-track/refresh")
@_serialized_project_mutation
def refresh_chords_track(pid: str, request: Request, old_time_ms: int, new_time_ms: int):
    """Refresh an existing generated Chords track after any chord mutation."""
    with CHORDS_TRACK_LOCK:
        project = _project_for_actor(request, pid)
        def is_chords_track(item: Track) -> bool:
            name = str(getattr(item, "name", "") or "").strip().lower()
            filename = str(getattr(item, "filename", "") or "").lower()
            return name in {"chords", "accordi", "chords piano", "accordi piano"} or filename.startswith("chords-piano-")
        track = next((item for item in project.tracks if is_chords_track(item)), None)
        if track is None or not track.filename:
            return {"project": project, "refreshed": False, "mode": "none"}
        target = audio_path(pid, track.filename)
        staged = target.with_name(f".{target.stem}.{uuid.uuid4().hex}.tmp.wav")
        mode = "fast"
        refresh_start_ms = 0
        refresh_end_ms = project_duration_ms(project)
        try:
            if target.exists():
                shutil.copyfile(target, staged)
            try:
                refresh_start_ms, refresh_end_ms = refresh_chords_piano_wav_region(project, staged, old_time_ms, new_time_ms)
            except Exception:
                mode = "full"
                active_chords = [c for c in project.chords if not c.excluded and not c.deleted]
                if active_chords:
                    generate_chords_piano_wav(project, staged)
                else:
                    generate_silent_chords_wav(project, staged)
            track.duration_ms = media_duration_ms(staged)
            if mode == "fast":
                try:
                    track.waveform_peaks = refresh_chords_waveform_region(
                        staged, track.waveform_peaks, refresh_start_ms, refresh_end_ms
                    )
                except (ValueError, OSError, TypeError):
                    track.waveform_peaks = waveform_peaks(staged)
            else:
                track.waveform_peaks = waveform_peaks(staged)
            # A crash during any earlier step leaves the previously valid WAV intact.
            with staged.open("rb") as handle:
                os.fsync(handle.fileno())
            os.replace(staged, target)
            track.waveform_revision = _track_waveform_revision(track, target) if track.waveform_peaks else ""
            save_project(project)
        finally:
            staged.unlink(missing_ok=True)
        return {
            "project": project, "track": track, "refreshed": True, "mode": mode,
            "refresh_start_ms": refresh_start_ms, "refresh_end_ms": refresh_end_ms,
        }


def _create_chords_track_locked(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    duration_ms = project_duration_ms(project)
    if duration_ms <= 0:
        raise HTTPException(400, "Il progetto non ha ancora una durata. Importa almeno una traccia audio prima di creare la traccia accordi.")
    active_chords = [c for c in project.chords if not c.excluded and not c.deleted]
    if not active_chords:
        raise HTTPException(400, "Il progetto non contiene chords attivi")

    def is_chords_track(item: Track) -> bool:
        name = str(getattr(item, "name", "") or "").strip().lower()
        filename = str(getattr(item, "filename", "") or "").lower()
        return name in {"chords", "accordi", "chords piano", "accordi piano"} or filename.startswith("chords-piano-")

    existing = [item for item in project.tracks if is_chords_track(item)]
    track = existing[0] if existing else None
    reused = track is not None
    if len(existing) > 1:
        duplicate_ids = {item.id for item in existing[1:]}
        for item in existing[1:]:
            if item.filename:
                audio_path(pid, item.filename).unlink(missing_ok=True)
        project.tracks = [item for item in project.tracks if item.id not in duplicate_ids]

    filename = track.filename if track and track.filename else f"chords-piano-{uuid.uuid4().hex[:10]}.wav"
    out = audio_path(pid, filename)
    try:
        duration_ms = generate_chords_piano_wav(project, out)
        peaks = waveform_peaks(out)
    except Exception as exc:
        if not reused:
            out.unlink(missing_ok=True)
        raise HTTPException(400, f"Creazione traccia accordi fallita: {str(exc)[:300]}") from exc

    if track is None:
        track = Track(
            id=uuid.uuid4().hex[:10],
            name="Chords",
            type="keyboards",
            filename=filename,
            duration_ms=duration_ms,
            channels=2,
            channel_layout="stereo",
            sample_rate=int(project.sample_rate),
            volume_db=0.0,
            color="#8B5CF6",
            waveform_peaks=peaks,
            waveform_revision="",
            clips=[Clip(id=uuid.uuid4().hex[:10], source_start_ms=0, source_end_ms=duration_ms, timeline_start_ms=0)],
        )
        project.tracks.append(track)
    else:
        track.name = "Chords"
        track.type = "keyboards"
        track.filename = filename
        track.duration_ms = duration_ms
        track.channels = 2
        track.channel_layout = "stereo"
        track.sample_rate = int(project.sample_rate)
        track.volume_db = 0.0
        track.waveform_peaks = peaks
        track.clips = [Clip(
            id=(track.clips[0].id if track.clips else uuid.uuid4().hex[:10]),
            source_start_ms=0, source_end_ms=duration_ms, timeline_start_ms=0,
        )]
    track.waveform_revision = _track_waveform_revision(track, out) if peaks else ""
    save_project(project)
    return {"project": project, "track": track, "reused": reused, "chord_count": len(active_chords)}

@app.post("/api/projects/{pid}/tracks/{track_id}/estimate-bpm")
def estimate_track_bpm(pid: str, track_id: str, request: Request, time_signature: str | None = None):
    from .ai_project_lock import project_publication_lock
    with project_publication_lock(pid):
        project = _project_for_actor(request, pid)
        track = next((item for item in project.tracks if item.id == track_id), None)
        if track is None:
            raise HTTPException(404, "track not found")
        track_snapshot = (track.filename, track.sample_rate, track.duration_ms)
        bpm_snapshot = (project.bpm, project.base_bpm, project.time_signature)
        source = audio_path(pid, track.filename)
    # Expensive BPM inference cannot block independent project edits.
    try:
        preferred = str(time_signature or "").strip()
        if preferred and preferred not in {"2/4", "3/4", "4/4", "5/4", "6/8", "7/8", "9/8", "12/8"}:
            raise HTTPException(400, "time signature non valida")
        bpm, signature = estimate_bpm_and_signature(source, preferred_signature=preferred)
        # Tempo estimators are inherently octave-ambiguous (e.g. 72 vs 144 BPM).
        # When the user is only changing the meter, preserve the established
        # musical pulse by selecting the x2/x0.5 equivalent closest to the
        # project's current BPM instead of allowing a signature change to double
        # or halve the perceived metronome speed.
        if preferred:
            reference_bpm = float(bpm_snapshot[0] or 0)
            if reference_bpm > 0:
                candidates = {float(bpm)}
                value = float(bpm)
                while value / 2.0 >= 30.0:
                    value /= 2.0
                    candidates.add(value)
                value = float(bpm)
                while value * 2.0 <= 300.0:
                    value *= 2.0
                    candidates.add(value)
                bpm = min(candidates, key=lambda candidate: abs(candidate - reference_bpm))
            signature = preferred
        bpm = float(round(bpm))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, f"Impossibile stimare i BPM: {exc}") from exc
    with project_publication_lock(pid):
        project = _project_for_actor(request, pid)
        current = next((item for item in project.tracks if item.id == track_id), None)
        if current is None or (current.filename, current.sample_rate, current.duration_ms) != track_snapshot:
            raise HTTPException(409, "Track changed during BPM estimation")
        if (project.bpm, project.base_bpm, project.time_signature) != bpm_snapshot:
            raise HTTPException(409, "Project tempo changed during BPM estimation")
        project.bpm = bpm
        project.base_bpm = bpm
        project.time_signature = signature
        save_project(project)
    return {"ok": True, "track_id": track_id, "bpm": bpm, "time_signature": signature}


@app.get("/api/projects/{pid}/preview-track/{track_id}")
def preview_track(pid: str, track_id: str, request: Request, render: bool = False):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if track is None:
        raise HTTPException(404, "track not found")
    # Preview stems deliberately keep mixer controls neutral. Volume, pan,
    # mute and solo are applied downstream in the browser WebAudio graph so
    # faders react immediately without re-rendering/restarting playback.
    preview_track_model = track.model_copy(deep=True)
    preview_track_model.volume_db = 0.0
    preview_track_model.pan = 0.0
    preview_track_model.mute = False
    signature = hashlib.sha256(
        (
            preview_track_model.model_dump_json()
            + f"|{project.bpm}|{project.base_bpm}|{project.pitch_semitones}|{int(render)}"
        ).encode("utf-8")
    ).hexdigest()[:20]
    cache = session_preview_dir(pid) / "tracks"
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{track.id}-{signature}.wav"
    if not out.is_file():
        render_track_export(
            preview_track_model,
            audio_path(pid, track.filename),
            out,
            fmt="wav",
            project=project,
            apply_inserts=bool(render),
        )
        # Keep only the latest few previews per track.
        stale = sorted(cache.glob(f"{track.id}-*.wav"), key=lambda item: item.stat().st_mtime, reverse=True)[4:]
        for path in stale:
            path.unlink(missing_ok=True)
    return FileResponse(out, media_type="audio/wav", filename=f"{track.name}-preview.wav")


@app.get("/api/projects/{pid}/preview-mix")
def preview_mix(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    out = session_preview_dir(pid) / "preview-master.mp3"
    try:
        validate_project_files(project)
        preview_project = project.model_copy(deep=True)
        # Master inserts are rendered server-side, while the master fader is kept
        # neutral here so the browser can apply master volume live during playback.
        preview_project.master_volume_db = 0.0
        render_mix(preview_project, audio_path, out, fmt="mp3", bitrate="192k", sample_rate=int(preview_project.sample_rate))
    except Exception as exc:
        raise HTTPException(400, "preview mix failed") from exc
    return FileResponse(out, media_type="audio/mpeg", filename="preview-master.mp3")


@app.delete("/api/projects/{pid}/preview-cache")
def clear_project_preview_cache(pid: str, request: Request):
    _project_for_actor(request, pid)
    return {"ok": True, **cleanup_session_preview_cache(pid)}


@app.get("/api/projects/{pid}/export-plan")
def export_plan(pid: str, request: Request, profile: str | None = None, target: str | None = None):
    source_project = _project_for_actor(request, pid)
    try:
        project = _audible_export_project(source_project)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if project.target == "DAW":
        project.target = target if target in {"MTA8", "MTA16"} else "MTA16"
    limit = 8 if project.target == "MTA8" else 16
    selected = resolve_mta_device_profile(project, profile)
    suggested = suggested_slots(project, selected)
    corpus_mta16 = project.target == "MTA16" and selected in {"mlive_mta16_default", "merish5_plus_mta16"}
    return {
        "target": project.target,
        "device_profile": selected,
        "project_track_count": len(project.tracks),
        "max_output_slots": limit,
        "requires_mapping": len(project.tracks) > limit,
        "requires_explicit_click_mapping": False,
        "mta16_default_roles": {"click": 1, "melody": 9} if corpus_mta16 else None,
        "suggested_slots": suggested,
        "tracks": [{"id": t.id, "name": t.name, "type": t.type} for t in project.tracks],
    }


@app.post("/api/projects/{pid}/export-mta")
def export_mta_with_mapping(pid: str, req: MtaExportRequest, request: Request):
    project = _project_for_actor(request, pid)
    try:
        validate_project_files(project)
        export_project = _musical_export_project(project)
        known = {track.id for track in export_project.tracks}
        requested_slots = [
            slot.model_copy(update={"track_ids": [track_id for track_id in slot.track_ids if track_id in known]})
            for slot in req.slots
        ]
        requested_slots = [slot for slot in requested_slots if slot.track_ids]
        slots = validate_slot_mapping(export_project, requested_slots)
        ext = "mta8" if export_project.target == "MTA8" else "mta16"
        out = pdir(pid) / f"export.{ext}"
        export_mta(export_project, out, slots)
    except Exception as exc:
        raise HTTPException(400, str(exc)[:500]) from exc
    return FileResponse(out, filename=_download_name(project.title, ext), media_type="application/octet-stream")



def _track_export_worker(job_id: str, pid: str, track_id: str, options: dict) -> None:
    try:
        project = load_project(pid)
        track = next((item for item in project.tracks if item.id == track_id), None)
        if track is None:
            raise ValueError("track not found")
        req = TrackExportRequest.model_validate(options)
        fmt = req.format
        _media_job_update(job_id, status="running", progress=20, message="Rendering della traccia")
        out = pdir(pid) / f"track-{track.id}.{fmt}"
        render_track_export(
            track,
            audio_path(pid, track.filename),
            out,
            fmt=fmt,
            bitrate=f"{int(req.mp3_bitrate_kbps)}k",
            sample_rate=int(req.sample_rate),
            wav_bit_depth=int(req.wav_bit_depth),
            flac_compression=int(req.flac_compression),
            metadata=req.metadata,
            project=project,
        )
        _media_job_update(job_id, progress=90, message="Preparazione download")
        _media_job_update(
            job_id, status="completed", progress=100, message="Export completato",
            result={
                "download_url": f"/api/media-jobs/{job_id}/download",
                "filename": _download_name(track.name, fmt),
                "format": fmt,
                "path": str(out),
            }
        )
    except Exception as exc:
        _media_job_update(job_id, status="failed", progress=0, message="Export fallito", error=str(exc)[-1200:])


@app.post("/api/projects/{pid}/tracks/{track_id}/track-export-jobs")
def start_track_export_job(pid: str, track_id: str, request: Request, body: TrackExportRequest | None = None, format: str = "wav"):
    project = _project_for_actor(request, pid)
    if not any(item.id == track_id for item in project.tracks):
        raise HTTPException(404, "track not found")
    try:
        req = body or TrackExportRequest(format=format.lower())
    except Exception as exc:
        raise HTTPException(400, str(exc)[:500]) from exc
    now = time.time()
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id, "kind": "track-export", "project_id": pid,
        "status": "queued", "progress": 5, "message": "Export in coda",
        "created_at": now, "updated_at": now,
        "result": None, "error": None,
    }
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    threading.Thread(target=_track_export_worker, args=(job_id, pid, track_id, req.model_dump()), daemon=True).start()
    return _media_job_public(job)


@app.get("/api/media-jobs/{job_id}/download")
def media_job_download(job_id: str, request: Request):
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "Job non trovato")
        snapshot = dict(job)
    _project_for_actor(request, snapshot["project_id"])
    if snapshot["status"] != "completed" or not snapshot.get("result"):
        raise HTTPException(409, "Job non completato")
    result = snapshot["result"]
    if snapshot["kind"] not in {"track-export", "project-export"}:
        raise HTTPException(400, "Il job non produce un file")
    project = load_project(snapshot["project_id"])
    out = Path(result["path"]).resolve()
    if out.parent != pdir(project.id).resolve() or not out.is_file():
        raise HTTPException(404, "File export non trovato")
    if snapshot["kind"] == "project-export":
        media = result.get("media_type") or "application/octet-stream"
    else:
        fmt = result["format"]
        media = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac"}[fmt]
    return FileResponse(out, filename=result["filename"], media_type=media)


@app.get("/api/projects/{pid}/tracks/{track_id}/export")
def export_single_track(pid: str, track_id: str, request: Request, format: str = "wav"):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    fmt = format.lower()
    if fmt not in {"wav", "mp3", "flac"}:
        raise HTTPException(400, "unsupported track export format")
    try:
        validate_project_files(project)
        out = pdir(pid) / f"track-{track.id}.{fmt}"
        render_track_export(track, audio_path(pid, track.filename), out, fmt=fmt, project=project)
    except Exception as exc:
        raise HTTPException(400, "track export failed") from exc
    media = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac"}[fmt]
    return FileResponse(out, filename=_download_name(track.name, fmt), media_type=media)


@app.get("/api/projects/{pid}/mta-analysis")
def mta_analysis(pid: str, request: Request):
    _project_for_actor(request, pid)
    path = pdir(pid) / "mta-analysis.json"
    if not path.exists():
        source = pdir(pid) / "source.mta"
        if not source.exists():
            raise HTTPException(404, "no imported MTA source is available for analysis")
        try:
            report = analyze_mta(source, pdir(pid) / "attachments" / "reverse-analysis")
            path.write_text(__import__("json").dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            raise HTTPException(400, "MTA analysis failed") from exc
    return __import__("json").loads(path.read_text(encoding="utf-8"))


@app.get("/api/projects/{pid}/mta-miditk")
def mta_miditk(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    analysis_dir = pdir(pid) / "attachments" / "reverse-analysis"
    midi_files = sorted(analysis_dir.glob("*.miditk.mid")) if analysis_dir.exists() else []
    if not midi_files:
        source = pdir(pid) / "source.mta"
        if not source.exists():
            raise HTTPException(404, "no imported MTA source is available for MIDITK extraction")
        try:
            analyze_mta(source, analysis_dir)
        except Exception as exc:
            raise HTTPException(400, "MIDITK extraction failed") from exc
        midi_files = sorted(analysis_dir.glob("*.miditk.mid"))
    if not midi_files:
        raise HTTPException(404, "no verified MIDITK Standard MIDI payload found")
    return FileResponse(
        midi_files[0],
        filename=_download_name(f"{project.title}-MIDITK", "mid"),
        media_type="audio/midi",
    )


@app.post("/api/mta/diff")
async def mta_binary_diff(file_a: UploadFile = File(...), file_b: UploadFile = File(...)):
    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        a = td / "a.mta"; b = td / "b.mta"
        _copy_limited(file_a.file, a); _copy_limited(file_b.file, b)
        try:
            ffprobe(a); ffprobe(b)
        except Exception as exc:
            raise HTTPException(400, "both files must be valid media containers") from exc
        return diff_blobs(a.read_bytes(), b.read_bytes())



def _ffmpeg_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _karaoke_background_path(pid: str, name: str | None) -> Path | None:
    if not name:
        return None
    if Path(name).name != name or name in {".", ".."}:
        raise ValueError("invalid karaoke background")
    path = pdir(pid) / "karaoke" / name
    if not path.is_file():
        raise ValueError("karaoke background not found")
    return path


def _render_karaoke_video(pid: str, project: Project, out: Path, req: ProjectExportRequest) -> None:
    if not project.lyrics:
        raise ValueError("MP4 karaoke export requires synchronized lyrics")
    width, height = (1280, 720) if req.karaoke_resolution == "1280x720" else (1920, 1080)
    work = pdir(pid) / "karaoke"
    work.mkdir(parents=True, exist_ok=True)
    mix = work / "mix.wav"
    ass = work / "lyrics.ass"
    render_mix(project, audio_path, mix, fmt="wav", sample_rate=48000, wav_bit_depth=24)
    build_karaoke_ass(
        ass, title=project.title, artist=project.artist, lyrics=project.lyrics,
        chords=transpose_chords(project.chords, project.pitch_semitones), include_chords=req.karaoke_chords, width=width, height=height,
    )
    bg = _karaoke_background_path(pid, req.karaoke_background)
    ass_filter = _ffmpeg_filter_path(ass)
    if bg:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(bg), "-i", str(mix),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,ass='{ass_filter}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "320k", "-shortest", str(out),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=30", "-i", str(mix),
            "-vf", f"ass='{ass_filter}'", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "320k", "-shortest", str(out),
        ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "FFmpeg karaoke export failed")


@app.post("/api/projects/{pid}/karaoke-background")
async def upload_karaoke_background(pid: str, request: Request, file: UploadFile = File(...)):
    _project_for_actor(request, pid)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(400, "Background non supportato: usa JPG, PNG o WEBP")
    folder = pdir(pid) / "karaoke"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"background-{uuid.uuid4().hex[:12]}{suffix}"
    target = folder / name
    _copy_limited(file.file, target)
    return {"name": name}


def _render_configured_project_export(pid: str, req: ProjectExportRequest) -> tuple[Path, str, str, str]:
    source_project = load_project(pid)
    fmt = req.format.lower()
    validate_project_files(source_project)
    safe_stem = SAFE_DOWNLOAD_RE.sub("_", Path(req.filename).stem).strip(" ._")[:180] or "project"
    if fmt == "mta":
        export_project = _musical_export_project(source_project)
        if export_project.target == "DAW":
            export_project.target = req.mta_target or "MTA16"
        ext = "mta8" if export_project.target == "MTA8" else "mta16"
        out = pdir(pid) / f"configured-export.{ext}"
        limit = 8 if export_project.target == "MTA8" else 16
        if len(export_project.tracks) > limit or req.slots:
            known = {track.id for track in export_project.tracks}
            requested_slots = [
                slot.model_copy(update={"track_ids": [track_id for track_id in slot.track_ids if track_id in known]})
                for slot in req.slots
            ]
            requested_slots = [slot for slot in requested_slots if slot.track_ids]
            slots = validate_slot_mapping(export_project, requested_slots, req.mta_device_profile)
            export_mta(export_project, out, slots, req.mta_device_profile)
        else:
            export_mta(export_project, out, profile=req.mta_device_profile)
        media_type = "application/octet-stream"
    elif fmt in {"wav", "mp3", "mlive_mp3", "mp3g", "flac"}:
        if fmt == "mp3g" and not any(not line.disabled and not line.deleted and str(line.text).strip() for line in source_project.lyrics):
            raise ValueError("MP3+G export requires synchronized lyrics")
        ext = "mp3" if fmt == "mlive_mp3" else ("zip" if fmt == "mp3g" else fmt)
        out = pdir(pid) / f"configured-export.{ext}"
        export_project = _audible_export_project(source_project)
        audio_out = pdir(pid) / "configured-export-mp3g.mp3" if fmt == "mp3g" else out
        if fmt == "mp3g":
            render_mix(
                export_project,
                audio_path,
                audio_out,
                fmt="mp3",
                bitrate=f"{int(req.mp3_bitrate_kbps)}k",
                sample_rate=int(req.sample_rate),
                wav_bit_depth=int(req.wav_bit_depth),
                flac_compression=int(req.flac_compression),
                normalize_peak_db=float(req.normalize_peak_db) if req.normalize_audio else None,
            )
        else:
            render_mix(
                export_project,
                audio_path,
                audio_out,
                fmt="mp3" if fmt == "mlive_mp3" else fmt,
                bitrate=f"{int(req.mp3_bitrate_kbps)}k",
                sample_rate=int(req.sample_rate),
                wav_bit_depth=int(req.wav_bit_depth),
                flac_compression=int(req.flac_compression),
                normalize_peak_db=float(req.normalize_peak_db) if req.normalize_audio else None,
            )
        if fmt == "mlive_mp3":
            embed_mlive_merish_metadata(out, source_project)
        elif fmt == "mp3g":
            build_mp3g_zip(source_project, audio_out, out, safe_stem, media_duration_ms(audio_out))
            audio_out.unlink(missing_ok=True)
        media_type = {"wav": "audio/wav", "mp3": "audio/mpeg", "mlive_mp3": "audio/mpeg", "mp3g": "application/zip", "flac": "audio/flac"}[fmt]
    elif fmt == "mp4":
        export_project = _audible_export_project(source_project)
        if not export_project.lyrics:
            raise ValueError("MP4 karaoke export requires synchronized lyrics")
        ext = "mp4"
        out = pdir(pid) / "configured-export.mp4"
        _render_karaoke_video(pid, export_project, out, req)
        media_type = "video/mp4"
    else:
        raise ValueError("unsupported export format")
    return out, f"{safe_stem}.{ext}", media_type, fmt


@app.post("/api/projects/{pid}/configured-export")
def configured_project_export(pid: str, req: ProjectExportRequest, request: Request):
    _project_for_actor(request, pid)
    try:
        out, final_name, media_type, fmt = _render_configured_project_export(pid, req)
        if req.output_path:
            if not NATIVE_SINGLE_USER:
                raise HTTPException(403, "Filesystem export path is available only in native mode")
            destination = Path(req.output_path).expanduser().resolve()
            if destination.suffix.lower() != Path(final_name).suffix.lower():
                destination = destination.with_suffix(Path(final_name).suffix)
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Write to a sibling temporary file and replace once. Some native file
            # dialogs may leave the previous file visible while export is running;
            # atomic replace prevents a stale copy from reappearing after overwrite.
            temp_destination = destination.with_name(f".{destination.name}.export-{uuid.uuid4().hex}.tmp")
            try:
                shutil.copyfile(out, temp_destination)
                with temp_destination.open("rb") as handle:
                    os.fsync(handle.fileno())
                os.replace(temp_destination, destination)
                try:
                    dir_fd = os.open(str(destination.parent), os.O_RDONLY)
                    try:
                        os.fsync(dir_fd)
                    finally:
                        os.close(dir_fd)
                except OSError:
                    pass
            finally:
                temp_destination.unlink(missing_ok=True)
            return {"ok": True, "native": True, "path": str(destination), "filename": destination.name, "format": fmt}
        return FileResponse(out, filename=final_name, media_type=media_type)
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Configured project export failed")
        raise HTTPException(400, f"export failed: {str(exc)[:300]}") from exc


def _configured_export_worker(job_id: str, pid: str, req_data: dict) -> None:
    try:
        _media_job_update(job_id, status="running", progress=12, message="Preparazione export")
        req = ProjectExportRequest.model_validate(req_data)
        out, final_name, media_type, fmt = _render_configured_project_export(pid, req)
        _media_job_update(job_id, progress=94, message="Preparazione download")
        _media_job_update(
            job_id,
            status="completed",
            progress=100,
            message="Export completato",
            result={
                "download_url": f"/api/media-jobs/{job_id}/download",
                "filename": final_name,
                "format": fmt,
                "media_type": media_type,
                "path": str(out),
            },
        )
    except Exception as exc:
        LOGGER.exception("Configured export job failed")
        _media_job_update(job_id, status="failed", progress=0, message="Export fallito", error=str(exc)[-1200:])


@app.post("/api/projects/{pid}/configured-export-jobs")
def start_configured_project_export_job(pid: str, req: ProjectExportRequest, request: Request):
    _project_for_actor(request, pid)
    now = time.time()
    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "kind": "project-export",
        "project_id": pid,
        "status": "queued",
        "progress": 5,
        "message": "Export in coda",
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    threading.Thread(
        target=_configured_export_worker,
        args=(job_id, pid, req.model_dump(mode="json")),
        daemon=True,
        name=f"project-export-{job_id}",
    ).start()
    return _media_job_public(job)




def _karaoke_export_worker(job_id: str, pid: str, background_path: str | None, include_chords: bool = True) -> None:
    bg = Path(background_path) if background_path else None
    try:
        project = load_project(pid)
        if not project.lyrics:
            raise RuntimeError("Il progetto non contiene lyrics sincronizzate")
        _media_job_update(job_id, status="running", progress=10, message="Rendering audio progetto")
        mix = pdir(pid) / f"karaoke-{job_id}.wav"
        ass = pdir(pid) / f"karaoke-{job_id}.ass"
        out = pdir(pid) / f"karaoke-{job_id}.mp4"
        render_mix(project, audio_path, mix, fmt="wav", sample_rate=48000, wav_bit_depth=24)
        build_karaoke_ass(
            ass,
            title=project.title,
            artist=project.artist,
            lyrics=project.lyrics,
            chords=transpose_chords(project.chords, project.pitch_semitones),
            include_chords=include_chords,
        )
        _media_job_update(job_id, progress=55, message="Rendering video karaoke")
        ass_filter = str(ass).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        if bg and bg.is_file():
            cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(bg), "-i", str(mix), "-vf", f"scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,ass='{ass_filter}'", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-shortest", str(out)]
        else:
            cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30", "-i", str(mix), "-vf", f"ass='{ass_filter}'", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-shortest", str(out)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode or not out.is_file():
            raise RuntimeError(proc.stderr.strip() or "FFmpeg karaoke export failed")
        _media_job_update(job_id, status="completed", progress=100, message="MP4 karaoke completato", result={"download_url": f"/api/media-jobs/{job_id}/download", "filename": _download_name(project.title or "karaoke", "mp4"), "format": "mp4", "media_type": "video/mp4", "path": str(out)})
    except Exception as exc:
        LOGGER.exception("Karaoke export failed")
        _media_job_update(job_id, status="failed", progress=0, message="Export MP4 fallito", error=str(exc)[-1200:])
    finally:
        if bg:
            bg.unlink(missing_ok=True)


@app.post("/api/projects/{pid}/karaoke-export-jobs")
async def start_karaoke_export_job(
    pid: str,
    request: Request,
    include_chords: bool = True,
    background: UploadFile | None = File(default=None),
):
    project = _project_for_actor(request, pid)
    if not project.lyrics:
        raise HTTPException(409, "L'export MP4 richiede lyrics sincronizzate")
    background_path: Path | None = None
    if background and background.filename:
        suffix = Path(background.filename).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(400, "Background non supportato: usa JPG, PNG o WEBP")
        background_path = pdir(pid) / f"karaoke-background-{uuid.uuid4().hex[:10]}{suffix}"
        _copy_limited(background.file, background_path)
    now = time.time()
    job_id = uuid.uuid4().hex[:16]
    job = {"id": job_id, "kind": "project-export", "project_id": pid, "status": "queued", "progress": 5, "message": "Export MP4 in coda", "created_at": now, "updated_at": now, "result": None, "error": None}
    with MEDIA_JOB_LOCK:
        MEDIA_JOBS[job_id] = job
    threading.Thread(
        target=_karaoke_export_worker,
        args=(job_id, pid, str(background_path) if background_path else None, include_chords),
        daemon=True,
        name=f"karaoke-export-{job_id}",
    ).start()
    return _media_job_public(job)

@app.get("/api/projects/{pid}/export")
def export(pid: str, request: Request, format: str = "mta"):
    project = _project_for_actor(request, pid)
    try:
        validate_project_files(project)
        export_project = _audible_export_project(project)
        if format == "mta":
            if export_project.target == "DAW":
                raise HTTPException(409, "DAW projects require choosing MTA8 or MTA16 in configured export")
            if len(export_project.tracks) > (8 if export_project.target == "MTA8" else 16):
                raise HTTPException(409, "MTA export mapping required; use /export-plan and /export-mta")
            ext = "mta8" if export_project.target == "MTA8" else "mta16"
            out = pdir(pid) / f"export.{ext}"
            export_mta(_musical_export_project(project), out)
            media_type = "application/octet-stream"
        elif format in {"wav", "mp3", "mlive_mp3", "mp3g", "flac"}:
            if format == "mp3g" and not any(not line.disabled and not line.deleted and str(line.text).strip() for line in project.lyrics):
                raise HTTPException(409, "L'export MP3+G richiede lyrics sincronizzate")
            ext = "mp3" if format == "mlive_mp3" else ("zip" if format == "mp3g" else format)
            out = pdir(pid) / f"export.{ext}"
            audio_out = pdir(pid) / "export-mp3g.mp3" if format == "mp3g" else out
            render_mix(export_project, audio_path, audio_out, fmt="mp3" if format in {"mlive_mp3", "mp3g"} else ext, bitrate="320k")
            if format == "mlive_mp3":
                embed_mlive_merish_metadata(out, project)
            elif format == "mp3g":
                build_mp3g_zip(project, audio_out, out, SAFE_DOWNLOAD_RE.sub("_", project.title or "karaoke").strip(" ._") or "karaoke", media_duration_ms(audio_out))
                audio_out.unlink(missing_ok=True)
            media_type = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac", "zip": "application/zip"}[ext]
        else:
            raise HTTPException(400, "unsupported export format")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "export failed") from exc
    return FileResponse(out, filename=_download_name(project.title, ext), media_type=media_type)


if __name__ == "__main__":
    import uvicorn

    tls_cert = os.getenv("MTA_TLS_CERTFILE")
    tls_key = os.getenv("MTA_TLS_KEYFILE")
    if bool(tls_cert) != bool(tls_key):
        raise RuntimeError("Both MTA_TLS_CERTFILE and MTA_TLS_KEYFILE are required for HTTPS")
    options = {"ssl_certfile": tls_cert, "ssl_keyfile": tls_key} if tls_cert else {}
    uvicorn.run("app.main:app", host=os.getenv("MTA_HOST", "127.0.0.1"), port=int(os.getenv("MTA_PORT", "8080")), **options)

# Native-desktop ACE-Step lifecycle. Never expose installer/process controls from
# multi-user web/Docker deployments.
from . import ace_step_desktop_manager as _ace_desktop
from .ace_step_live_smoke import test_live_inference as _ace_live_test
_ace_test_guard = threading.RLock()
_ace_test_state: dict = {'state': 'idle'}


def _ace_native_only(request: Request) -> None:
    _actor(request)
    if not NATIVE_SINGLE_USER:
        raise HTTPException(403, 'ACE-Step desktop management is only available in native single-user mode')


@app.get('/api/ai-arranger/desktop-ace/status')
def desktop_ace_status(request: Request):
    _ace_native_only(request)
    with _ace_test_guard:
        result = dict(_ace_test_state)
    return {'desktop':{**_ace_desktop.status(), 'connection':_ace_desktop.connection()}, 'inference_test':result}


@app.get('/api/native/ai-workers/settings')
def native_ai_workers_settings(request: Request):
    _ace_native_only(request)
    from .native_ai_routing import public_settings
    return public_settings()


@app.get('/api/native/ai-workers/pending')
def native_ai_workers_pending(request: Request):
    _ace_native_only(request)
    from .ai_native_remote_journal import list_pending
    return {'pending': list_pending()}


@app.get('/api/native/ai-workers/remote-history/{kind}')
def native_ai_workers_remote_history(request: Request, kind: str, limit: int = 50,
                                     offset: int = 0, state: str | None = None):
    """Read-only rediscovery after native restart; never starts inference.

    Discovery uses only the current saved HTTPS endpoint and its private token.
    Discovered requests are *not* local pending receipts and cannot be imported
    until provenance and artifact type have been re-verified separately.
    """
    _ace_native_only(request)
    from .native_ai_routing import _read, KINDS
    from .ai_remote_client import list_remote_requests, RemoteAIError
    if kind not in KINDS:
        raise HTTPException(404, 'Unknown AI worker')
    config = _read().get('workers', {}).get(kind, {})
    if (not isinstance(config, dict) or config.get('mode') != 'remote'
            or not config.get('url') or not config.get('token')):
        raise HTTPException(409, 'Remote AI worker is not configured')
    try:
        result = list_remote_requests(config['url'], config['token'],
                                      limit=limit, offset=offset, state=state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RemoteAIError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {'kind': kind, **result}


@app.get('/api/native/ai-workers/remote-history/{kind}/artifact/{request_id}')
def native_ai_workers_discovered_artifact(request: Request, kind: str, request_id: str):
    """Read-only download of a server-discovered result, never infer or import.

    Discovery is repeated with the configured worker token to establish ownership
    independently of any local journal. No discovered result can mutate a project.
    """
    _ace_native_only(request)
    from .native_ai_routing import _read, KINDS
    from .ai_remote_client import (remote_request_status, recover_after_lost_response,
                                   RemoteAIError)
    if kind not in KINDS:
        raise HTTPException(404, 'Unknown AI worker')
    from .ai_request_dedup import _KEY
    if not _KEY.fullmatch(request_id):
        raise HTTPException(400, 'Invalid remote request identifier')
    settings = _read().get('workers', {}).get(kind, {})
    if (not isinstance(settings, dict) or settings.get('mode') != 'remote'
            or not settings.get('url') or not settings.get('token')):
        raise HTTPException(409, 'Remote AI worker is not configured')
    try:
        # Server verifies ownership against the bearer token for this exact key.
        # Avoid scanning a bounded history: older retained jobs must remain recoverable.
        status = remote_request_status(settings['url'], settings['token'], request_id)
        if status.get('state') != 'completed':
            raise HTTPException(404, 'Completed request not found for this worker')
        strict = os.getenv('MTA_REMOTE_AI_REQUIRE_ATTESTATION', '').strip().lower() in ('1', 'true', 'yes', 'on')
        payload, mime, _ = recover_after_lost_response(
            settings['url'], settings['token'], request_id, require_attestation=strict)
        if mime not in ('application/json', 'audio/wav', 'application/zip') or not isinstance(payload, bytes) or not payload:
            raise ValueError('Unsupported or empty remote result')
        suffix = {'application/json': 'json', 'audio/wav': 'wav', 'application/zip': 'zip'}[mime]
        return Response(content=payload, media_type=mime,
                        headers={'Content-Disposition': f'attachment; filename="mta-discovered-{request_id}.{suffix}"',
                                 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except RemoteAIError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/api/native/ai-workers/pending/{request_id}/status')
def native_ai_workers_pending_status(request: Request, request_id: str):
    _ace_native_only(request)
    from .ai_native_remote_journal import read_owned_pending
    from .native_ai_routing import _read
    from .ai_remote_client import remote_request_status, RemoteAIError
    try:
        item = read_owned_pending(request_id)
        kind, url = item.get('kind'), item.get('url')
        settings = _read().get('workers', {}).get(kind, {}) if isinstance(kind, str) else {}
        if not kind or settings.get('mode') != 'remote' or settings.get('url') != url or not settings.get('token'):
            raise ValueError('Original remote worker settings are unavailable; no inference was retried')
        return {'request_id': request_id, 'kind': kind,
                'remote': remote_request_status(url, settings['token'], request_id)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RemoteAIError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.get('/api/native/ai-workers/pending/{request_id}/artifact')
def native_ai_workers_pending_artifact(request: Request, request_id: str):
    """Download an already-completed result read-only, without clearing the journal.

    The original native workflow must still consume and validate the recovered
    result before its own journal entry may be retired.
    """
    _ace_native_only(request)
    from .ai_native_remote_journal import read_owned_pending
    from .native_ai_routing import _read
    from .ai_remote_client import recover_after_lost_response, RemoteAIError
    try:
        item = read_owned_pending(request_id)
        kind, url = item.get('kind'), item.get('url')
        settings = _read().get('workers', {}).get(kind, {}) if isinstance(kind, str) else {}
        if not kind or settings.get('mode') != 'remote' or settings.get('url') != url or not settings.get('token'):
            raise ValueError('Original remote worker settings unavailable; no inference was retried')
        strict = os.getenv('MTA_REMOTE_AI_REQUIRE_ATTESTATION', '').strip().lower() in ('1', 'true', 'yes', 'on')
        payload, mime, job_id = recover_after_lost_response(url, settings['token'], request_id,
                                                              require_attestation=strict)
        if mime not in ('application/json', 'audio/wav', 'application/zip'):
            raise ValueError('Unsupported remote result content type')
        if not isinstance(payload, bytes) or not payload:
            raise ValueError('Empty remote result')
        suffix = {'application/json': 'json', 'audio/wav': 'wav', 'application/zip': 'zip'}[mime]
        return Response(content=payload, media_type=mime,
                        headers={'Content-Disposition': f'attachment; filename="mta-recovered-{request_id}.{suffix}"',
                                 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except RemoteAIError as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post('/api/native/ai-workers/pending/{request_id}/import-wav/{pid}')
async def native_ai_workers_import_recovered_wav(request: Request, request_id: str, pid: str):
    """Fetch and import a recovered WAV once per project, across browser windows.

    Never submits a remote inference; the durable pending journal is retained.
    """
    import io
    from .ai_project_lock import project_publication_lock
    _ace_native_only(request)
    _project_for_actor(request, pid)
    if not re.fullmatch(r'[0-9a-f]{32}', request_id):
        raise HTTPException(400, 'Invalid pending request identifier')
    track_name = 'Recovered AI ' + request_id
    # A durable receipt survives later track renames. Historical projects may
    # not have the field yet, so retain the name check for compatibility.
    # Share a canonical receipt with server-history discovery. The legacy pending
    # receipt is still honored for projects created by earlier r208 builds.
    from .ai_native_remote_journal import read_owned_pending
    try:
        owned = read_owned_pending(request_id)
        kind = owned.get('kind')
        from .native_ai_routing import KINDS
        if kind not in KINDS:
            raise ValueError('Unknown original AI worker')
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    receipt = f'wav:{kind}:{request_id}'
    legacy_receipt = f'wav:pending:{request_id}'
    # Lock before checking the project: independent sessions/processes must
    # never both pass the duplicate check based on a stale project snapshot.
    with project_publication_lock(pid):
        current_project = _project_for_actor(request, pid)
        if (receipt in getattr(current_project, 'recovered_ai_imports', [])
                or legacy_receipt in getattr(current_project, 'recovered_ai_imports', [])
                or any(track.name == track_name for track in current_project.tracks)):
            raise HTTPException(409, 'This recovered result was already imported')
        recovered = native_ai_workers_pending_artifact(request, request_id)
        if recovered.media_type != 'audio/wav':
            raise HTTPException(415, 'Recovered artifact is not WAV audio')
        payload = recovered.body
        if (len(payload) < 44 or payload[:4] != b'RIFF'
                or payload[8:12] != b'WAVE'):
            raise HTTPException(422, 'Recovered artifact is not a valid WAV container')
        uploaded = UploadFile(filename=f'mta-recovered-{request_id}.wav', file=io.BytesIO(payload))
        return await _add_track_under_project_lock(pid, request, uploaded, name=track_name,
                                                   recovery_receipt=receipt)


@app.post('/api/native/ai-workers/remote-history/{kind}/import-wav/{request_id}/{pid}')
async def native_ai_workers_import_discovered_wav(request: Request, kind: str, request_id: str, pid: str):
    """Explicitly associate a verified, server-owned WAV with the selected project.

    This path does not use or forge a local pending journal and never submits
    inference. The operator chooses the project; the server authenticates the
    stored request and verifies the recovered artifact before publication.
    """
    import io
    from .native_ai_routing import KINDS
    from .ai_project_lock import project_publication_lock
    from .ai_worker_artifacts import _verify_wav_bytes
    _ace_native_only(request)
    _project_for_actor(request, pid)
    if kind not in KINDS:
        raise HTTPException(404, 'Unknown remote worker')
    if not re.fullmatch(r'[0-9a-f]{32}', request_id):
        raise HTTPException(400, 'Invalid remote request identifier')
    track_name = f'Recovered AI {kind} {request_id}'
    receipt = f"wav:{kind}:{request_id}"
    with project_publication_lock(pid):
        project = _project_for_actor(request, pid)
        if (receipt in project.recovered_ai_imports
                or f'wav:pending:{request_id}' in project.recovered_ai_imports
                or any(track.name == track_name for track in project.tracks)):
            raise HTTPException(409, 'This remote result was already imported')
        result = native_ai_workers_discovered_artifact(request, kind, request_id)
        if result.media_type != 'audio/wav':
            raise HTTPException(415, 'Discovered result is not WAV audio')
        try:
            _verify_wav_bytes(result.body)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, 'Invalid remote WAV audio') from exc
        uploaded = UploadFile(filename=f'mta-discovered-{request_id}.wav',
                              file=io.BytesIO(result.body))
        return await _add_track_under_project_lock(pid, request, uploaded, name=track_name,
                                                   recovery_receipt=receipt)


@app.post('/api/native/ai-workers/pending/{request_id}/import-json/{pid}')
def native_ai_workers_import_recovered_json(request: Request, request_id: str, pid: str,
                                            _discovered_kind: str | None = None):
    """Apply a completed Whisper/Chords JSON result exactly once to a project.

    Provenance and events are saved in the same project transaction, guarded
    across server processes. No remote POST or speculative metering occurs.
    """
    import io, zipfile
    from .ai_project_lock import project_publication_lock
    from .ai_native_remote_journal import read_owned_pending
    from .models import LyricLine, Chord
    _ace_native_only(request)
    _project_for_actor(request, pid)
    if not re.fullmatch(r'[0-9a-f]{32}', request_id):
        raise HTTPException(400, 'Invalid pending request identifier')
    if _discovered_kind is None:
        try:
            owned = read_owned_pending(request_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        kind = owned.get('kind')
    else:
        kind = _discovered_kind
    if kind not in ('whisper', 'chords-ml'):
        raise HTTPException(415, 'Only Whisper and Chords JSON can be applied to the project')
    with project_publication_lock(pid):
        project = _project_for_actor(request, pid)
        receipt = f'{kind}:{request_id}'
        if receipt in project.recovered_ai_imports:
            raise HTTPException(409, 'This recovered result was already applied')
        recovered = (native_ai_workers_discovered_artifact(request, kind, request_id)
                     if _discovered_kind is not None else native_ai_workers_pending_artifact(request, request_id))
        if recovered.media_type not in ('application/json', 'application/zip'):
            raise HTTPException(415, 'Recovered result is not JSON or a JSON artifact archive')
        if len(recovered.body) > 32 * 1024 * 1024:
            raise HTTPException(413, 'Recovered artifact is too large')
        try:
            document_name = 'transcript.json' if kind == 'whisper' else 'chords.json'
            field = 'lines' if kind == 'whisper' else 'chords'
            if recovered.media_type == 'application/zip':
                with zipfile.ZipFile(io.BytesIO(recovered.body)) as bundle:
                    entries = bundle.infolist()
                    # Reject ambiguous/unsafe ZIP metadata before extracting anything.
                    # Other worker metadata files remain supported, but must be
                    # bounded, regular files with unique portable names.
                    from .ai_worker_artifacts import SAFE_NAME
                    names = [entry.filename for entry in entries]
                    if (not entries or len(entries) > 32
                            or len(set(names)) != len(names)
                            or any(not SAFE_NAME.fullmatch(entry.filename)
                                   or entry.is_dir()
                                   or (entry.external_attr >> 16) & 0o170000 == 0o120000
                                   or entry.file_size > 8 * 1024 * 1024
                                   for entry in entries)
                            or sum(entry.file_size for entry in entries) > 32 * 1024 * 1024):
                        raise ValueError('Unsafe or oversized recovered archive')
                    matches = [item for item in entries if item.filename == document_name]
                    if len(matches) != 1:
                        raise ValueError('Missing recovered annotation')
                    raw_json = bundle.read(matches[0])
            else:
                raw_json = recovered.body
            if len(raw_json) > 8 * 1024 * 1024:
                raise ValueError('Oversized annotation')
            document = json.loads(raw_json)
            events = document.get(field) if isinstance(document, dict) else None
            if not isinstance(events, list) or not events or len(events) > 20000:
                raise ValueError('Expected a nonempty bounded sequence of events')
            cls = LyricLine if kind == 'whisper' else Chord
            parsed = [cls.model_validate(event) for event in events]
        except (ValueError, TypeError, KeyError, OSError, zipfile.BadZipFile) as exc:
            raise HTTPException(422, 'Invalid recovered music annotations') from exc
        # Timestamps in recovered JSON refer to the original source; callers
        # must explicitly choose a timeline-aligned source before applying.
        # Never silently replace manually edited content.
        if kind == 'whisper':
            if project.lyrics:
                raise HTTPException(409, 'Existing lyrics must be cleared or merged manually')
            project.lyrics = parsed
            project.lyrics_engine = 'Recovered remote Whisper'
        else:
            if project.chords:
                raise HTTPException(409, 'Existing chords must be cleared or merged manually')
            project.chords = parsed
            project.chords_engine = 'Recovered remote Chords'
        project.recovered_ai_imports.append(receipt)
        save_project(project)
        return {'ok': True, 'kind': kind, 'count': len(parsed), 'request_id': request_id,
                'project_id': pid, 'journal_preserved': True}


@app.post('/api/native/ai-workers/pending/{request_id}/import-stems/{pid}')
def native_ai_workers_import_recovered_stems(request: Request, request_id: str, pid: str,
                                             _discovered_kind: str | None = None):
    """Import a verified multi-WAV worker archive as one durable project update.

    The original pending record is retained: no POST to the remote inference
    endpoint occurs here. Project locking serializes cross-process retries.
    """
    import io, zipfile, hashlib
    from .ai_project_lock import project_publication_lock
    from .ai_native_remote_journal import read_owned_pending
    from .ai_worker_artifacts import _verify_wav_bytes, SAFE_NAME, MAX_ARTIFACT_BYTES
    from . import ai_recovered_stem_transaction as stem_transaction
    _ace_native_only(request)
    _project_for_actor(request, pid)
    if not re.fullmatch(r'[0-9a-f]{32}', request_id):
        raise HTTPException(400, 'Invalid pending request identifier')
    if _discovered_kind is None:
        try:
            owned = read_owned_pending(request_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        kind = owned.get('kind')
    else:
        kind = _discovered_kind
    if kind not in ('demucs', 'drumsep', 'sam-audio', 'singer-separation', 'backing-vocals'):
        raise HTTPException(415, 'This adapter does not produce importable audio stems')
    with project_publication_lock(pid):
        stem_transaction.reconcile(pid)
        project = _project_for_actor(request, pid)
        receipt = f'stems:{kind}:{request_id}'
        if receipt in project.recovered_ai_imports:
            raise HTTPException(409, 'These recovered stems were already imported')
        recovered = (native_ai_workers_discovered_artifact(request, kind, request_id)
                     if _discovered_kind is not None else native_ai_workers_pending_artifact(request, request_id))
        if recovered.media_type != 'application/zip' or len(recovered.body) > MAX_ARTIFACT_BYTES:
            raise HTTPException(415, 'Recovered result must be a bounded artifact ZIP')
        try:
            with zipfile.ZipFile(io.BytesIO(recovered.body)) as archive:
                entries = archive.infolist()
                if not entries or len(entries) > 17:
                    raise ValueError('Invalid artifact count')
                if len({entry.filename.casefold() for entry in entries}) != len(entries):
                    raise ValueError('Duplicate archive entry (including case-insensitive collisions)')
                if any(not SAFE_NAME.fullmatch(entry.filename) or entry.is_dir() or
                       (entry.external_attr >> 16) & 0o170000 == 0o120000 for entry in entries):
                    raise ValueError('Unsafe archive entry')
                manifest_entries = [entry for entry in entries if entry.filename == 'manifest.json']
                if len(manifest_entries) != 1 or manifest_entries[0].file_size > 256000:
                    raise ValueError('Missing output manifest')
                manifest = json.loads(archive.read('manifest.json'))
                if not isinstance(manifest, dict) or manifest.get('version') != 1 or not isinstance(manifest.get('files'), list):
                    raise ValueError('Unsupported output manifest')
                specs = manifest['files']
                if not specs or len(specs) > 16 or len(specs) != len(entries) - 1:
                    raise ValueError('Manifest does not describe archive')
                # A set comparison alone misses duplicate specifications.  Every
                # member must have exactly one manifest entry, including metadata.
                names = [spec.get('name') if isinstance(spec, dict) else None for spec in specs]
                if (len({name.casefold() for name in names if isinstance(name, str)}) != len(names) or
                        set(names) != {entry.filename for entry in entries if entry.filename != 'manifest.json'}):
                    raise ValueError('Manifest entry mismatch')
                if any(entry.flag_bits & 0x1 for entry in entries):
                    raise ValueError('Encrypted archive entry')
                audio = []
                total = 0
                for spec in specs:
                    if not isinstance(spec, dict):
                        raise ValueError('Invalid artifact entry')
                    name, media = spec.get('name'), spec.get('type')
                    if media not in ('audio/wav', 'application/json', 'text/plain'):
                        raise ValueError('Unsupported manifest media type')
                    info = archive.getinfo(name)
                    total += info.file_size
                    if info.file_size > MAX_ARTIFACT_BYTES or total > MAX_ARTIFACT_BYTES:
                        raise ValueError('Expanded archive exceeds limit')
                    payload = archive.read(name)
                    digest = spec.get('sha256')
                    if digest is not None and (not isinstance(digest, str) or
                          hashlib.sha256(payload).hexdigest() != digest):
                        raise ValueError('Artifact digest mismatch')
                    if media == 'audio/wav':
                        if not name.endswith('.wav'):
                            raise ValueError('Expected WAV extension')
                        _verify_wav_bytes(payload)
                        audio.append((name, payload))
                    elif media == 'application/json':
                        if not name.endswith('.json'):
                            raise ValueError('Expected JSON extension')
                        json.loads(payload)
                    elif media == 'text/plain' and not name.endswith('.txt'):
                        raise ValueError('Expected text extension')
                if not audio or len(audio) > 16:
                    raise ValueError('No WAV stems in recovered archive')
        except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
            raise HTTPException(422, 'Invalid recovered stem archive') from exc
        stem_transaction.begin(pid, receipt)
        created = []
        try:
            for name, payload in audio:
                uploaded = UploadFile(filename=name, file=io.BytesIO(payload))
                filename, dst, duration = _save_upload(pid, uploaded, int(project.sample_rate))
                created.append(dst)
                stem = Path(name).stem.replace('_', ' ').title()
                track = Track(id=uuid.uuid4().hex[:10], name=f'Recovered {stem}'[:200],
                              filename=filename, duration_ms=duration,
                              sample_rate=int(project.sample_rate),
                              clips=[Clip(id=uuid.uuid4().hex[:10], source_start_ms=0,
                                          source_end_ms=duration, timeline_start_ms=0)])
                project.tracks.append(track)
                _register_track_source_in_library(project, track, f'Recovered AI stem: {name}')
            project.recovered_ai_imports.append(receipt)
            save_project(project)
        except Exception:
            # Retain journal on failure: on-disk state is reconciled under
            # the project lock before the next import.
            raise
        stem_transaction.reconcile(pid)
        return {'ok': True, 'kind': kind, 'count': len(audio), 'request_id': request_id,
                'project_id': pid, 'journal_preserved': True}


@app.post('/api/native/ai-workers/remote-history/{kind}/import-json/{request_id}/{pid}')
def native_ai_workers_import_discovered_json(request: Request, kind: str, request_id: str, pid: str):
    """Operator-selected project import of authenticated historical annotations.

    No local pending entry is synthesized, and the original worker output is
    fetched and validated by the same pipeline as durable journal recovery.
    """
    return native_ai_workers_import_recovered_json(request, request_id, pid, _discovered_kind=kind)


@app.post('/api/native/ai-workers/remote-history/{kind}/import-stems/{request_id}/{pid}')
def native_ai_workers_import_discovered_stems(request: Request, kind: str, request_id: str, pid: str):
    """Operator-selected atomic stem import after authenticated rediscovery."""
    return native_ai_workers_import_recovered_stems(request, request_id, pid, _discovered_kind=kind)


@app.post('/api/native/ai-workers/settings')
def native_ai_workers_configure(request: Request, body: dict):
    _ace_native_only(request)
    from .native_ai_routing import configure
    try:
        return configure(kind=body.get('kind',''),mode=body.get('mode',''),
                         url=body.get('url',''),token=body.get('token',''))
    except (ValueError,OSError) as exc:
        raise HTTPException(400,str(exc)) from exc


@app.post('/api/ai-arranger/desktop-ace/connection')
def desktop_ace_connection(request: Request, body: dict):
    _ace_native_only(request)
    try:
        return _ace_desktop.configure_connection(mode=body.get('mode', ''),
                                                 url=body.get('url', ''), token=body.get('token', ''))
    except (ValueError, OSError, RuntimeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/ai-arranger/desktop-ace/install')
def desktop_ace_install(request: Request, body: dict):
    _ace_native_only(request)
    try:
        return _ace_desktop.install(confirmed=body.get('consent') is True)
    except (ValueError,RuntimeError) as exc:
        raise HTTPException(400,str(exc)) from exc


@app.post('/api/ai-arranger/desktop-ace/start')
def desktop_ace_start(request: Request, body: dict):
    _ace_native_only(request)
    try:
        return _ace_desktop.start_server(confirmed_model_download=body.get('consent') is True)
    except (ValueError,RuntimeError,OSError) as exc:
        raise HTTPException(400,str(exc)) from exc


def _run_ace_test() -> None:
    global _ace_test_state
    try:
        result=_ace_live_test(seconds=5,timeout_seconds=1200)
        with _ace_test_guard:
            _ace_test_state={'state':'passed' if result.get('verified') else 'failed', 'result':result}
    except Exception as exc:
        with _ace_test_guard:
            _ace_test_state={'state':'failed','error':str(exc)[:300]}


@app.post('/api/ai-arranger/desktop-ace/stop')
def desktop_ace_stop(request: Request, body: dict):
    _ace_native_only(request)
    return _ace_desktop.stop_server(disable_auto_start=body.get('disable_auto_start') is True)


@app.post('/api/ai-arranger/desktop-ace/test')
def desktop_ace_test(request: Request):
    global _ace_test_state
    _ace_native_only(request)
    with _ace_test_guard:
        if _ace_test_state.get('state')=='running': return dict(_ace_test_state)
        _ace_test_state={'state':'running'}
    threading.Thread(target=_run_ace_test,daemon=True,name='mta-ace-smoke').start()
    return {'state':'running'}


@app.get('/api/projects/{pid}/recovered-stem-orphans')
def recovered_stem_orphans_review(request: Request, pid: str):
    _project_for_actor(request, pid)
    from .ai_project_lock import project_publication_lock
    from .ai_recovered_stem_transaction import review_preserved
    with project_publication_lock(pid):
        return review_preserved(pid)


@app.get('/api/projects/{pid}/recovered-stem-orphans/quarantine')
def recovered_stem_quarantine_review(request: Request, pid: str):
    _project_for_actor(request, pid)
    from .ai_project_lock import project_publication_lock
    from .ai_recovered_stem_transaction import review_quarantine
    with project_publication_lock(pid):
        return review_quarantine(pid)


@app.post('/api/projects/{pid}/recovered-stem-orphans/restore')
def recovered_stem_quarantine_restore(request: Request, pid: str, body: dict):
    _project_for_actor(request, pid)
    name = body.get('quarantine_name')
    if not isinstance(name, str):
        raise HTTPException(400, 'Invalid quarantine selection')
    from .ai_project_lock import project_publication_lock
    from .ai_recovered_stem_transaction import restore_quarantined
    with project_publication_lock(pid):
        try:
            return restore_quarantined(pid, name)
        except (ValueError, RuntimeError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc


@app.post('/api/projects/{pid}/recovered-stem-orphans/quarantine')
def recovered_stem_orphans_quarantine(request: Request, pid: str, body: dict):
    _project_for_actor(request, pid)
    from .ai_project_lock import project_publication_lock
    from .ai_recovered_stem_transaction import quarantine_preserved
    receipt, path = body.get('receipt'), body.get('file')
    if not isinstance(receipt, str) or not isinstance(path, str):
        raise HTTPException(400, 'Invalid preserved stem selection')
    with project_publication_lock(pid):
        try:
            return quarantine_preserved(pid, receipt, path)
        except (ValueError, RuntimeError, OSError) as exc:
            raise HTTPException(409, str(exc)) from exc
