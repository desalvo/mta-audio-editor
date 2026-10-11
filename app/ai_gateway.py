"""Authenticated, bounded pass-through for a private ACE-Step HTTP endpoint."""
from __future__ import annotations
import ipaddress
import os
import time
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from . import ai_access

router = APIRouter()
ALLOWED = {'health','release_task','query_result','v1/audio','v1/init','v1/models','v1/generate','v1/health'}
# The proxy must never route public traffic to raw ACE-Step; clients authenticate here.
MAX_BODY = 32 * 1024 * 1024


def upstream_url() -> str:
    # Server administrator controls this address, never the client.
    target = os.getenv('MTA_ACE_STEP_URL', 'http://127.0.0.1:8001').rstrip('/')
    parsed = urlsplit(target)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/'):
        raise RuntimeError('Invalid configured ACE-Step upstream')
    if parsed.scheme == 'http':
        try:
            if not ipaddress.ip_address(parsed.hostname).is_private:
                raise RuntimeError('Plain HTTP upstream must use a private IP')
        except ValueError:
            if parsed.hostname != 'localhost':
                raise RuntimeError('Plain HTTP upstream must use a private IP')
    return target


@router.api_route('/api/ai-gateway/{path:path}', methods=['GET','POST'])
async def ai_gateway(path: str, request: Request):
    # No cookies/basic login here: only dedicated revocable per-user tokens.
    header = request.headers.get('authorization','')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI user token required')
    if path not in ALLOWED:
        raise HTTPException(404, 'ACE-Step operation not permitted')
    if request.method == 'GET' and path not in {'health','v1/models','v1/health','v1/audio'}:
        raise HTTPException(405, 'Method not permitted')
    started = time.time()
    data = await request.body()
    if len(data) > MAX_BODY:
        raise HTTPException(413, 'AI request too large')
    status = 502
    body = b''
    try:
        import httpx
        headers = {'content-type': request.headers.get('content-type','application/json')}
        # Do not forward client Bearer credentials to upstream ACE-Step.
        internal_key = os.getenv('MTA_ACE_STEP_TOKEN','')
        if internal_key:
            headers['authorization'] = 'Bearer ' + internal_key
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0,connect=10.0),follow_redirects=False,trust_env=False) as client:
            upstream = await client.request(request.method, upstream_url()+'/'+path,
                        params=request.query_params,content=data,headers=headers)
        status = upstream.status_code
        body = upstream.content
        if len(body) > MAX_BODY:
            status,body = 502,b'Upstream response too large'
        return Response(content=body,status_code=status,media_type=upstream.headers.get('content-type','application/octet-stream'))
    except (OSError,RuntimeError,ValueError) as exc:
        raise HTTPException(502,'ACE-Step upstream unavailable') from exc
    except Exception as exc:
        # httpx timeout and transport exceptions
        raise HTTPException(502,'ACE-Step upstream connection failed') from exc
    finally:
        ai_access.usage(identity['id'], identity['user_id'], path,started,status,len(data),len(body))
