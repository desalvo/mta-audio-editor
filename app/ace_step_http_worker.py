#!/usr/bin/env python3
"""Standalone ACE-Step 1.5 HTTP adapter for the MTA trusted worker protocol.

Requires a separately installed, operator-controlled ACE-Step server. No model
weights, copyrighted data or Python packages from ACE-Step are redistributed.
Loopback HTTP or explicitly trusted HTTPS endpoints (including /api/ai-gateway) are permitted; arbitrary project URLs are rejected.
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
import re
import shutil
from io import BytesIO
# The packaged worker protocol invokes this file by absolute path from an
# isolated temporary cwd. Resolve only its installed sibling, never cwd/PYTHONPATH.
if __package__:
    from .ace_gpu_process_meter import AceProcessMeter
    from .ai_execution_limits import inference_timeout
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ace_gpu_process_meter import AceProcessMeter
    from ai_execution_limits import inference_timeout

MAX_RESULT = 1024 * 1024 * 1024


def endpoint_base() -> str:
    """Resolve a deployment-controlled endpoint, never user/project-supplied URLs.

    Network targets require TLS, an exact host allowlist and an API bearer token.
    SSH tunnels remain supported through localhost HTTP.
    """
    value = os.environ.get('MTA_ACE_STEP_URL', 'http://127.0.0.1:8001').rstrip('/')
    parsed = urlsplit(value)
    local = {'127.0.0.1', 'localhost', '::1'}
    extra = os.environ.get('MTA_ACE_STEP_TRUSTED_HOST', '').strip()
    if extra:
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', extra) or '..' in extra:
            raise ValueError('Invalid trusted ACE-Step host')
    accepted = parsed.hostname in local or (extra and parsed.hostname == extra)
    if (not accepted or parsed.scheme not in ('http', 'https') or parsed.username or parsed.password
            or parsed.path not in ('', '/api/ai-gateway') or parsed.query or parsed.fragment or parsed.port is None
            or not 1 <= parsed.port <= 65535):
        raise ValueError('Invalid or untrusted ACE-Step endpoint')
    if parsed.hostname not in local:
        if parsed.scheme != 'https':
            raise ValueError('Remote ACE-Step requires HTTPS with certificate validation')
        if not os.environ.get('MTA_ACE_STEP_TOKEN', '').strip():
            raise ValueError('Remote ACE-Step requires an API bearer token')
    return value


def _request(url: str, data: bytes | None = None, content_type: str | None = None, *, timeout=30) -> bytes:
    headers = {}
    if content_type:
        headers['Content-Type'] = content_type
    token = os.environ.get('MTA_ACE_STEP_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    # The worker must never resolve non-HTTP schemes or unapproved hosts.
    base = endpoint_base()
    parsed = urlsplit(url)
    trusted = urlsplit(base)
    if parsed.scheme != trusted.scheme or parsed.netloc != trusted.netloc or not parsed.path.startswith('/') or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Untrusted ACE-Step request URL')
    req = Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')  # noqa: S310 -- checked scheme and exact host above
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


def _progress(phase: str, message: str, percent=None, telemetry=None) -> None:
    """Emit only backend-supplied progress; never infer a percentage from elapsed time."""
    path = os.environ.get('MTA_AI_PROGRESS_FILE', '')
    if not path:
        return
    try:
        target = Path(path)
        info = {'phase': phase, 'message': message[:200], 'progress_percent': percent}
        if isinstance(telemetry, dict): info.update(telemetry)
        temporary = target.with_name(target.name + '.tmp')
        temporary.write_text(json.dumps(info), encoding='utf-8')
        os.replace(temporary, target)
    except OSError:
        pass


def run(plan_path: Path, output: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan.get('model_id') != 'ace-step-1.5':
        raise ValueError('This adapter only supports ACE-Step 1.5')
    budget = inference_timeout(plan)
    started = time.monotonic()
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
    _progress('uploading', 'Uploading source audio to ACE-Step')
    body, content_type = _multipart(fields, source.read_bytes())
    base = endpoint_base()
    meter = AceProcessMeter(base)
    _progress('uploading', 'Submitting audio to ACE-Step', telemetry=meter.sample())
    submitted = json.loads(_request(base + '/release_task', body, content_type, timeout=60))
    task = submitted.get('data') if isinstance(submitted, dict) else None
    task_id = task.get('task_id') if isinstance(task, dict) else None
    if not isinstance(task_id, str) or not task_id:
        raise RuntimeError('ACE-Step did not return a task ID')
    _progress('queued', 'ACE-Step accepted job ' + task_id[:12] + '; waiting for inference', telemetry=meter.sample())
    # Keep time for downloading the result before the outer supervisor deadline.
    # Explicit per-job settings supersede the legacy deployment poll override.
    reserve = min(120, budget // 10)
    max_seconds = max(1, budget - reserve)
    if 'inference_timeout_seconds' not in plan and os.environ.get('MTA_ACE_STEP_POLL_SECONDS'):
        max_seconds = max(1, min(max_seconds, int(os.environ['MTA_ACE_STEP_POLL_SECONDS'])))
    deadline = min(started + max(1, budget - reserve), time.monotonic() + max_seconds)
    while time.monotonic() < deadline:
        status_payload = _json(base + '/query_result', {'task_id_list': [task_id]})
        rows = status_payload.get('data')
        row = next((item for item in rows if isinstance(item, dict) and item.get('task_id') == task_id), None) if isinstance(rows, list) else None
        if row:
            supplied = row.get('progress')
            percent = supplied if isinstance(supplied, (int, float)) and 0 <= supplied <= 100 else None
            _progress('inference', 'ACE-Step processing task ' + task_id[:12], percent, meter.sample())
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
            _progress('downloading', 'Retrieving generated audio', telemetry=meter.sample())
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
            _progress('completed', 'ACE-Step audio saved', 100, meter.sample())
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
