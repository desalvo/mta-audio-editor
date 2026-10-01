import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles

from .audio_engine import auto_align_ms, delete_range, delete_song_range, ensure_clips, media_duration_ms, render_mix, render_track_export, shift_track
from .codec import export_mta, ffprobe, import_mta, suggested_slots, validate_slot_mapping
from .models import AutoMixRequest, Clip, CustomPresetRequest, DeleteRangeRequest, MoveTrackRequest, MtaExportRequest, Project, Track
from .plugins import STEM_SPLITTER, delete_user_preset, plugin_manifest, save_user_preset
from .security import auth_failure_response, check_basic_auth
from .auth import (
    authenticate, begin_totp, confirm_email, create_session, delete_session, disable_totp,
    enable_totp, find_user, get_smtp_config, get_user, list_users, public_user,
    register_user, require_admin, require_user, resend_verification, save_smtp_config,
    session_user, test_smtp_config, totp_qr_svg, totp_uri, update_profile,
    update_user_admin, delete_user_admin, change_password, request_password_reset, reset_password,
)
from .auto_mix import disable_auto_mix, enable_auto_mix
from .mta_reverse import analyze_mta, diff_blobs
from .storage import (
    audio_path,
    create_project,
    delete_project,
    delete_project_file,
    file_path,
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
)
from .version import APP_VERSION, BUILD_ID, CREATOR, REPOSITORY

app = FastAPI(title="MTA Audio Editor", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)
BASE = Path(__file__).parent
MAX_UPLOAD_BYTES = int(os.getenv("MTA_MAX_UPLOAD_MB", "150")) * 1024 * 1024
SAFE_DOWNLOAD_RE = re.compile(r"[^A-Za-z0-9._ -]+")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


def _is_public(path: str) -> bool:
    return (
        path.startswith("/static/")
        or path in {"/api/health", "/api/about", "/login", "/register", "/verify-email", "/resend-verification", "/forgot-password", "/reset-password"}
        or path.startswith("/docs/user")
        or path.startswith("/docs/pdf/user")
    )


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    user = session_user(request)
    if not _is_public(request.url.path) and user is None and not check_basic_auth(request):
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
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; media-src 'self' blob:; connect-src 'self'"
    )
    response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api/") else "no-cache"
    return response


def _template(name: str, **replacements) -> str:
    text = (BASE / "templates" / name).read_text(encoding="utf-8")
    text = text.replace("__VERSION__", APP_VERSION).replace("__BUILD__", BUILD_ID)
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
    return f"{clean}-{project.id}.mta-project.zip"


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if session_user(request):
        return RedirectResponse("/", status_code=303)
    return _template("login.html", error="")


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request):
    form = await request.form()
    identifier = str(form.get("identifier", "")).strip()
    password = str(form.get("password", ""))
    totp = str(form.get("totp", "")).strip()
    user, error = authenticate(identifier, password, totp)
    if not user:
        return HTMLResponse(_template("login.html", error=_alert(error)), status_code=401)
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
    return _template("register.html", error="")


