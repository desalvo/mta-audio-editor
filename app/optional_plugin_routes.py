"""Operator-only optional native/server VST3 installation controls."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from . import auth, optional_plugins as plugins

router=APIRouter()


def _operator(request):
    return auth.require_admin(request)


@router.get('/api/admin/optional-vst3')
def catalog(request:Request):
    _operator(request)
    return plugins.catalog()


@router.get('/api/admin/optional-vst3/{identifier}/license',response_class=PlainTextResponse)
def license_text(request:Request,identifier:str):
    _operator(request)
    spec=next((p for p in plugins.catalog()['plugins'] if p['id']==identifier),None)
    if not spec:raise HTTPException(404,'Plugin not found')
    return (plugins.LICENSES/spec['license_file']).read_text(encoding='utf-8')


@router.post('/api/admin/optional-vst3/install')
def install(request:Request,body:dict):
    _operator(request)
    if set(body)!={'plugins','accept_licenses'} or body['accept_licenses'] is not True:raise HTTPException(422,'Review and accept the plugin licenses before installation')
    try:return plugins.start(body['plugins'])
    except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc


@router.get('/api/admin/optional-vst3/jobs/{identifier}')
def status(request:Request,identifier:str):
    _operator(request)
    try:return plugins.status(identifier)
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc
