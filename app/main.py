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
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles

from .audio_engine import auto_align_ms, delete_range, delete_song_range, ensure_clips, estimate_bpm, generate_metronome_wav, media_duration_ms, project_duration_ms, render_mix, render_track, render_track_export, shift_track, waveform_peaks
from .codec import export_mta, ffprobe, import_mta, resolve_mta_device_profile, suggested_slots, validate_slot_mapping
from .models import AutoMixRequest, Clip, CustomPresetRequest, DeleteRangeRequest, InstantiateProjectClipRequest, UpdateProjectClipRequest, MoveTrackRequest, MtaExportRequest, Project, ProjectClip, ProjectExportRequest, RightsRecord, Track, SampleEditRequest, SampleEffectRequest
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
    pdir,
    preserve_original,
    project_access,
    project_files,
    save_project,
    validate_project_files,
    write_project_archive,
    ROOT as STORAGE_ROOT,
)
from .rights_registry import (provider_catalog as rights_provider_catalog, search_provider as search_rights_provider, search_musicbrainz_metadata, resolve_musicbrainz_metadata)
from . import sample_editor as sample_editor_engine
from .version import APP_RELEASE, APP_REVISION, APP_VERSION, BUILD_ID, CREATOR, REPOSITORY

app = FastAPI(title="MTA Audio Editor", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)


def _musical_export_project(project: Project) -> Project:
    """Return a non-destructive export view with chords/key following project transposition."""
    export_project = project.model_copy(deep=True)
    export_project.chords = transpose_chords([ch for ch in project.chords if not ch.excluded], project.pitch_semitones)
    export_project.key = transpose_key_name(project.key, project.pitch_semitones)
    return export_project

@app.on_event("startup")
def _start_demucs_model_updater():
    start_background_updater()
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
    return model

def _lead_backing_catalog() -> dict:
    return {
        "default_model": LEAD_BACKING_DEFAULT_MODEL if any(x["id"] == LEAD_BACKING_DEFAULT_MODEL for x in LEAD_BACKING_MODELS) else "uvr_mdxnet_kara_2",
        "models": [_lead_backing_model_info(item["id"]) for item in LEAD_BACKING_MODELS],
        "storage": "local" if NATIVE_SINGLE_USER else "server",
        "on_demand": True,
    }

def _download_lead_backing_model(model_id: str) -> dict:
    info = _lead_backing_model_info(model_id)
    LEAD_BACKING_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from audio_separator.separator import Separator
    except ImportError as exc:
        raise RuntimeError("audio-separator is not installed") from exc
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



def _stem_job_update(job_id: str, **changes) -> None:
    with STEM_JOB_LOCK:
        job = STEM_JOBS.get(job_id)
        if job is not None:
            job.update(changes)
            job["updated_at"] = time.time()


def _stem_job_public(job: dict) -> dict:
    return {
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
    }


def _media_job_update(job_id: str, **changes) -> None:
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.get(job_id)
        if job is not None:
            job.update(changes)
            job["updated_at"] = time.time()


def _media_job_public(job: dict) -> dict:
    cancel_event=job.get("cancel_event")
    return {
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
    if not _is_public(request.url.path) and user is None and not model_bearer_ok and not check_basic_auth(request):
        if request.url.path.startswith("/api/"):
            return auth_failure_response()
        return RedirectResponse(url="/login", status_code=303)

    # API mutations must carry an explicit same-origin request marker.
    if request.url.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-mta-request") != "1":
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
    return f"{clean}-{project.id}.maeproj"


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
        "build": BUILD_ID,
        "creator": CREATOR,
        "repository": REPOSITORY,
        "license": "EUPL-1.2",
        "native_single_user": NATIVE_SINGLE_USER,
    }




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


@app.get("/api/projects")
def projects(request: Request):
    actor = _actor(request)
    # Legacy pre-multi-user projects are claimed once by the first persistent
    # administrator that opens the workspace after upgrade.
    if actor["id"] > 0 and actor["role"] == "admin":
        for legacy in list_projects():
            if legacy.owner_user_id is None:
                legacy.owner_user_id = actor["id"]
                save_project(legacy)
    # Even administrators get their own workspace here; cross-user administration
    # is exposed explicitly through the dump/admin APIs.
    return list_projects(actor["id"] if actor["id"] > 0 else None, include_shared=True, is_admin=False)


@app.post("/api/projects")
def project_new(request: Request, title: str = "Untitled", target: str = "MTA8"):
    actor = _actor(request)
    owner = actor["id"] if actor["id"] > 0 else None
    return create_project(title, target if target in {"MTA8", "MTA16", "DAW"} else "MTA8", owner_user_id=owner)


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


@app.get("/api/projects/{pid}")
def project_get(pid: str, request: Request):
    project = _project_for_actor(request, pid)
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
def project_put(pid: str, project: Project, request: Request):
    current = _project_for_actor(request, pid)
    if pid != project.id:
        raise HTTPException(400, "project id mismatch")
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
    duplicate = find_duplicate_project_file(pid, dst)
    if duplicate:
        dst.unlink(missing_ok=True)
        raise HTTPException(
            409,
            f"Il file è già presente nel progetto come {duplicate['category']}/{duplicate['name']}.",
        )
    preserve_original(pid, dst, Path(file.filename or filename).name)
    return filename, dst, media_duration_ms(dst)




def _waveform_revision(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"


def _track_waveform_revision(track: Track, source: Path) -> str:
    """Revision of the audible track output waveform, including insert state/config."""
    payload = {
        "source": _waveform_revision(source),
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
                peaks = waveform_peaks(rendered, 1024, progress)
        else:
            peaks = waveform_peaks(source, 1024, progress)
        latest = load_project(pid)
        latest_track = next((item for item in latest.tracks if item.id == track_id), None)
        if latest_track is None:
            raise ValueError("track removed while waveform was updating")
        latest_track.waveform_peaks = peaks
        latest_track.waveform_revision = _track_waveform_revision(latest_track, source)
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
    try:
        _media_job_update(job_id, status="running", progress=58, message="Validazione della traccia")
        ffprobe(dst)
        duration = media_duration_ms(dst)
        channels, channel_layout = _audio_channel_info(dst)
        project = load_project(pid)
        if estimate_first_bpm and not project.tracks:
            def bpm_progress(value: int, message: str) -> None:
                _media_job_update(job_id, progress=60 + int(max(0, min(100, value)) * 0.28), message=message)
            try:
                project.bpm = float(round(estimate_bpm(dst, bpm_progress)))
                project.base_bpm = project.bpm
                save_project(project)
            except Exception:
                _media_job_update(job_id, progress=87, message="Stima BPM non conclusiva; mantengo il BPM corrente")
        _media_job_update(job_id, progress=88, message="Generazione waveform")
        try:
            peaks = waveform_peaks(dst, 1024, lambda value, message: _media_job_update(
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
        )
        track.waveform_revision = _track_waveform_revision(track, dst) if peaks else ""
        _media_job_update(job_id, progress=91, message="Aggiunta della traccia al progetto")
        if sync_mode == "auto" and project.tracks:
            ref = next((item for item in project.tracks if item.id == reference_track_id), project.tracks[0])
            shift_track(track, auto_align_ms(audio_path(pid, ref.filename), dst))
        project.tracks.append(track)
        _register_track_source_in_library(project, track, provenance)
        save_project(project)
        _media_job_update(
            job_id,
            status="completed",
            progress=100,
            message="Import completato",
            result={"project_id": pid, "track_id": track.id, "bpm": project.bpm},
        )
    except Exception as exc:
        dst.unlink(missing_ok=True)
        _media_job_update(job_id, status="failed", progress=0, message="Import fallito", error=str(exc)[-1200:])


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
    project = _project_for_actor(request, pid)
    _ensure_workspace_capacity(project.owner_user_id, int(request.headers.get("content-length") or 0))
    ext = Path(file.filename or "track.wav").suffix.lower() or ".bin"
    if len(ext) > 12 or not ext.replace(".", "").isalnum():
        raise HTTPException(400, "invalid file extension")
    filename = f"{uuid.uuid4().hex[:10]}{ext}"
    dst = audio_path(pid, filename)
    _copy_limited(file.file, dst)
    duplicate = find_duplicate_project_file(pid, dst)
    if duplicate:
        dst.unlink(missing_ok=True)
        raise HTTPException(
            409,
            f"Il file è già presente nel progetto come {duplicate['category']}/{duplicate['name']}.",
        )
    preserve_original(pid, dst, Path(file.filename or filename).name)
    now = time.time()
    job_id = uuid.uuid4().hex[:16]
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
    threading.Thread(
        target=_track_import_worker,
        args=(job_id, pid, filename, Path(file.filename or filename).name, name, type, offset_ms, sync_mode, reference_track_id, first_track),
        daemon=True,
        name=f"track-import-{job_id}",
    ).start()
    return _media_job_public(job)



def _text_music_worker(job_id: str, pid: str, track_id: str, kind: str, model_or_engine: str = "", advanced_alignment: bool = False) -> None:
    try:
        project = load_project(pid)
        track = next((item for item in project.tracks if item.id == track_id), None)
        if track is None:
            raise ValueError("track not found")
        source = audio_path(pid, track.filename)
        _media_job_update(job_id, status="running", progress=3, message="Preparazione analisi e verifica sorgente")
        if kind == "lyrics":
            selected_model=model_or_engine or lyrics_catalog(native=NATIVE_SINGLE_USER)["default_model"]
            _media_job_update(job_id, progress=5, message=f"Verifica modello lyrics · OpenAI Whisper · {selected_model}")
            cancel_event=MEDIA_JOBS[job_id].get("cancel_event")
            def lyrics_progress(pct, items, message):
                # Do not expose incremental transcript text while Whisper is running:
                # it may encourage chunk stitching artefacts (repeated/missing phrases).
                _media_job_update(job_id,progress=pct,message=message,partial={"kind":"lyrics","items":[]})
            if getattr(extract_lyrics,"__module__","") != "app.music_text":
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
            mapped = map_source_events_to_timeline(track, events)
            latest = load_project(pid)
            latest.lyrics = mapped
            latest.lyrics_engine = "OpenAI Whisper"
            latest.lyrics_model = selected_model
            _media_job_update(job_id, progress=98, message="Salvataggio lyrics nel progetto")
            save_project(latest)
            _media_job_update(
                job_id, status="completed", progress=100, message="Lyrics estratte e sincronizzate",
                result={"kind": "lyrics", "count": len(mapped), "engine": "OpenAI Whisper", "model": selected_model, "advanced_alignment": advanced_alignment},
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
            if getattr(extract_chords,"__module__","") != "app.music_text":
                try: events=extract_chords(source,engine=selected_engine)
                except TypeError: events=extract_chords(source)
                chords_progress(90,events,"Analisi chords")
            else:
                events=extract_chords_progressive(
                    source,engine=selected_engine,progress=chords_progress,
                    cancelled=(lambda: bool(cancel_event and cancel_event.is_set())),
                )
            if cancel_event and cancel_event.is_set():
                raise InterruptedError("Chord extraction cancelled")
            _media_job_update(job_id, progress=96, message="Sincronizzazione chords sulla timeline")
            mapped = map_source_events_to_timeline(track, events)
            latest = load_project(pid)
            latest.chords = mapped
            latest.chords_engine = selected_engine
            latest.chords_model = selected_model
            _media_job_update(job_id, progress=98, message="Salvataggio chords nel progetto")
            save_project(latest)
            _media_job_update(
                job_id, status="completed", progress=100, message="Chords estratti e sincronizzati",
                result={"kind": "chords", "count": len(mapped), "engine": selected_engine, "model": selected_model, "engine_display_name": engine_info["display_name"]},
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
            latest=load_project(pid)
            latest.markers=mapped
            save_project(latest)
            _media_job_update(job_id,status="completed",progress=100,message="Marker/sezioni estratti e sincronizzati",result={"kind":"markers","count":len(mapped),"engine":"MTA structural analysis"})
            return
        raise ValueError("unsupported analysis kind")
    except InterruptedError as exc:
        _media_job_update(job_id,status="cancelled",message="Estrazione annullata",error=str(exc),result=None)
    except Exception as exc:
        LOGGER.exception("Text/music analysis job %s failed", job_id)
        _media_job_update(job_id, status="failed", progress=0, message="Analisi fallita", error=str(exc)[-1200:])


def _start_text_music_job(pid: str, track_id: str, request: Request, kind: str, model_or_engine: str = "", advanced_alignment: bool = False):
    project = _project_for_actor(request, pid)
    if not any(item.id == track_id for item in project.tracks):
        raise HTTPException(404, "track not found")
    if kind == "lyrics":
        if not lyrics_engine_available():
            raise HTTPException(409, "Motore lyrics Whisper non disponibile in questo runtime")
        allowed={x["id"] for x in lyrics_catalog(native=NATIVE_SINGLE_USER)["models"]}
        if model_or_engine and model_or_engine not in allowed:
            raise HTTPException(400, "Modello lyrics non supportato")
    if kind == "chords":
        selected=model_or_engine or chords_catalog(native=NATIVE_SINGLE_USER)["default_engine"]
        engines={x["id"]:x for x in chords_catalog(native=NATIVE_SINGLE_USER)["engines"]}
        if selected not in engines:
            raise HTTPException(400, "Motore chords non supportato")
        if not chord_engine_available(selected):
            raise HTTPException(409, f"Motore chords {engines[selected]['display_name']} non disponibile in questo runtime")
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
    threading.Thread(
        target=_text_music_worker, args=(job_id, pid, track_id, kind, model_or_engine, advanced_alignment),
        daemon=True, name=f"mta-{kind}-{job_id}",
    ).start()
    return _media_job_public(job)


@app.post("/api/projects/{pid}/tracks/{track_id}/extract-lyrics-jobs")
def start_lyrics_extraction(pid: str, track_id: str, request: Request, model: str = "", advanced_alignment: bool = False):
    return _start_text_music_job(pid, track_id, request, "lyrics", model, advanced_alignment)


@app.post("/api/projects/{pid}/tracks/{track_id}/extract-chords-jobs")
def start_chord_extraction(pid: str, track_id: str, request: Request, engine: str = ""):
    return _start_text_music_job(pid, track_id, request, "chords", engine)


@app.post("/api/projects/{pid}/tracks/{track_id}/extract-markers-jobs")
def start_marker_extraction(pid: str, track_id: str, request: Request):
    return _start_text_music_job(pid, track_id, request, "markers")


@app.post("/api/projects/{pid}/lyrics/reset")
def reset_project_lyrics(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    project.lyrics = []
    project.lyrics_engine = ""
    project.lyrics_model = ""
    save_project(project)
    return {"ok": True, "lyrics": [], "lyrics_engine": "", "lyrics_model": ""}


@app.post("/api/projects/{pid}/chords/reset")
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


@app.get("/api/projects/{pid}/lyrics.pdf")
def download_project_lyrics_pdf(pid: str, request: Request, chord_color: str = "#7B1FA2", preview: bool = False):
    project = _project_for_actor(request, pid)
    if not project.lyrics:
        raise HTTPException(409, "Il progetto non contiene lyrics")
    tmp = Path(tempfile.mkstemp(prefix=f"mta-lyrics-{pid}-", suffix=".pdf")[1])
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", chord_color):
        raise HTTPException(400, "Colore accordi non valido")
    build_lyrics_pdf(
        tmp, title=project.title, artist=project.artist,
        lyrics=project.lyrics, chords=transpose_chords(project.chords, project.pitch_semitones), chord_color=chord_color,
        key=transpose_key_name(project.key, project.pitch_semitones), bpm=project.bpm,
        rights_records=project.rights_records, markers=project.markers,
        pdf_style=project.lyrics_pdf_style.model_dump(),
    )
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


@app.post("/api/projects/{pid}/metadata-search")
def api_project_metadata_search(pid: str, request: Request, body: dict):
    project = _project_for_actor(request, pid)
    title = str(body.get("title") or project.title or "").strip()
    artist = str(body.get("artist") or project.artist or "").strip()
    if not title:
        raise HTTPException(400, "Inserisci il titolo del brano")
    try:
        results = search_musicbrainz_metadata(title=title, artist=artist, limit=15)
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


@app.get("/api/media-jobs/{job_id}")
def media_job_status(job_id: str, request: Request):
    with MEDIA_JOB_LOCK:
        job = MEDIA_JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "Job non trovato")
        snapshot = dict(job)
    if snapshot.get("project_id"):
        _project_for_actor(request, snapshot["project_id"])
    else:
        _actor(request)
    return _media_job_public(snapshot)


@app.post("/api/media-jobs/{job_id}/cancel")
def cancel_media_job(job_id: str, request: Request):
    with MEDIA_JOB_LOCK:
        job=MEDIA_JOBS.get(job_id)
        if job is None:
            raise HTTPException(404,"Job non trovato")
        snapshot=dict(job)
        event=job.get("cancel_event")
        if event is None:
            raise HTTPException(409,"Questo job non supporta l'annullamento")
        event.set()
        if job.get("status") in {"queued","running"}:
            job["message"]="Annullamento richiesto…"
            job["updated_at"]=time.time()
    if snapshot.get("project_id"):
        _project_for_actor(request,snapshot["project_id"])
    else:
        _actor(request)
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
    project = _project_for_actor(request, pid)
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
    _register_track_source_in_library(project, track, f"Import file: {Path(file.filename or filename).name}")
    save_project(project)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/replace")
async def replace_track(
    pid: str,
    track_id: str,
    request: Request,
    file: UploadFile = File(...),
    sync_mode: str = "keep",
    offset_ms: int = 0,
    reference_track_id: str = "",
):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    ensure_clips(track)
    previous_offset = track.clips[0].timeline_start_ms if track.clips else 0
    old = audio_path(pid, track.filename)
    filename, dst, duration = _save_upload(pid, file)

    track.filename = filename
    track.duration_ms = duration
    track.channels, track.channel_layout = _audio_channel_info(dst)
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
        dst.unlink(missing_ok=True)
        raise
    except Exception as exc:
        dst.unlink(missing_ok=True)
        raise HTTPException(400, "automatic sync failed") from exc

    _register_track_source_in_library(project, track)
    save_project(project)
    library_files = {item.filename for item in project.clip_library}
    if old.exists() and old.name != filename and old.name not in library_files:
        old.unlink(missing_ok=True)
    return project



@app.patch("/api/projects/{pid}/clip-library/{clip_id}")
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
def instantiate_project_clip(pid: str, clip_id: str, req: InstantiateProjectClipRequest, request: Request):
    project = _project_for_actor(request, pid)
    _ensure_project_clip_library(project)
    asset = next((item for item in project.clip_library if item.id == clip_id), None)
    if asset is None:
        raise HTTPException(404, "clip di libreria non trovata")
    source = audio_path(pid, asset.filename)
    if not source.is_file():
        raise HTTPException(404, "file audio della clip non trovato")
    track = Track(
        id=uuid.uuid4().hex[:10],
        name=asset.name[:200],
        type=asset.type,
        filename=asset.filename,
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
    )
    try:
        track.waveform_peaks = waveform_peaks(source, 1024)
        track.waveform_revision = _track_waveform_revision(track, source)
    except Exception:
        track.waveform_peaks = []
        track.waveform_revision = ""
    project.tracks.append(track)
    save_project(project)
    return {"project": project, "track": track, "clip": asset}


@app.post("/api/projects/{pid}/delete-tracks")
def delete_tracks(pid: str, request: Request, track_ids: list[str]):
    project = _project_for_actor(request, pid)
    _ensure_project_clip_library(project)
    wanted = {str(track_id) for track_id in track_ids}
    if not wanted:
        raise HTTPException(400, "no tracks selected")
    known = {track.id for track in project.tracks}
    if not wanted <= known:
        raise HTTPException(400, "unknown track id")
    removed = [track for track in project.tracks if track.id in wanted]
    project.tracks = [track for track in project.tracks if track.id not in wanted]
    save_project(project)
    # Remove only working audio no longer referenced by any remaining track.
    still_referenced = {track.filename for track in project.tracks} | {item.filename for item in project.clip_library}
    for track in removed:
        if track.filename not in still_referenced:
            audio_path(pid, track.filename).unlink(missing_ok=True)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/move")
def move_track(pid: str, track_id: str, req: MoveTrackRequest, request: Request):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if not track:
        raise HTTPException(404, "track not found")
    shift_track(track, req.offset_ms)
    save_project(project)
    return project


@app.post("/api/projects/{pid}/tracks/{track_id}/autosync")
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
def project_auto_mix(pid: str, req: AutoMixRequest, request: Request):
    project = _project_for_actor(request, pid)
    if req.enabled:
        enable_auto_mix(project, req.style)
    else:
        disable_auto_mix(project)
    save_project(project)
    return project


@app.post("/api/projects/{pid}/delete-range")
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
        return import_mta(src, project)
    except Exception as exc:
        delete_project(project.id)
        raise HTTPException(400, "MTA import failed") from exc


def _download_name(title: str, ext: str) -> str:
    clean = SAFE_DOWNLOAD_RE.sub("_", title).strip(" ._")[:120] or "project"
    return f"{clean}.{ext}"


def _split_lead_backing_vocals(vocal_stem: Path, output_dir: Path, *, model_id: str | None = None, cancel_event=None) -> tuple[Path, Path, str]:
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
    separator = Separator(model_file_dir=str(LEAD_BACKING_MODEL_DIR), output_dir=str(output_dir), output_format="WAV")
    separator.load_model(model_filename=info["filename"])
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError("stem separation cancelled")
    outputs = [Path(item) for item in separator.separate(str(vocal_stem))]
    vocal_output = next((x for x in outputs if "vocal" in x.name.lower() and "back" not in x.name.lower()), None)
    backing_output = next((x for x in outputs if any(k in x.name.lower() for k in ("instrumental", "karaoke", "backing"))), None)
    if vocal_output is None or backing_output is None:
        raise RuntimeError(f"AI separator did not return lead/backing-compatible stems: {[x.name for x in outputs]}")
    shutil.move(str(vocal_output), lead)
    shutil.move(str(backing_output), backing)
    return lead, backing, f"audio-separator:{selected}"


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
        backing_vocal_model = str(job.get("backing_vocal_model") or LEAD_BACKING_DEFAULT_MODEL)
        stem_count = int(job.get("stem_count") or 0)

    def progress(value: int, message: str) -> None:
        _stem_job_update(job_id, progress=max(1, min(99, int(value))), message=message)

    added_track_ids: list[str] = []
    added_files: list[Path] = []
    try:
        _stem_job_update(job_id, status="running", progress=12, message="Analisi del brano completo")
        ffprobe(source)
        if estimate_project_bpm:
            def bpm_progress(value: int, message: str) -> None:
                progress(12 + int(max(0, min(100, value)) * 0.12), message)
            try:
                project_for_bpm = load_project(project_id)
                project_for_bpm.bpm = float(round(estimate_bpm(source, bpm_progress)))
                project_for_bpm.base_bpm = project_for_bpm.bpm
                save_project(project_for_bpm)
            except Exception:
                progress(24, "Stima BPM non conclusiva; continuo con il BPM corrente")
        if cancel_event.is_set():
            raise RuntimeError("stem separation cancelled")
        with tempfile.TemporaryDirectory(prefix=f"mta-stems-{job_id}-") as td_raw:
            td = Path(td_raw)
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
            if split_backing_vocals:
                vocal_stem = next((Path(stem) for stem in stems if Path(stem).stem.lower() in {"vocals", "vocal"}), None)
                if vocal_stem is None:
                    raise RuntimeError("Il modello selezionato non ha prodotto uno stem vocals da separare")
                progress(86, "Separazione voce principale e backing vocals")
                lead_vocal, backing_vocal, vocal_split_method = _split_lead_backing_vocals(
                    vocal_stem, td / "lead-backing", model_id=backing_vocal_model, cancel_event=cancel_event
                )
                stems = [stem for stem in stems if Path(stem) != vocal_stem] + [lead_vocal, backing_vocal]
                _stem_job_update(job_id, vocal_split_method=vocal_split_method)
            progress(90, "Importazione delle tracce nel progetto")
            project = load_project(project_id)
            mapping = {
                "drums": "drums",
                "bass": "bass",
                "guitar": "guitars",
                "piano": "keyboards",
                "vocals": "melody",
                "lead_vocals": "melody",
                "backing_vocals": "melody",
                "other": "other",
            }
            for index, stem in enumerate(stems, start=1):
                if cancel_event.is_set():
                    raise RuntimeError("stem separation cancelled")
                stem_name = stem.stem.lower()
                kind = mapping.get(stem_name, "other")
                filename = f"{uuid.uuid4().hex[:10]}.wav"
                dst = audio_path(project.id, filename)
                shutil.copyfile(stem, dst)
                duration = media_duration_ms(dst)
                channels, channel_layout = _audio_channel_info(dst)
                display_name = {"lead_vocals": "Lead Vocals", "backing_vocals": "Backing Vocals"}.get(stem_name, stem.stem.title())
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
                        clips=[
                            Clip(
                                id=uuid.uuid4().hex[:10],
                                source_start_ms=0,
                                source_end_ms=duration,
                                timeline_start_ms=0,
                            )
                        ],
                    )
                project.tracks.append(new_track)
                added_track_ids.append(new_track.id)
                added_files.append(dst)
                save_project(project)
                progress(90 + int(index / max(1, len(stems)) * 8), f"Importata traccia {stem.stem.title()}")

            # Optional musical-text analysis is intentionally non-fatal: a successful
            # stem separation must remain usable even if Whisper/Chordino is unavailable.
            analysis: dict[str, dict[str, object]] = {}
            if extract_lyrics_after:
                progress(98, "Estrazione lyrics ad alta accuratezza")
                vocal_stem = next((Path(stem) for stem in stems if Path(stem).stem.lower() in {"vocals", "vocal"}), None)
                lyric_source = vocal_stem or source
                try:
                    project = load_project(project_id)
                    selected_lyrics_model=str(job.get("lyrics_model") or lyrics_catalog(native=NATIVE_SINGLE_USER)["default_model"])
                    # Legacy equivalent: project.lyrics = extract_lyrics(lyric_source)
                    project.lyrics = extract_lyrics(lyric_source, model_name=selected_lyrics_model)
                    project.lyrics_engine="OpenAI Whisper"; project.lyrics_model=selected_lyrics_model
                    save_project(project)
                    analysis["lyrics"] = {"ok": True, "count": len(project.lyrics), "source": "vocals" if vocal_stem else "mix", "engine":"OpenAI Whisper", "model":selected_lyrics_model}
                except Exception as analysis_exc:
                    LOGGER.exception("Lyrics extraction after stem separation failed")
                    analysis["lyrics"] = {"ok": False, "error": str(analysis_exc)[-500:]}
                _stem_job_update(job_id, analysis=dict(analysis))
            if extract_chords_after:
                progress(99, "Analisi chords ad alta accuratezza")
                try:
                    project = load_project(project_id)
                    selected_chords_engine=str(job.get("chords_engine") or chords_catalog(native=NATIVE_SINGLE_USER)["default_engine"])
                    chord_info=next((x for x in chords_catalog(native=NATIVE_SINGLE_USER)["engines"] if x["id"]==selected_chords_engine),{})
                    # Legacy equivalent: project.chords = extract_chords(source)
                    project.chords = extract_chords(source, engine=selected_chords_engine)
                    project.chords_engine=selected_chords_engine; project.chords_model=str(chord_info.get("model_id") or "")
                    save_project(project)
                    analysis["chords"] = {"ok": True, "count": len(project.chords), "source": "mix", "engine":selected_chords_engine, "model":project.chords_model, "engine_display_name":chord_info.get("display_name",selected_chords_engine)}
                except Exception as analysis_exc:
                    LOGGER.exception("Chord extraction after stem separation failed")
                    analysis["chords"] = {"ok": False, "error": str(analysis_exc)[-500:]}
                _stem_job_update(job_id, analysis=dict(analysis))
        if not keep_original_track:
            source.unlink(missing_ok=True)
        _stem_job_update(job_id, status="completed", progress=100, message="Separazione completata")
    except Exception as exc:
        if cancel_event.is_set() or "cancelled" in str(exc).lower():
            try:
                project = load_project(project_id)
                project.tracks = [track for track in project.tracks if track.id not in set(added_track_ids)]
                save_project(project)
                for path in added_files:
                    path.unlink(missing_ok=True)
            except Exception as cleanup_exc:
                LOGGER.warning(
                    "Unable to fully roll back partial stem files for job %s: %s",
                    job_id,
                    cleanup_exc,
                )
            _stem_job_update(job_id, status="cancelled", progress=0, message="Separazione annullata", error=None)
        else:
            if not keep_original_track:
                source.unlink(missing_ok=True)
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


def _start_ai_model_download_job(kind: str, model_id: str, request: Request):
    _actor(request)
    now=time.time();job_id=uuid.uuid4().hex[:16]
    job={"id":job_id,"kind":f"download-{kind}-model","project_id":None,"status":"queued","progress":3,"message":"Download modello in coda","created_at":now,"updated_at":now,"result":None,"error":None}
    with MEDIA_JOB_LOCK: MEDIA_JOBS[job_id]=job
    threading.Thread(target=_ai_model_download_worker,args=(job_id,kind,model_id),daemon=True,name=f"model-download-{job_id}").start()
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


@app.get("/api/vocal-separation/models")
def lead_backing_models(request: Request):
    _actor(request)
    return _lead_backing_catalog()

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
):
    if Path(file.filename or "").suffix.lower() != ".mp3":
        raise HTTPException(400, "La separazione strumenti accetta attualmente file MP3.")
    if not STEM_SPLITTER.available():
        raise HTTPException(503, "Il plugin Demucs non è installato in questo runtime.")
    status = STEM_SPLITTER.status()
    supported_counts = [int(value) for value in status.get("supported_stem_counts", [])]
    if stem_count != 0 and (stem_count < 2 or stem_count > 64):
        raise HTTPException(400, "Numero di stem non valido. Usa Auto oppure una cardinalità tra 2 e 64.")
    if stem_count and stem_count not in supported_counts:
        raise HTTPException(400, f"Nessun modello configurato fornisce {stem_count} stem.")
    if stem_count == 2:
        model = "htdemucs" if model not in {"htdemucs", "htdemucs_ft"} else model
    elif stem_count:
        profiles = [item for item in status.get("model_profiles", []) if int(item.get("stem_count", 0)) == stem_count]
        if profiles and (model not in status["models"] or next((int(item.get("stem_count", 0)) for item in status.get("model_profiles", []) if item.get("model") == model), -1) != stem_count):
            model = str(profiles[0]["model"])
    if model not in status["models"]:
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
        "backing_vocal_model": backing_vocal_model,
        "vocal_split_method": None,
        "analysis": {},
    }
    with STEM_JOB_LOCK:
        STEM_JOBS[job_id] = job
    thread = threading.Thread(
        target=_stem_split_worker,
        args=(job_id, source, keep_original_track),
        daemon=True,
        name=f"stem-job-{job_id}",
    )
    thread.start()
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
        current_job["cancel_event"].set()
        current_job["status"] = "cancelling"
        current_job["message"] = "Annullamento in corso…"
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
            duration = media_duration_ms(dst)
            project.tracks.append(Track(
                id=uuid.uuid4().hex[:10],
                name=stem.stem.title(),
                type=mapping.get(stem.stem.lower(), "other"),
                filename=filename,
                duration_ms=duration,
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
    threading.Thread(
        target=_stem_split_worker,
        args=(job_id, source, True),
        daemon=True,
        name=f"track-stem-{job_id}",
    ).start()
    return _stem_job_public(job)



@app.post("/api/projects/{pid}/metronome-track")
def create_metronome_track(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    duration_ms = project_duration_ms(project)
    if duration_ms <= 0:
        raise HTTPException(400, "Il progetto non ha ancora una durata. Importa almeno una traccia audio prima di creare il metronomo.")

    filename = f"metronome-{uuid.uuid4().hex[:10]}.wav"
    out = audio_path(pid, filename)
    try:
        duration_ms = generate_metronome_wav(project, out)
        peaks = waveform_peaks(out)
    except Exception as exc:
        out.unlink(missing_ok=True)
        raise HTTPException(400, f"Creazione metronomo fallita: {str(exc)[:300]}") from exc

    track = Track(
        id=uuid.uuid4().hex[:10],
        name=f"Metronomo {project.bpm:g} BPM",
        type="other",
        filename=filename,
        duration_ms=duration_ms,
        channels=1,
        channel_layout="mono",
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
    track.waveform_revision = _track_waveform_revision(track, out) if peaks else ""
    project.tracks.append(track)
    save_project(project)
    return {"project": project, "track": track}


@app.post("/api/projects/{pid}/tracks/{track_id}/estimate-bpm")
def estimate_track_bpm(pid: str, track_id: str, request: Request):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if track is None:
        raise HTTPException(404, "track not found")
    try:
        bpm = float(round(estimate_bpm(audio_path(pid, track.filename))))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(422, f"Impossibile stimare i BPM: {exc}") from exc
    project.bpm = bpm
    project.base_bpm = bpm
    save_project(project)
    return {"ok": True, "track_id": track_id, "bpm": bpm}


@app.get("/api/projects/{pid}/preview-track/{track_id}")
def preview_track(pid: str, track_id: str, request: Request, render: bool = False):
    project = _project_for_actor(request, pid)
    track = next((item for item in project.tracks if item.id == track_id), None)
    if track is None:
        raise HTTPException(404, "track not found")
    signature = hashlib.sha256(
        (
            track.model_dump_json()
            + f"|{project.bpm}|{project.base_bpm}|{project.pitch_semitones}|{int(render)}"
        ).encode("utf-8")
    ).hexdigest()[:20]
    cache = pdir(pid) / ".preview"
    cache.mkdir(exist_ok=True)
    out = cache / f"{track.id}-{signature}.wav"
    if not out.is_file():
        render_track_export(
            track,
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
    out = pdir(pid) / "preview-master.mp3"
    try:
        validate_project_files(project)
        preview_project = project.model_copy(deep=True)
        # Master inserts are rendered server-side, while the master fader is kept
        # neutral here so the browser can apply master volume live during playback.
        preview_project.master_volume_db = 0.0
        render_mix(preview_project, audio_path, out, fmt="mp3", bitrate="192k")
    except Exception as exc:
        raise HTTPException(400, "preview mix failed") from exc
    return FileResponse(out, media_type="audio/mpeg", filename="preview-master.mp3")


@app.get("/api/projects/{pid}/export-plan")
def export_plan(pid: str, request: Request, profile: str | None = None, target: str | None = None):
    source_project = _project_for_actor(request, pid)
    project = source_project.model_copy(deep=True)
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
        slots = validate_slot_mapping(export_project, req.slots)
        ext = "mta8" if export_project.target == "MTA8" else "mta16"
        out = pdir(pid) / f"export.{ext}"
        export_mta(export_project, out, slots)
    except Exception as exc:
        raise HTTPException(400, str(exc)[:500]) from exc
    return FileResponse(out, filename=_download_name(project.title, ext), media_type="application/octet-stream")



def _track_export_worker(job_id: str, pid: str, track_id: str, fmt: str) -> None:
    try:
        project = load_project(pid)
        track = next((item for item in project.tracks if item.id == track_id), None)
        if track is None:
            raise ValueError("track not found")
        _media_job_update(job_id, status="running", progress=20, message="Rendering della traccia")
        out = pdir(pid) / f"track-{track.id}.{fmt}"
        render_track_export(track, audio_path(pid, track.filename), out, fmt=fmt, project=project)
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
def start_track_export_job(pid: str, track_id: str, request: Request, format: str = "wav"):
    project = _project_for_actor(request, pid)
    if not any(item.id == track_id for item in project.tracks):
        raise HTTPException(404, "track not found")
    fmt = format.lower()
    if fmt not in {"wav", "mp3", "flac"}:
        raise HTTPException(400, "unsupported track export format")
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
    threading.Thread(target=_track_export_worker, args=(job_id, pid, track_id, fmt), daemon=True).start()
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
    project = load_project(pid)
    fmt = req.format.lower()
    validate_project_files(project)
    safe_stem = SAFE_DOWNLOAD_RE.sub("_", Path(req.filename).stem).strip(" ._")[:180] or "project"
    if fmt == "mta":
        export_project = _musical_export_project(project)
        if export_project.target == "DAW":
            export_project.target = req.mta_target or "MTA16"
        ext = "mta8" if export_project.target == "MTA8" else "mta16"
        out = pdir(pid) / f"configured-export.{ext}"
        limit = 8 if export_project.target == "MTA8" else 16
        if len(export_project.tracks) > limit or req.slots:
            slots = validate_slot_mapping(export_project, req.slots, req.mta_device_profile)
            export_mta(export_project, out, slots, req.mta_device_profile)
        else:
            export_mta(export_project, out, profile=req.mta_device_profile)
        media_type = "application/octet-stream"
    elif fmt in {"wav", "mp3", "flac"}:
        ext = fmt
        out = pdir(pid) / f"configured-export.{ext}"
        render_mix(
            project,
            audio_path,
            out,
            fmt=fmt,
            bitrate=f"{int(req.mp3_bitrate_kbps)}k",
            sample_rate=int(req.sample_rate),
            wav_bit_depth=int(req.wav_bit_depth),
            flac_compression=int(req.flac_compression),
        )
        media_type = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac"}[fmt]
    elif fmt == "mp4":
        if not project.lyrics:
            raise ValueError("MP4 karaoke export requires synchronized lyrics")
        ext = "mp4"
        out = pdir(pid) / "configured-export.mp4"
        _render_karaoke_video(pid, project, out, req)
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
            shutil.copy2(out, destination)
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
        if format == "mta":
            if project.target == "DAW":
                raise HTTPException(409, "DAW projects require choosing MTA8 or MTA16 in configured export")
            if len(project.tracks) > (8 if project.target == "MTA8" else 16):
                raise HTTPException(409, "MTA export mapping required; use /export-plan and /export-mta")
            ext = "mta8" if project.target == "MTA8" else "mta16"
            out = pdir(pid) / f"export.{ext}"
            export_mta(_musical_export_project(project), out)
            media_type = "application/octet-stream"
        elif format in {"wav", "mp3", "flac"}:
            ext = format
            out = pdir(pid) / f"export.{ext}"
            render_mix(project, audio_path, out, fmt=ext, bitrate="320k")
            media_type = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac"}[ext]
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
