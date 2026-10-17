"""Per-model opt-in remote inference settings and bounded result decoding.

Only available to the native single-user backend. No implicit local fallback.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from .platform_file_lock import private_mode
import tempfile
import zipfile

KINDS = ('whisper','chords-ml','demucs','drumsep','sam-audio','singer-separation','backing-vocals','markers')


def _file() -> Path:
    return Path(os.getenv('MTA_NATIVE_AI_CONFIG', str(Path.home()/'.config'/'mta-audio-editor'/'remote-workers.json'))).expanduser()


def _read() -> dict:
    try:
        data = json.loads(_file().read_text(encoding='utf-8'))
        if not isinstance(data,dict):return {}
        from .native_ai_account import credentials
        try:
            shared=credentials()
            for worker in data.get('workers',{}).values():
                if worker.get('mode')=='remote':worker.update(shared)
        except ValueError:
            pass
        return data
    except (OSError, ValueError):
        return {}


def public_settings() -> dict:
    return {'workers': {kind: {'mode': _read().get('workers', {}).get(kind, {}).get('mode','local'),
                               'url': _read().get('workers', {}).get(kind, {}).get('url',''),
                               'has_token': bool(_read().get('workers', {}).get(kind, {}).get('token'))}
                        for kind in sorted(set(KINDS)|set(_read().get('workers',{})))}}


def configure(kind: str, mode: str, url: str = '', token: str = '') -> dict:
    if (not isinstance(kind,str) or not __import__('re').fullmatch(r'[a-z][a-z0-9-]{0,63}',kind) or mode not in ('local','remote')):
        raise ValueError('Invalid worker or execution mode')
    from .ai_remote_client import _endpoint
    data = _read()
    workers = data.setdefault('workers',{})
    old = workers.get(kind,{})
    if mode == 'remote' and not token:
        from .native_ai_account import credentials
        try:
            shared=credentials()
            if not url or url.rstrip('/')==shared['url']:
                url,token=shared['url'],shared['token']
        except ValueError:
            pass
    if mode == 'remote':
        _endpoint(url,kind)
        token = token or (old.get('token','') if old.get('url')==url else '')
        if not token or len(token)>4096 or any(c in token for c in '\r\n'):
            raise ValueError('Remote execution requires a personal token')
    workers[kind] = {'mode':mode, 'url':url if mode=='remote' else '', 'token':token if mode=='remote' else ''}
    destination = _file()
    destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd,tmp = tempfile.mkstemp(dir=destination.parent,prefix='.remote-workers-')
    try:
        private_mode(fd)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(data,stream)
        os.replace(tmp,destination)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return public_settings()


def is_remote(kind: str) -> bool:
    return _read().get('workers',{}).get(kind,{}).get('mode') == 'remote'


def infer(kind: str, audio: Path, options: dict | None = None) -> tuple[dict, str]:
    """Infer remotely, returning validated JSON and/or named WAV data. No fallback."""
    from .ai_remote_client import infer_audio, recover_after_lost_response, RemoteAIError
    from . import ai_native_remote_journal as pending
    from .ai_worker_artifacts import SAFE_NAME, MAX_FILES
    from .ai_payload_limits import MAX_ARTIFACT_CEILING_BYTES as MAX_ARTIFACT_BYTES
    cfg = _read().get('workers',{}).get(kind,{})
    if cfg.get('mode') != 'remote': raise ValueError('Remote AI mode not selected')
    from .ai_payload_limits import MAX_SOURCE_BYTES
    from .ai_worker_artifacts import _read_private_file
    wav = _read_private_file(audio, MAX_SOURCE_BYTES)
    # Modern servers attest both the exact request and result bytes.
    # Enable a fail-closed mode for installations requiring this guarantee.
    strict = os.getenv('MTA_REMOTE_AI_REQUIRE_ATTESTATION', '').strip().lower() in ('1','true','yes','on')
    request_id, already_pending, fingerprint = pending.begin(cfg['url'], cfg['token'], kind, wav, options)
    if already_pending:
        payload,mime,job_id = recover_after_lost_response(
            cfg['url'], cfg['token'], request_id, require_attestation=strict)
    else:
        payload,mime,job_id = infer_audio(
            cfg['url'],cfg['token'],kind,wav,options,
            request_id=request_id, require_attestation=strict)
    if mime == 'application/json':
        try:
            value = {'audio': {}, 'json': {'result.json': json.loads(payload.decode('utf-8'))}}
            pending.finish(fingerprint, request_id)
            return value, job_id
        except (UnicodeError, ValueError) as exc:
            raise RemoteAIError('Invalid remote AI JSON result') from exc
    if mime == 'audio/wav':
        value = {'audio':{'result.wav':payload},'json':{}}
        pending.finish(fingerprint, request_id)
        return value,job_id
    result = {'audio':{},'json':{}}
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            entries=z.infolist()
            if len(entries)>MAX_FILES+1: raise ValueError('Too many AI outputs')
            total=0
            for info in entries:
                name=info.filename
                if name=='manifest.json': continue
                if not SAFE_NAME.fullmatch(name) or name.startswith('.') or info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Unsafe AI result member')
                if info.file_size>MAX_ARTIFACT_BYTES: raise ValueError('AI output too large')
                total+=info.file_size
                if total>MAX_ARTIFACT_BYTES: raise ValueError('AI output too large')
                data=z.read(info)
                if name.endswith('.wav'):
                    if data[:4]!=b'RIFF' or data[8:12]!=b'WAVE': raise ValueError('Invalid returned WAV')
                    result['audio'][name]=data
                elif name.endswith('.json'):
                    result['json'][name]=json.loads(data.decode('utf-8'))
                else: raise ValueError('Unexpected AI result type')
            if not result['audio'] and not result['json']: raise ValueError('Empty AI results')
    except (OSError,zipfile.BadZipFile,UnicodeError) as exc:
        raise RemoteAIError('Invalid remote AI artifact archive') from exc
    pending.finish(fingerprint, request_id)
    return result,job_id
