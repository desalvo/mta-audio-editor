"""Active-admin,CSRF-protected service drain control;never change regime/money."""
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import JSONResponse
import sqlite3

from . import auth,service_admission as admission
from .regime_operation_fence import FenceBlocked

router = APIRouter()
NO_STORE = {'Cache-Control':'private, no-store','Pragma':'no-cache'}


def _actor(request,write=False):
    user = auth.session_user(request)
    if not user: raise HTTPException(401,'Authentication required')
    if user['role']!='admin' or not user['active']: raise HTTPException(403,'Active administrator required')
    if write and request.headers.get('x-mta-request')!='1': raise HTTPException(403,'Request integrity marker required')
    return user['id']


@router.get('/api/admin/service-admission')
def status(request:Request):
    actor = _actor(request)
    try: return JSONResponse(admission.inspect(actor=actor),headers=NO_STORE)
    except (FenceBlocked,sqlite3.Error,OSError) as exc: raise HTTPException(409,'Service admission evidence unavailable') from exc


@router.post('/api/admin/service-admission/change')
def change(request:Request,body:dict):
    actor = _actor(request,True)
    if set(body)!={'expected_generation','draining','identifier','confirm'}:
        raise HTTPException(400,'Exact service admission control fields required')
    try: return JSONResponse(admission.change(actor=actor,**body),headers=NO_STORE)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    except (FenceBlocked,sqlite3.Error,OSError) as exc: raise HTTPException(409,'Service admission conflict or evidence unavailable') from exc


@router.post('/api/admin/service-admission/upgrade')
def upgrade(request:Request,body:dict):
    actor=_actor(request,True)
    if set(body)!={'expected_generation','expected_build','confirm'}:
        raise HTTPException(400,'Exact service build handoff fields required')
    try:return JSONResponse(admission.upgrade(actor=actor,**body),headers=NO_STORE)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    except (FenceBlocked,sqlite3.Error,OSError) as exc:raise HTTPException(409,'Service build handoff is not verified') from exc
