"""Admin-only AI token management API and web page."""
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from .auth import require_admin, require_user
from . import ai_access

router = APIRouter()

@router.get('/api/admin/ai-tokens')
def tokens(request: Request):
    require_admin(request)
    return ai_access.list_tokens()

@router.post('/api/admin/ai-tokens')
def create(request: Request, body: dict):
    require_admin(request)
    try:
        return ai_access.issue(int(body['user_id']),str(body.get('label','AI client')))
    except (KeyError,ValueError,TypeError) as exc:
        raise HTTPException(400,str(exc)) from exc

@router.delete('/api/admin/ai-tokens/{token_id}')
def delete(token_id: int,request: Request):
    require_admin(request)
    if not ai_access.revoke(token_id):
        raise HTTPException(404,'Token not found or already revoked')
    return {'ok':True}

@router.post('/api/admin/ai-tokens/{token_id}/rotate')
def rotate(token_id: int,request: Request):
    require_admin(request)
    found = next((t for t in ai_access.list_tokens() if t['id']==token_id and not t['revoked_at']),None)
    if not found:
        raise HTTPException(404,'Active token not found')
    try:
        return ai_access.rotate(token_id)
    except ValueError as exc:
        raise HTTPException(404, 'Active token not found') from exc

@router.get('/api/admin/ai-usage')
def all_usage(request: Request):
    require_admin(request)
    return {'units':'wall_ms / bytes; NOT GPU or CPU billable time', 'items':ai_access.summary()}

@router.get('/api/account/ai-usage')
def personal_usage(request: Request):
    actor=require_user(request)
    return {'items':ai_access.summary(actor['id'])}

@router.get('/admin/ai-tokens',response_class=HTMLResponse)
def admin_page(request: Request):
    require_admin(request)
    from pathlib import Path
    return HTMLResponse((Path(__file__).parent / 'templates' / 'ai_tokens.html').read_text(encoding='utf-8'))
