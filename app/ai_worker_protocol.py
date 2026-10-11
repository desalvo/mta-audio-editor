"""External AI worker contract. No model weights or inference is bundled.

A trusted administrator installs/configures a worker executable; no user-provided
commands, shell invocation, URLs, or arbitrary output paths are accepted.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import wave
import stat
import shutil
import re

MAX_REQUEST_BYTES = 256_000
MAX_WAV_BYTES = 1024 * 1024 * 1024

class WorkerUnavailable(RuntimeError):
    pass


def configured_worker() -> Path | None:
    """An explicit opt-in. Do not infer readiness from a model catalog entry."""
    if os.getenv('MTA_AI_WORKER_ENABLED', '').lower() != 'true':
        return None
    value = os.getenv('MTA_AI_WORKER_EXECUTABLE', '')
    if not value or not Path(value).is_absolute():
        return None
    path = Path(value)
    if path.is_symlink() or not path.is_file() or not os.access(path, os.X_OK):
        return None
    return path


def verify_preview_wav(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('worker preview is missing or symbolic link')
    size = path.stat().st_size
    if not 44 <= size <= MAX_WAV_BYTES:
        raise ValueError('worker preview has invalid size')
    with wave.open(str(path), 'rb') as wav:
        channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
        width = wav.getsampwidth()
        if channels not in (1, 2) or rate not in (44100, 48000, 96000):
            raise ValueError('unsupported AI preview audio format')
        if width not in (2, 3, 4) or frames == 0 or frames > rate * 60 * 30:
            raise ValueError('invalid AI preview duration or bit depth')
        if frames * channels * width + 44 > size + 4096:
            raise ValueError('truncated AI preview WAV')
        if wav.getcomptype() != 'NONE':
            raise ValueError('compressed AI preview WAV is unsupported')
    return {'channels': channels, 'sample_rate': rate, 'frames': frames, 'bytes': size}


def run_external_worker(plan: dict, *, timeout_seconds: int = 1200) -> tuple[bytes, dict]:
    """Invoke an installed worker with JSON file input, validated WAV output.

    The worker must accept: --request <path> --output <path>.
    This is a detached non-realtime operation. It is not ACE-Step by itself.
    """
    worker = configured_worker()
    if worker is None:
        raise WorkerUnavailable('No trusted AI inference executable is configured')
    raw = json.dumps(plan, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError('AI request exceeds size limit')
    if not 1 <= timeout_seconds <= 3600:
        raise ValueError('invalid worker timeout')
    with tempfile.TemporaryDirectory(prefix='mta-ai-') as folder:
        directory = Path(folder)
        request = directory / 'request.json'
        output = directory / 'preview.wav'
        request.write_bytes(raw)
        request.chmod(0o600)
        try:
            completed = subprocess.run(([sys.executable, str(worker)] if worker.suffix == '.py' else [str(worker)]) + ['--request', str(request), '--output', str(output)],
                shell=False, cwd=str(directory), capture_output=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            raise WorkerUnavailable('AI worker timed out') from exc
        if completed.returncode:
            raise WorkerUnavailable('AI worker exited unsuccessfully')
        info = verify_preview_wav(output)
        return output.read_bytes(), info



_SAFE_AUDIO_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MAX_SOURCE_BYTES = 512 * 1024 * 1024
MAX_SOURCE_DURATION_SECONDS = 1800


def run_worker_with_project_audio(plan: dict, project, resolve_audio, *, timeout_seconds: int = 1200):
    """Run a trusted worker with copied project WAV inputs, not host file paths.

    Source files are discovered from the authenticated project object. The resolver
    must be the server's project-local audio_path, never an HTTP-supplied pathname.
    Worker receives workspace-relative source filenames in request['source_audio'].
    Current protocol supports WAV only; other codecs require a trusted converter.
    """
    worker = configured_worker()
    if worker is None:
        raise WorkerUnavailable('No trusted AI inference executable is configured')
    if not 1 <= timeout_seconds <= 3600:
        raise ValueError('invalid worker timeout')
    from .audio_engine import render_mix, render_track
    source_mode = plan.get('input_source', 'legacy_tracks')
    if source_mode not in ('master', 'track', 'legacy_tracks'):
        raise ValueError('invalid audio input source')
    input_id = plan.get('input_track_id')
    if source_mode == 'track' and not input_id:
        raise ValueError('input track required')
    if source_mode == 'master' and input_id is not None:
        raise ValueError('master input cannot select a track')
    selected = ({input_id} if source_mode == 'track' else
                set(plan.get('track_ids') or []) if plan.get('scope') == 'tracks' else None)
    tracks = [t for t in project.tracks if selected is None or t.id in selected]
    if not tracks:
        raise ValueError('No source tracks selected')
    if len(tracks) > 64:
        raise ValueError('Too many input audio tracks')
    with tempfile.TemporaryDirectory(prefix='mta-ai-') as folder:
        directory = Path(folder)
        inputs = directory / 'inputs'
        inputs.mkdir(mode=0o700)
        sources = []
        total = 0
        if source_mode == 'master':
            # Share the exact export mixer: track/master inserts, mute/solo, pan and faders.
            # Never reuse preview-mix, which intentionally neutralizes the master fader.
            master = inputs / 'master.wav'
            render_mix(project, resolve_audio, master, fmt='wav', wav_bit_depth=24)
            info = verify_preview_wav(master)
            if info['bytes'] > MAX_SOURCE_BYTES:
                raise ValueError('AI master audio exceeds size limit')
            master.chmod(0o400)
            sources.append({'track_id': None, 'kind': 'master', 'filename': 'inputs/master.wav',
                            'channels': info['channels'], 'sample_rate': info['sample_rate'], 'frames': info['frames'],
                            'rendered_with': 'project_master_mix'})
        for index, track in enumerate(tracks if source_mode in ('track', 'legacy_tracks') else []):
            filename = track.filename
            if not _SAFE_AUDIO_NAME.fullmatch(filename) or not filename.lower().endswith('.wav'):
                raise ValueError('AI worker currently requires WAV source tracks')
            source = Path(resolve_audio(project.id, filename))
            if source.is_symlink() or not source.is_file():
                raise ValueError('AI input track is missing or symbolic link')
            # Render track inserts before presenting it to the model; the input
            # is isolated from other tracks, ignoring their mute/solo status.
            target = inputs / f'{index:03d}.wav'
            if source_mode == 'legacy_tracks':
                shutil.copyfile(source, target)
            else:
                render_track(track, source, target, apply_inserts=True)
            info = verify_preview_wav(target)
            total += info['bytes']
            if total > MAX_SOURCE_BYTES:
                raise ValueError('AI project audio exceeds size limit')
            target.chmod(0o400)
            sources.append({'track_id': track.id, 'filename': 'inputs/' + target.name,
                            'channels': info['channels'], 'sample_rate': info['sample_rate'],
                            'frames': info['frames'], 'kind': 'track', 'rendered_with': 'track_inserts'})
        # A plan must never be allowed to spoof the server-created source manifest.
        if any(item['frames'] > item['sample_rate'] * MAX_SOURCE_DURATION_SECONDS for item in sources):
            raise ValueError('AI source audio is too long')
        request_data = dict(plan)
        request_data['source_audio'] = sources
        raw = json.dumps(request_data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError('AI request exceeds size limit')
        request = directory / 'request.json'
        output = directory / 'preview.wav'
        request.write_bytes(raw)
        request.chmod(0o600)
        try:
            result = subprocess.run(([sys.executable, str(worker)] if worker.suffix == '.py' else [str(worker)]) + ['--request', str(request), '--output', str(output)],
                shell=False, cwd=str(directory), capture_output=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired as exc:
            raise WorkerUnavailable('AI worker timed out') from exc
        if result.returncode:
            raise WorkerUnavailable('AI worker exited unsuccessfully')
        meta = verify_preview_wav(output)
        # A worker output must be derived from a plausible source duration.
        # Allow up to 4x for intentional tempo/style variations, but reject
        # obviously unbounded/incorrect results before exposing them to users.
        max_duration = max(item['frames'] / item['sample_rate'] for item in sources)
        if meta['frames'] / meta['sample_rate'] > max(15.0, max_duration * 4.0):
            raise ValueError('AI preview duration exceeds source limit')
        return output.read_bytes(), meta

def probe_worker(*, timeout_seconds: float = 2.0) -> dict:
    """Optional non-realtime executable handshake; never establishes inference readiness.

    Protocol: executable --capabilities must emit one small JSON document.
    Failure is fail-closed. No user-supplied commands or shell are involved.
    """
    path = configured_worker()
    result = {'probe_ok': False, 'declared_models': [], 'supports_audio_input': False}
    if path is None:
        return result
    try:
        completed = subprocess.run(([sys.executable, str(path)] if path.suffix == '.py' else [str(path)]) + ['--capabilities'], shell=False,
            capture_output=True, timeout=timeout_seconds, check=False)
        if completed.returncode or len(completed.stdout) > 16_384:
            return result
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict) or payload.get('protocol') != 'mta.ai.worker.v1':
            return result
        models = payload.get('models')
        if not isinstance(models, list) or len(models) > 16 or not all(
            isinstance(item, str) and item in ('ace-step-1.5', 'diffrhythm-2') for item in models
        ):
            return result
        return {'probe_ok': True, 'declared_models': models,
                'supports_audio_input': payload.get('supports_audio_input') is True}
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        return result


def worker_capabilities() -> dict:
    """Status is infrastructural, not a claim that ACE-Step inference works."""
    path = configured_worker()
    probe = probe_worker()
    return {
        **probe,
        'worker_configured': path is not None,
        'inference_verified': False,
        'ace_step_ready': False,
        'remix_ready': False,
        'note': ('External worker configured; run an end-to-end audio test before enabling production.'
                 if path else 'No external worker configured.'),
    }
