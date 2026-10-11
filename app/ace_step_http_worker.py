#!/usr/bin/env python3
"""Standalone ACE-Step 1.5 HTTP adapter for the MTA trusted worker protocol.

Requires a separately installed, operator-controlled ACE-Step server. No model
weights, copyrighted data or Python packages from ACE-Step are redistributed.
Only loopback HTTP or an explicitly trusted internal sidecar hostname is permitted.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
import uuid
import wave
import tempfile
import shutil
from io import BytesIO

MAX_RESULT = 1024 * 1024 * 1024


def endpoint_base() -> str:
    value = os.environ.get('MTA_ACE_STEP_URL', 'http://127.0.0.1:8001').rstrip('/')
    parsed = urlsplit(value)
    trusted = {'127.0.0.1', 'localhost', '::1'}
    # The sole additional hostname must be provided by the trusted deployment,
    # never by project data or client input (Docker internal-only network).
    extra = os.environ.get('MTA_ACE_STEP_TRUSTED_HOST', '').strip()
    if extra and extra.isascii() and all(c.isalnum() or c == '-' for c in extra) and len(extra) <= 63:
        trusted.add(extra)
    if parsed.scheme != 'http' or parsed.hostname not in trusted or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('ACE-Step must be bound to a loopback HTTP endpoint (use an SSH tunnel for remote instances)')
    if parsed.port is None or not 1 <= parsed.port <= 65535:
        raise ValueError('ACE-Step URL requires an explicit valid port')
    return value


def _request(url: str, data: bytes | None = None, content_type: str | None = None, *, timeout=30) -> bytes:
    headers = {}
    if content_type:
        headers['Content-Type'] = content_type
    token = os.environ.get('MTA_ACE_STEP_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            raise ValueError('ACE-Step redirect denied')
    # Ignore proxy environment settings even for loopback and internal sidecar endpoints.
    from urllib.request import ProxyHandler
    with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout) as response:
        if response.geturl().split('?', 1)[0] != url.split('?', 1)[0]:
            raise ValueError('ACE-Step redirected its response')
        size = response.headers.get('Content-Length')
        if size and int(size) > MAX_RESULT:
            raise ValueError('ACE-Step audio exceeds maximum size')
        payload = response.read(MAX_RESULT + 1)
        if len(payload) > MAX_RESULT:
            raise ValueError('ACE-Step audio exceeds maximum size')
        return payload


def _json(url: str, data: dict) -> dict:
    result = json.loads(_request(url, json.dumps(data).encode(), 'application/json'))
    if not isinstance(result, dict) or result.get('code') not in (None, 200):
        raise RuntimeError('ACE-Step API reported an error')
    return result


def _multipart(fields: dict[str, str], audio: bytes) -> tuple[bytes, str]:
    boundary = 'mta' + uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode())
    parts.extend([(f'--{boundary}\r\nContent-Disposition: form-data; name="src_audio"; filename="source.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode(), audio, b'\r\n', f'--{boundary}--\r\n'.encode()])
    return b''.join(parts), 'multipart/form-data; boundary=' + boundary


def _source_path(request_file: Path, plan: dict) -> Path:
    sources = plan.get('source_audio')
    if not isinstance(sources, list) or len(sources) != 1:
        raise ValueError('ACE-Step adapter requires exactly one rendered track/master WAV input')
    name = sources[0].get('filename')
    if not isinstance(name, str) or not name.startswith('inputs/') or '/' in name[7:] or '\\' in name:
        raise ValueError('invalid staged audio name')
    path = request_file.parent / name
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(request_file.parent.resolve()):
        raise ValueError('unsafe staged audio')
    if path.stat().st_size > 512 * 1024 * 1024:
        raise ValueError('staged audio too large')
    return path


def run(plan_path: Path, output: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan.get('model_id') != 'ace-step-1.5':
        raise ValueError('This adapter only supports ACE-Step 1.5')
    source = _source_path(plan_path, plan)
    operation = plan.get('operation', 'rearrange')
    if operation not in ('rearrange', 'remix'):
        raise ValueError('unsupported operation')
    # Audio-to-audio cover is supported by ACE-Step; harmonic/voice preservation
    # is best effort and is NOT guaranteed by this API.
    prompt = str(plan.get('prompt', '')).strip()[:3000]
    if not prompt:
        raise ValueError('empty arranger prompt')
    fields = {'prompt': prompt, 'task_type': 'cover', 'audio_format': 'wav',
              'audio_cover_strength': str(1.0 - max(0, min(100, int(plan.get('strength', 60)))) / 100)}
    body, content_type = _multipart(fields, source.read_bytes())
    base = endpoint_base()
    submitted = json.loads(_request(base + '/release_task', body, content_type, timeout=60))
    task = submitted.get('data') if isinstance(submitted, dict) else None
    task_id = task.get('task_id') if isinstance(task, dict) else None
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeError('ACE-Step did not return a task ID')
    max_seconds = max(30, min(3500, int(os.environ.get('MTA_ACE_STEP_POLL_SECONDS', '1100'))))
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        status_payload = _json(base + '/query_result', {'task_id_list': [task_id]})
        rows = status_payload.get('data')
        row = next((item for item in rows if isinstance(item, dict) and item.get('task_id') == task_id), None) if isinstance(rows, list) else None
        if row and row.get('status') == 2:
            raise RuntimeError('ACE-Step generation failed')
        if row and row.get('status') == 1:
            result = row.get('result')
            parsed = json.loads(result) if isinstance(result, str) else result
            if not isinstance(parsed, list) or not parsed or not isinstance(parsed[0], dict):
                raise RuntimeError('ACE-Step returned invalid task output')
            audio_url = parsed[0].get('file')
            if not isinstance(audio_url, str) or not audio_url.startswith('/v1/audio?') or '#' in audio_url or '://' in audio_url or '\\' in audio_url or any(ord(c) < 32 for c in audio_url):
                raise RuntimeError('ACE-Step returned unsafe audio URL')
            preview = _request(base + audio_url, timeout=120)
            # Reject HTML error pages, partial payloads and invalid/malicious wave data
            # before the external worker protocol accepts the result.
            try:
                with wave.open(BytesIO(preview), 'rb') as wav:
                    if wav.getnchannels() not in (1, 2) or wav.getsampwidth() not in (2, 3, 4):
                        raise ValueError('unsupported ACE-Step audio channels or bit depth')
                    if wav.getframerate() not in (44100, 48000, 96000) or not 0 < wav.getnframes() <= wav.getframerate() * 1800:
                        raise ValueError('unsupported ACE-Step audio rate or duration')
                    expected = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
                    if len(wav.readframes(wav.getnframes())) != expected:
                        raise ValueError('truncated ACE-Step WAV data')
            except (wave.Error, EOFError) as exc:
                raise ValueError('ACE-Step returned invalid WAV audio') from exc
            output.write_bytes(preview)
            return
        time.sleep(2)
    raise RuntimeError('ACE-Step generation timed out')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--capabilities', action='store_true')
    parser.add_argument('--check-server', action='store_true', help='Check loopback API reachability; does not test inference')
    parser.add_argument('--smoke-input', type=Path, help='Opt-in actual inference with a local test WAV')
    parser.add_argument('--request', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.capabilities:
        print(json.dumps({'protocol': 'mta.ai.worker.v1', 'models': ['ace-step-1.5'], 'supports_audio_input': True}))
        return 0
    if args.check_server:
        try:
            base = endpoint_base()
            response = _request(base + '/health', timeout=5)
            # A proxy splash page is not a healthy ACE-Step endpoint.
            health = json.loads(response)
            if not isinstance(health, dict):
                raise ValueError('ACE-Step health endpoint did not return a JSON object')
            print(json.dumps({'server_reachable': True, 'health': health, 'inference_verified': False}))
            return 0
        except (OSError, ValueError, json.JSONDecodeError, HTTPError, URLError) as exc:
            print(f'ACE-Step server unavailable: {exc}', file=sys.stderr)
            return 1
    if args.smoke_input:
        if not args.output or not args.smoke_input.is_file():
            parser.error('--smoke-input requires an existing WAV and --output')
        try:
            with tempfile.TemporaryDirectory(prefix='mta-ace-smoke-') as folder:
                base = Path(folder)
                (base / 'inputs').mkdir()
                staged = base / 'inputs' / 'source.wav'
                shutil.copyfile(args.smoke_input, staged)
                plan = base / 'request.json'
                plan.write_text(json.dumps({'model_id': 'ace-step-1.5', 'operation': 'remix',
                    'prompt': 'A short instrumental arrangement, melodic and clear', 'strength': 50,
                    'source_audio': [{'filename': 'inputs/source.wav'}]}))
                run(plan, args.output)
            return 0
        except (OSError, ValueError, RuntimeError, HTTPError, URLError, KeyError, TypeError) as exc:
            print(f'ACE-Step smoke inference error: {exc}', file=sys.stderr)
            return 1
    if not args.request or not args.output:
        parser.error('--request and --output required')
    try:
        run(args.request, args.output)
    except (OSError, ValueError, RuntimeError, HTTPError, URLError, KeyError, TypeError) as exc:
        print(f'ACE-Step adapter error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
