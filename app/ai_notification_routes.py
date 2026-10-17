"""Self-service/admin resource summaries and email preferences."""
from __future__ import annotations
import time
from fastapi import APIRouter,Request,HTTPException
from .auth import require_user,require_admin
from . import ai_notifications as mail
from .ai_usage_reporting import snapshot

router=APIRouter()


def _user(request):
    user=require_user(request)
    if int(user['id'])<=0:raise HTTPException(400,'A registered server account is required')
    return int(user['id'])


def _call(fn):
    try:return fn()
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc


@router.get('/api/account/ai-notifications')
def personal_preferences(request:Request):return mail.preferences(_user(request))


@router.put('/api/account/ai-notifications')
def personal_save(request:Request,body:dict):return _call(lambda:mail.set_preferences(_user(request),body))


@router.get('/api/account/ai-resources')
def personal_report(request:Request,start:float=0,end:float|None=None,token_id:int|None=None):
    return _call(lambda:snapshot(_user(request),start,end if end is not None else time.time()+1,token_id=token_id))


@router.get('/api/account/ai-tokens')
def personal_tokens(request:Request):
    from .ai_access import list_tokens
    return list_tokens(_user(request))


@router.delete('/api/account/ai-tokens/{token_id}')
def personal_revoke(request:Request,token_id:int):
    from .ai_access import list_tokens,revoke
    uid=_user(request)
    if not any(row['id']==token_id for row in list_tokens(uid)):raise HTTPException(404,'Token not found')
    return {'ok':revoke(token_id)}


@router.get('/api/admin/ai-notifications')
def admin_preferences(request:Request,user_id:int|None=None):
    require_admin(request)
    if user_id is not None:return mail.preferences(user_id)
    from .auth import db
    with db() as con:
        mail._init(con)
        defaults=dict(con.execute('SELECT * FROM ai_mail_config WHERE id=1').fetchone())
        rows=[dict(r) for r in con.execute('SELECT user_id,cadence,language,cursor FROM ai_mail_preferences')]
        pending=con.execute("SELECT COUNT(*) FROM ai_mail_events WHERE state!='sent'").fetchone()[0]
    return {'default_cadence':defaults['cadence'],'smtp_configured':mail.smtp_configured(),'users':rows,'pending_emails':pending}


@router.put('/api/admin/ai-notifications')
def admin_save(request:Request,body:dict):
    require_admin(request)
    if set(body)-{'user_id','cadence','language'}:raise HTTPException(400,'Unsupported preference')
    if 'user_id' in body and (type(body['user_id']) is not int or body['user_id']<=0):raise HTTPException(400,'Invalid user ID')
    if type(body.get('user_id')) is int:
        return _call(lambda:mail.set_preferences(body['user_id'],{k:v for k,v in body.items() if k!='user_id'}))
    return _call(lambda:mail.set_default(body.get('cadence')))


@router.get('/api/admin/ai-resources')
def admin_report(request:Request,user_id:int,start:float=0,end:float|None=None,token_id:int|None=None):
    require_admin(request)
    return _call(lambda:snapshot(user_id,start,end if end is not None else time.time()+1,token_id=token_id))