@app.post("/register", response_class=HTMLResponse)
async def register_submit(request: Request):
    form = await request.form()
    if str(form.get("password", "")) != str(form.get("password2", "")):
        return HTMLResponse(_template("register.html", error=_alert("Le password non coincidono.")), status_code=400)
    try:
        user, token = register_user(
            str(form.get("username", "")),
            str(form.get("email", "")),
            str(form.get("display_name", "")),
            str(form.get("password", "")),
            base_url=str(request.base_url).rstrip("/"),
        )
    except ValueError as exc:
        return HTMLResponse(_template("register.html", error=_alert(str(exc))), status_code=400)
    extra = ""
    if os.getenv("MTA_DEV_EXPOSE_EMAIL_TOKENS", "").lower() in {"1","true","yes","on"}:
        extra = f'<p class="alert ok">DEV verification token: <code>{token}</code></p>'
    return HTMLResponse(_template(
        "message.html",
        title="Conferma la tua email",
        message=f"Abbiamo inviato un link di conferma a {user['email']}. Dopo la conferma, il tuo account resterà in attesa dell'approvazione di un amministratore.",
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
    require_user(request)
    return _template("account.html")


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    require_admin(request)
    return _template("admin.html")


@app.get("/api/session")
def api_session(request: Request):
    return public_user(require_user(request))


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


@app.get("/api/admin/users")
def api_admin_users(request: Request):
    require_admin(request)
    return list_users()


@app.patch("/api/admin/users/{user_id}")
def api_admin_user_update(user_id: int, request: Request, body: dict):
    actor = require_admin(request)
    try:
        return update_user_admin(user_id, actor["id"], active=body.get("active"), role=body.get("role"))
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
            filename=f"mta-audio-editor-all-projects-{APP_VERSION}.zip",
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
def admin_docs(request: Request):
    user = session_user(request)
    if user is not None and user["role"] != "admin":
        raise HTTPException(403, "Ruolo amministratore richiesto.")
    return _render_doc("admin.html")


@app.get("/docs/pdf/user")
def user_pdf():
    return FileResponse(BASE / "docs" / "MTA-Audio-Editor-User-Manual.pdf", filename="MTA-Audio-Editor-User-Manual.pdf")


@app.get("/docs/pdf/admin")
def admin_pdf(request: Request):
    user = session_user(request)
    if user is not None and user["role"] != "admin":
        raise HTTPException(403, "Ruolo amministratore richiesto.")
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
    manifest = plugin_manifest()
    return {
        "inserts": manifest["presets"],
        "schemas": manifest["schemas"],
        "custom": manifest["custom"],
        "notes": manifest["notes"],
        "stem_splitter": STEM_SPLITTER.status(),
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
    return create_project(title, target if target in {"MTA8", "MTA16"} else "MTA8", owner_user_id=owner)


@app.get("/api/projects/{pid}")
def project_get(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    for track in project.tracks:
        ensure_clips(track)
    return project


@app.put("/api/projects/{pid}")
def project_put(pid: str, project: Project, request: Request):
    current = _project_for_actor(request, pid)
    if pid != project.id:
        raise HTTPException(400, "project id mismatch")
    # Ownership/shares are managed only through dedicated endpoints.
    project.owner_user_id = current.owner_user_id
    project.shared_with_user_ids = current.shared_with_user_ids
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
    _project_for_actor(request, pid)
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "upload.bin"
        _copy_limited(file.file, src)
        dst = preserve_original(pid, src, Path(file.filename or "upload.bin").name)
    return {"ok": True, "category": "original", "name": dst.name, "size": dst.stat().st_size}


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


@app.get("/api/projects/{pid}/archive")
def project_archive_export(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    tmp = Path(tempfile.mkstemp(prefix=f"mta-project-{pid}-", suffix=".zip")[1])
    try:
        write_project_archive(pid, tmp)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return FileResponse(
        tmp,
        media_type="application/zip",
        filename=_project_archive_name(project),
        background=BackgroundTask(lambda: tmp.unlink(missing_ok=True)),
    )


@app.post("/api/project-archives/import")
async def project_archive_import(request: Request, file: UploadFile = File(...)):
    actor = _actor(request)
    if actor["id"] <= 0:
        raise HTTPException(400, "L'import completo richiede un account utente persistente.")
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "project.zip"
        _copy_limited(file.file, src)
        try:
            return import_project_archive(src, actor["id"])
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
    original = None
    try:
        original = preserve_original(pid, dst, Path(file.filename or filename).name)
        ffprobe(dst)
    except Exception as exc:
        dst.unlink(missing_ok=True)
        if original is not None:
            original.unlink(missing_ok=True)
        raise HTTPException(400, "invalid or unsupported audio file") from exc
    return filename, dst, media_duration_ms(dst)


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


@app.post("/api/import")
async def import_file(request: Request, file: UploadFile = File(...)):
    actor = _actor(request)
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


@app.post("/api/stems/split")
async def split_stems(
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
    try:
        actor = _actor(request)
        project = _project_for_actor(request, project_id) if project_id else create_project(
            Path(file.filename or "Stems").stem[:200],
            target if target in {"MTA8", "MTA16"} else "MTA8",
            owner_user_id=actor["id"] if actor["id"] > 0 else None,
        )
    except (OSError, ValueError) as exc:
        raise HTTPException(404, "project not found") from exc
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
            "vocals": "melody", "other": "other"
        }
        for stem in stems:
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
def preview_mix(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    out = pdir(pid) / "preview-master.mp3"
    try:
        validate_project_files(project)
        render_mix(project, audio_path, out, fmt="mp3", bitrate="192k")
    except Exception as exc:
        raise HTTPException(400, "preview mix failed") from exc
    return FileResponse(out, media_type="audio/mpeg", filename="preview-master.mp3")


@app.get("/api/projects/{pid}/export-plan")
def export_plan(pid: str, request: Request):
    project = _project_for_actor(request, pid)
    limit = 8 if project.target == "MTA8" else 16
    return {
        "target": project.target,
        "project_track_count": len(project.tracks),
        "max_output_slots": limit,
        "requires_mapping": len(project.tracks) > limit,
        "suggested_slots": suggested_slots(project),
        "tracks": [{"id": t.id, "name": t.name, "type": t.type} for t in project.tracks],
    }


@app.post("/api/projects/{pid}/export-mta")
def export_mta_with_mapping(pid: str, req: MtaExportRequest, request: Request):
    project = _project_for_actor(request, pid)
    try:
        validate_project_files(project)
        slots = validate_slot_mapping(project, req.slots)
        ext = "mta8" if project.target == "MTA8" else "mta16"
        out = pdir(pid) / f"export.{ext}"
        export_mta(project, out, slots)
    except Exception as exc:
        raise HTTPException(400, str(exc)[:500]) from exc
    return FileResponse(out, filename=_download_name(project.title, ext), media_type="application/octet-stream")


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
        render_track_export(track, audio_path(pid, track.filename), out, fmt=fmt)
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


@app.get("/api/projects/{pid}/export")
def export(pid: str, request: Request, format: str = "mta"):
    project = _project_for_actor(request, pid)
    try:
        validate_project_files(project)
        if format == "mta":
            if len(project.tracks) > (8 if project.target == "MTA8" else 16):
                raise HTTPException(409, "MTA export mapping required; use /export-plan and /export-mta")
            ext = "mta8" if project.target == "MTA8" else "mta16"
            out = pdir(pid) / f"export.{ext}"
            export_mta(project, out)
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
