"""Authenticated snapshot creation and restore archive preflight."""
import os
from pathlib import Path
import tempfile
import zipfile
from fastapi import HTTPException, Request, UploadFile, File, Body
from fastapi.responses import FileResponse, HTMLResponse
from starlette.background import BackgroundTask
from . import auth, admin_dump


def register_routes(app):
    @app.get('/docs/admin/application-dump', response_class=HTMLResponse)
    def guide(request: Request):
        auth.require_admin(request)
        return (Path(__file__).parent/'docs/application-dump.html').read_text()

    @app.get('/api/admin/application-dump/catalog')
    def catalog(request: Request):
        auth.require_admin(request)
        return admin_dump.catalog()

    @app.post('/api/admin/application-dump/preview')
    def preview(request: Request, body: dict = Body(...)):
        auth.require_admin(request)
        try:
            _, uids, pids = admin_dump.selection(body)
            return {'user_ids': sorted(uids), 'project_ids': sorted(pids), 'users': len(uids), 'projects': len(pids), 'admin_accounts_included': True}
        except ValueError as exc: raise HTTPException(422, str(exc)) from exc

    @app.post('/api/admin/application-dump')
    def create(request: Request, body: dict = Body(...)):
        auth.require_admin(request)
        try: path = admin_dump.create(body)
        except (ValueError, OSError, zipfile.BadZipFile) as exc: raise HTTPException(409, str(exc)) from exc
        return FileResponse(path, media_type='application/zip', filename='MTA-' + admin_dump.APP_RELEASE + '-application-dump.zip',
                            headers={'Cache-Control': 'private, no-store'}, background=BackgroundTask(lambda: path.unlink(missing_ok=True)))

    @app.post('/api/admin/application-dump/restore-preview')
    async def restore_preview(request: Request, file: UploadFile = File(...)):
        auth.require_admin(request)
        fd, name = tempfile.mkstemp(prefix='mta-restore-preview-', suffix='.zip'); os.close(fd)
        path = Path(name)
        try:
            total = 0
            with path.open('wb') as out:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > admin_dump.limit(): raise ValueError('Archivio oltre il limite configurato')
                    out.write(chunk)
            value = admin_dump.inspect(path)
            return {'valid': True, 'release': value['release'], 'users': len(value['user_ids']), 'projects': len(value['project_ids']), 'restore_mode': 'offline-empty-target',
                    'message': 'Integrità ZIP e SHA-256 verificata. Il ripristino richiede il servizio fermo e directory vuote; il comando verifica anche database, admin e progetti prima di pubblicare i dati.'}
        except (ValueError, OSError, zipfile.BadZipFile, KeyError, TypeError) as exc: raise HTTPException(422, str(exc)) from exc
        finally: path.unlink(missing_ok=True); await file.close()
