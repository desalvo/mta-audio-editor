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
    created = ai_access.issue(found['user_id'],found['label'])
    ai_access.revoke(token_id)
    return created

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
    return HTMLResponse('''<!doctype html><html lang="en"><meta charset="utf-8"><title>AI access tokens</title>
<style>body{font:16px system-ui;max-width:960px;margin:30px auto;padding:12px}input,button{padding:8px;margin:4px}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left}code{overflow-wrap:anywhere}</style>
<h1>AI access tokens</h1><p>Create one token per user/device, rotate or revoke independently. Tokens are shown <b>once</b>.</p>
<label>User ID <input id="uid" type="number" min="1" required></label><label>Label <input id="label" value="AI client"></label>
<button onclick="create()">Create token</button><p id="message" role="status"></p><table><thead><tr><th>ID</th><th>User</th><th>Label</th><th>Status</th><th>Action</th></tr></thead><tbody id="entries"></tbody></table>
<h2>Usage (gateway requests)</h2><pre id="usage"></pre><p>Wall time and transfer bytes are measured. Actual attributed GPU/CPU usage requires worker instrumentation, and is not yet available for billing.</p>
<script>
const msg=document.getElementById('message');
async function call(url,method='GET',body){const r=await fetch(url,{method,credentials:'same-origin',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(d.detail||r.status);return d;}
async function create(){try{let d=await call('/api/admin/ai-tokens','POST',{user_id:+uid.value,label:document.getElementById('label').value});msg.replaceChildren('New token (copy now): ');let c=document.createElement('code');c.textContent=d.token;msg.append(c);await refresh();}catch(e){msg.textContent=e.message}}
async function act(id,action){if(!confirm(action+' token '+id+'?'))return;try{let d=await call('/api/admin/ai-tokens/'+id+(action==='rotate'?'/rotate':''),action==='rotate'?'POST':'DELETE');msg.textContent=action==='rotate'?'New token (copy now): '+d.token:'Token revoked';await refresh()}catch(e){msg.textContent=e.message}}
async function refresh(){let arr=await call('/api/admin/ai-tokens');entries.replaceChildren();for(let t of arr){let tr=document.createElement('tr');for(let x of [t.id,t.user_id,t.label,t.revoked_at?'revoked':'active']){let td=document.createElement('td');td.textContent=x;tr.append(td)}let td=document.createElement('td');if(!t.revoked_at){for(let action of ['rotate','revoke']){let b=document.createElement('button');b.textContent=action;b.onclick=()=>act(t.id,action);td.append(b)}}tr.append(td);entries.append(tr)}usage.textContent=JSON.stringify(await call('/api/admin/ai-usage'),null,2)}refresh().catch(e=>msg.textContent=e.message);
</script></html>''')
