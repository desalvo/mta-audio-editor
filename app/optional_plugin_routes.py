"""Operator-only optional native/server VST3 installation controls."""
import os
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from . import auth, optional_plugins as plugins

router=APIRouter()


def _operator(request):
    if request.url.path.startswith('/api/native/') and os.getenv('MTA_NATIVE_SINGLE_USER','').lower() not in {'1','true','yes','on'}:
        raise HTTPException(404,'Native plugin settings unavailable')
    return auth.require_admin(request)


@router.get('/api/native/optional-vst3')
@router.get('/api/admin/optional-vst3')
def catalog(request:Request):
    _operator(request)
    return plugins.catalog()


@router.get('/api/native/optional-vst3/{identifier}/license',response_class=PlainTextResponse)
@router.get('/api/admin/optional-vst3/{identifier}/license',response_class=PlainTextResponse)
def license_text(request:Request,identifier:str):
    _operator(request)
    spec=next((p for p in plugins.catalog()['plugins'] if p['id']==identifier),None)
    if not spec:raise HTTPException(404,'Plugin not found')
    return (plugins.LICENSES/spec['license_file']).read_text(encoding='utf-8')


@router.post('/api/native/optional-vst3/install')
@router.post('/api/admin/optional-vst3/install')
def install(request:Request,body:dict):
    _operator(request)
    if set(body)!={'plugins','accept_licenses'} or body['accept_licenses'] is not True:raise HTTPException(422,'Review and accept the plugin licenses before installation')
    try:return plugins.start(body['plugins'])
    except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc


@router.get('/api/native/optional-vst3/jobs/{identifier}')
@router.get('/api/admin/optional-vst3/jobs/{identifier}')
def status(request:Request,identifier:str):
    _operator(request)
    try:return plugins.status(identifier)
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc


@router.get('/api/native/optional-vst3/{identifier}/uninstall')
@router.get('/api/admin/optional-vst3/{identifier}/uninstall')
def uninstall_info(request:Request,identifier:str):
    _operator(request)
    try:return plugins.uninstall_info(identifier)
    except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc


@router.post('/api/native/optional-vst3/{identifier}/uninstall')
@router.post('/api/admin/optional-vst3/{identifier}/uninstall')
def uninstall(request:Request,identifier:str,body:dict):
    _operator(request)
    if set(body)!={'confirm','remove_build_cache'} or body['confirm'] is not True or type(body['remove_build_cache']) is not bool:
        raise HTTPException(422,'Confirm uninstall and choose whether to remove the build cache')
    try:return plugins.uninstall(identifier,remove_build_cache=body['remove_build_cache'])
    except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc
