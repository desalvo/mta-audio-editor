"""Opt-in remote Arranger/Remix execution with verified metering settlement.

The remote path is deliberately restricted to renderable source selections. It
never silently substitutes a master mix for a selected-track request.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile


def configured_remote():
    """Read server-owned configuration; never accept these values from HTTP."""
    url = os.environ.get('MTA_AI_DURABLE_REMOTE_URL', '').strip()
    if not url:
        return None
    worker = os.environ.get('MTA_AI_DURABLE_REMOTE_WORKER_ID', '').strip()
    token = os.environ.get('MTA_AI_DURABLE_REMOTE_TOKEN', '')
    if not worker or not token:
        raise ValueError('Remote durable AI requires configured worker identity and token')
    return url, worker, token


def render_source(plan, project, resolve_audio, destination):
    """Render exactly the authenticated source chosen for remote inference."""
    from .audio_engine import render_mix, render_track
    from .ai_worker_protocol import verify_preview_wav
    mode = plan.get('input_source', 'legacy_tracks')
    if mode == 'master':
        if plan.get('input_track_id') is not None:
            raise ValueError('Master source cannot include a track selector')
        render_mix(project, resolve_audio, destination, fmt='wav', wav_bit_depth=24)
    elif mode in ('track', 'legacy_tracks'):
        track_id = plan.get('input_track_id')
        if mode == 'legacy_tracks':
            ids = plan.get('track_ids') or [track.id for track in project.tracks]
            if len(ids) != 1:
                raise ValueError('Remote legacy source requires exactly one selected track')
            track_id = ids[0]
        if not track_id:
            raise ValueError('Remote track source requires selected track')
        tracks = [track for track in project.tracks if track.id == track_id]
        if len(tracks) != 1:
            raise ValueError('Remote AI source track not found')
        track = tracks[0]
        source = Path(resolve_audio(project.id, track.filename))
        if source.is_symlink() or not source.is_file():
            raise ValueError('Remote AI source is missing or symbolic link')
        render_track(track, source, destination, apply_inserts=True)
    else:
        raise ValueError('Unsupported remote AI source mode')
    return verify_preview_wav(destination)


def execute(job_id, plan, project, resolve_audio, *, cancel_event=None):
    settings = configured_remote()
    if settings is None:
        raise ValueError('Remote execution not configured')
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError('Remote generation cancelled before submission')
    from . import ai_metering_bridge
    from .ai_worker_protocol import verify_preview_wav
    from .ai_execution_limits import inference_timeout
    timeout = inference_timeout(plan)
    url, worker, token = settings
    with tempfile.TemporaryDirectory(prefix='mta-ai-durable-remote-') as folder:
        source = Path(folder) / 'source.wav'
        render_source(plan, project, resolve_audio, source)
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError('Remote generation cancelled before submission')
        audio, mime, remote_id = ai_metering_bridge.infer_and_register_remote_settlement(
            job_id, base_url=url, token=token, wav=source.read_bytes(),
            worker_id=worker, options={'source': plan.get('input_source', '')},
            timeout_seconds=timeout,
            **({'cancel_event': cancel_event} if cancel_event is not None else {}))
        target = Path(folder) / 'result.wav'
        target.write_bytes(audio)
        info = verify_preview_wav(target)
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError('Remote generation cancelled before publication')
        return audio, {**info, 'remote_job_id': remote_id, 'mode': 'remote'}
