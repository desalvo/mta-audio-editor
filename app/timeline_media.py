"""Cross-track edits publish immutable, lossless track sources.

Callers hold the project publication lock from loading through saving. Original
sources remain in the project library so undo and archive export can use them.
"""
import json
import os
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf
from pydantic import BaseModel, Field

from . import ai_media_identity, ai_upload_transaction, storage
from .audio_engine import ensure_clips, waveform_peaks
from .models import Clip, ProjectClip, Track
from .project_kinds import require_kind

LIMIT_MS = 86_400_000


class EmptyTrackRequest(BaseModel):
    name: str = Field(default='Empty track', min_length=1, max_length=200)
    kind: Literal['audio', 'midi'] = 'audio'
    after_track_id: str | None = None


class TimelinePart(BaseModel):
    track_id: str | None = None
    clip_id: str | None = None
    filename: str | None = Field(default=None, min_length=1, max_length=128)
    source_start_ms: int = Field(ge=0, le=LIMIT_MS)
    source_end_ms: int = Field(gt=0, le=LIMIT_MS)
    offset_ms: int = Field(default=0, ge=0, le=LIMIT_MS)
    expected_start_ms: int | None = Field(default=None, ge=-LIMIT_MS, le=LIMIT_MS)


class TimelineTransferRequest(BaseModel):
    destination_track_id: str
    start_ms: int = Field(ge=0, le=LIMIT_MS)
    action: Literal['copy', 'move'] = 'copy'
    parts: list[TimelinePart] = Field(min_length=1, max_length=512)



class TimelineJoinRequest(BaseModel):
    track_id: str
    parts: list[TimelinePart] = Field(min_length=2, max_length=2)


def _source(project, name):
    # Check the directory entry before audio_path resolves it.
    entry = storage.pdir(project.id) / 'audio' / name
    path = storage.audio_path(project.id, name)
    if not stat.S_ISREG(entry.lstat().st_mode) or entry.is_symlink():
        raise ValueError('Sorgente audio non disponibile')
    return path


def _retain(project, track):
    asset = next((x for x in project.clip_library if x.filename == track.filename), None)
    if asset is None:
        if len(project.clip_library) >= 512:
            raise ValueError('Libreria del progetto piena')
        asset = ProjectClip(id=uuid.uuid4().hex[:12], name=track.name,
            filename=track.filename, duration_ms=track.duration_ms, type=track.type,
            channels=track.channels, channel_layout=track.channel_layout,
            sample_rate=track.sample_rate, current_location='audio/' + track.filename,
            provenance='Editing timeline')
        project.clip_library.append(asset)
    track.source_clip_id = asset.id


def _create_output(project):
    name = 'timeline-' + uuid.uuid4().hex + '.wav'
    path = storage.audio_path(project.id, name)
    handle = path.open('xb')
    ai_media_identity.record_upload(project.id, path)
    return name, path, handle


def _sync(handle, path):
    handle.flush()
    os.fsync(handle.fileno())
    storage._fsync_directory(path.parent)


def empty_track(project, req, capacity_check=None):
    require_kind(project, req.kind)
    if len(project.tracks) >= 1024:
        raise ValueError('Limite di tracce raggiunto')
    if req.after_track_id and not any(t.id == req.after_track_id for t in project.tracks):
        raise ValueError('Traccia di riferimento non trovata')
    if capacity_check:
        capacity_check(project.owner_user_id, 4096)
    ai_upload_transaction.begin(project.id)
    try:
        name, path, handle = _create_output(project)
        with handle:
            with sf.SoundFile(handle, 'w', samplerate=project.sample_rate,
                              channels=2, format='WAV', subtype='FLOAT', closefd=False) as out:
                out.write(np.zeros((max(1, project.sample_rate // 1000), 2), dtype='float32'))
                out.flush()
            _sync(handle, path)
        track = Track(id=uuid.uuid4().hex[:12], name=req.name, filename=name,
            kind=req.kind, channels=2, channel_layout='stereo',
            sample_rate=project.sample_rate, duration_ms=0, clips_initialized=True)
        index = next((i + 1 for i, t in enumerate(project.tracks) if t.id == req.after_track_id), len(project.tracks))
        project.tracks.insert(index, track)
        _retain(project, track)
        storage.save_project(project)
    except BaseException:
        ai_upload_transaction.reconcile(project.id)
        raise
    ai_upload_transaction.finish(project.id)
    return {'project': project, 'track_id': track.id}


def _check_no_overlap(clips):
    previous_end = -1
    for clip in sorted(clips, key=lambda c: c.timeline_start_ms):
        if clip.timeline_start_ms < previous_end:
            raise ValueError('I segmenti della stessa traccia non possono sovrapporsi')
        previous_end = clip.timeline_start_ms + clip.duration_ms


def _decode_span(source, begin, end, rate, channels, destination):
    # Decode before trimming. Sample counts are checked by the caller, including
    # inputs whose metadata claims a longer duration than their actual audio.
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
        'stream=channels', '-of', 'json', str(source)], capture_output=True, text=True, check=True, timeout=120)
    source_channels = int(json.loads(probe.stdout)['streams'][0]['channels'])
    normalize = ',pan=stereo|c0=c0|c1=c0' if channels == 2 and source_channels == 1 else ''
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(source),
        '-map', '0:a:0', '-af', f'atrim=start={begin / 1000:.6f}:end={end / 1000:.6f},asetpts=PTS-STARTPTS{normalize}',
        '-ar', str(rate), '-ac', str(channels), '-c:a', 'pcm_f32le', '-f', 'f32le', str(destination)],
        check=True, capture_output=True, timeout=1800)



def _pack_join_source(project, track, clips):
    """Pack unchanged clip PCM so discontinuous source spans become contiguous.

    Mixer, track delay, pitch and tempo remain track parameters and are never
    baked twice. Timeline positions and clips outside the joined pair survive.
    """
    channels = max(1, track.channels or 2)
    if channels > 2:
        raise ValueError('Per unire segmenti usa sorgenti mono o stereo')
    source = _source(project, track.filename)
    name, path, handle = _create_output(project)
    offset_ms = offset_frames = 0
    with handle, tempfile.TemporaryDirectory(prefix='mta-timeline-join-') as tmp:
        with sf.SoundFile(handle, 'w', samplerate=project.sample_rate, channels=channels,
                          format='WAV', subtype='FLOAT', closefd=False) as output:
            for index, clip in enumerate(clips):
                raw = Path(tmp) / f'{index}.f32'
                duration_ms = clip.duration_ms
                _decode_span(source, clip.source_start_ms, clip.source_end_ms,
                             project.sample_rate, channels, raw)
                wanted = round((offset_ms + duration_ms) * project.sample_rate / 1000) - offset_frames
                actual = raw.stat().st_size // (4 * channels)
                if abs(actual - wanted) > max(2, round(project.sample_rate / 1000)):
                    raise ValueError('Intervallo oltre la fine della sorgente audio')
                remaining = wanted
                with raw.open('rb') as data:
                    while remaining > 0:
                        chunk = data.read(min(remaining, 65536) * 4 * channels)
                        if not chunk:
                            break
                        frames = np.frombuffer(chunk, dtype='<f4').reshape(-1, channels)
                        if not np.isfinite(frames).all():
                            raise ValueError('La sorgente contiene campioni non validi')
                        output.write(frames)
                        remaining -= len(frames)
                if remaining > 0:
                    output.write(np.zeros((remaining, channels), dtype='float32'))
                clip.source_start_ms = offset_ms
                offset_ms += duration_ms
                offset_frames += wanted
                clip.source_end_ms = offset_ms
                raw.unlink()
            output.flush()
        _sync(handle, path)
    track.filename = name
    track.source_clip_id = None
    track.duration_ms = round(offset_frames * 1000 / project.sample_rate)
    track.channels = channels
    track.channel_layout = 'stereo' if channels == 2 else 'mono'
    track.sample_rate = project.sample_rate
    track.waveform_peaks = waveform_peaks(path, 4096)
    track.waveform_revision = ''
    _retain(project, track)


def join(project, req, capacity_check=None):
    """Join exactly two adjacent audio clips without changing audible timing."""
    require_kind(project, 'audio')
    track = next((t for t in project.tracks if t.id == req.track_id), None)
    if track is None or track.kind != 'audio':
        raise ValueError('Seleziona due segmenti audio della stessa traccia')
    ensure_clips(track)
    selected = []
    for part in req.parts:
        clip = next((c for c in track.clips if c.id == part.clip_id), None)
        if (clip is None or part.track_id != track.id
                or (part.filename is not None and part.filename != track.filename)
                or (clip.source_start_ms, clip.source_end_ms) != (part.source_start_ms, part.source_end_ms)
                or (part.expected_start_ms is not None
                    and clip.timeline_start_ms + track.delay_ms != part.expected_start_ms)):
            raise ValueError('Il segmento è cambiato; ripeti la selezione')
        selected.append(clip)
    selected.sort(key=lambda c: c.timeline_start_ms)
    left, right = selected
    if left.id == right.id or min(left.duration_ms, right.duration_ms) <= 0:
        raise ValueError('Seleziona due segmenti distinti e non vuoti')
    if left.timeline_start_ms + left.duration_ms != right.timeline_start_ms:
        raise ValueError('I due segmenti devono essere adiacenti nella timeline')
    _check_no_overlap(track.clips)
    clips = sorted((c.model_copy(deep=True) for c in track.clips), key=lambda c: c.timeline_start_ms)
    selected_ids = {left.id, right.id}
    from .audio_engine import media_duration_ms
    duration = media_duration_ms(_source(project, track.filename))
    if any(c.source_end_ms > duration + 1 for c in clips):
        raise ValueError('Intervallo oltre la fine della sorgente audio')
    needs_source = left.source_end_ms != right.source_start_ms
    packed = sum(c.duration_ms for c in clips)
    if len(clips) > 10000 or (needs_source and packed > LIMIT_MS):
        raise ValueError('Sorgente risultante troppo lunga')
    if capacity_check and needs_source:
        capacity_check(project.owner_user_id, int(packed * project.sample_rate / 1000) * max(1, track.channels or 2) * 8 + 65536)
    ai_upload_transaction.begin(project.id)
    try:
        _retain(project, track)
        if needs_source:
            _pack_join_source(project, track, clips)
        left, right = [c for c in clips if c.id in selected_ids]
        merged = left.model_copy(update={'id': uuid.uuid4().hex[:12], 'source_end_ms': right.source_end_ms})
        track.clips = sorted([c for c in clips if c.id not in selected_ids] + [merged], key=lambda c: c.timeline_start_ms)
        track.clips_initialized = True
        storage.save_project(project)
    except BaseException:
        ai_upload_transaction.reconcile(project.id)
        raise
    ai_upload_transaction.finish(project.id)
    return {'project': project, 'track_id': track.id, 'clip_ids': [merged.id], 'changed_track_ids': [track.id]}


def transfer(project, req, capacity_check=None):
    target = next((t for t in project.tracks if t.id == req.destination_track_id), None)
    if target is None or target.kind != 'audio':
        raise ValueError('Scegli una traccia audio di destinazione')
    require_kind(project, 'audio')
    ensure_clips(target)
    known = {x.filename for x in [*project.tracks, *project.clip_library]}
    moving = set()
    incoming = []
    channels = max(1, target.channels or 2)
    for part in req.parts:
        origin = next((t for t in project.tracks if t.id == part.track_id), None)
        if origin and origin.kind != 'audio':
            raise ValueError('I segmenti MIDI richiedono l’editor MIDI')
        name = part.filename or (origin.filename if origin else None)
        if name not in known:
            raise ValueError('Il file sorgente non appartiene al progetto')
        if part.source_end_ms <= part.source_start_ms:
            raise ValueError('Intervallo sorgente non valido')
        _source(project, name)
        if req.action == 'move':
            if origin is None or origin.filename != name or not part.clip_id:
                raise ValueError('Il segmento da spostare non esiste più')
            ensure_clips(origin)
            original = next((c for c in origin.clips if c.id == part.clip_id), None)
            identity = (origin.id, part.clip_id)
            if identity in moving or original is None or (original.source_start_ms, original.source_end_ms) != (part.source_start_ms, part.source_end_ms):
                raise ValueError('Il segmento è cambiato; ripeti lo spostamento')
            if part.expected_start_ms is not None and original.timeline_start_ms + origin.delay_ms != part.expected_start_ms:
                raise ValueError('Il segmento è cambiato; ripeti lo spostamento')
            moving.add(identity)
        raw_start = req.start_ms + part.offset_ms - target.delay_ms
        if raw_start < 0 or raw_start + part.source_end_ms - part.source_start_ms > LIMIT_MS:
            raise ValueError('Il segmento è fuori dalla timeline')
        clip = Clip(id=uuid.uuid4().hex[:12], source_start_ms=part.source_start_ms,
                    source_end_ms=part.source_end_ms, timeline_start_ms=raw_start)
        incoming.append((name, clip))
        asset = next((x for x in [*project.tracks, *project.clip_library] if x.filename == name), None)
        channels = max(channels, getattr(asset, 'channels', 0) or 2)
    if channels > 2:
        raise ValueError('Per trasferire segmenti usa sorgenti mono o stereo')
    existing = [c.model_copy(deep=True) for c in target.clips if (target.id, c.id) not in moving]
    planned = [*existing, *(c for _, c in incoming)]
    _check_no_overlap(planned)
    if len(planned) > 10000:
        raise ValueError('Troppi segmenti sulla traccia')
    packed = sum(c.duration_ms for c in planned)
    if packed > LIMIT_MS:
        raise ValueError('Sorgente risultante troppo lunga')
    needs_source = any(name != target.filename for name, _ in incoming)
    if capacity_check and needs_source:
        capacity_check(project.owner_user_id, int(packed * project.sample_rate / 1000) * channels * 8 + 65536)
    # No source files are changed in place. The upload journal removes only newly
    # owned files on failure; persisted projects retain every referenced source.
    ai_upload_transaction.begin(project.id)
    try:
        _retain(project, target)
        for track in project.tracks:
            if any(tid == track.id for tid, _ in moving):
                _retain(project, track)
        if needs_source:
            name, path, handle = _create_output(project)
            offset_frames = 0
            offset_ms = 0
            with handle, tempfile.TemporaryDirectory(prefix='mta-timeline-') as tmp:
                with sf.SoundFile(handle, 'w', samplerate=project.sample_rate, channels=channels,
                                  format='WAV', subtype='FLOAT', closefd=False) as output:
                    for index, (source_name, clip) in enumerate([*((target.filename, c) for c in existing), *incoming]):
                        raw = Path(tmp) / f'{index}.f32'
                        _decode_span(_source(project, source_name), clip.source_start_ms, clip.source_end_ms,
                                     project.sample_rate, channels, raw)
                        duration_ms = clip.duration_ms
                        wanted = round((offset_ms + duration_ms) * project.sample_rate / 1000) - offset_frames
                        actual = raw.stat().st_size // (4 * channels)
                        if abs(actual - wanted) > max(2, round(project.sample_rate / 1000)):
                            raise ValueError('Intervallo oltre la fine della sorgente audio')
                        remaining = wanted
                        with raw.open('rb') as data:
                            while remaining > 0:
                                chunk = data.read(min(remaining, 65536) * 4 * channels)
                                if not chunk:
                                    break
                                frames = np.frombuffer(chunk, dtype='<f4').reshape(-1, channels)
                                output.write(frames)
                                remaining -= len(frames)
                        if remaining > 0:
                            output.write(np.zeros((remaining, channels), dtype='float32'))
                        clip.source_start_ms = offset_ms
                        offset_ms += duration_ms
                        offset_frames += wanted
                        clip.source_end_ms = offset_ms
                        raw.unlink()
                    output.flush()
                _sync(handle, path)
            target.filename = name
            target.source_clip_id = None
            target.duration_ms = round(offset_frames * 1000 / project.sample_rate)
            target.channels = channels
            target.channel_layout = 'stereo' if channels == 2 else 'mono'
            target.sample_rate = project.sample_rate
            target.waveform_peaks = waveform_peaks(path, 4096)
            target.waveform_revision = ''
            _retain(project, target)
        else:
            # A same-source transfer must still reject out-of-bounds ranges.
            from .audio_engine import media_duration_ms
            duration = media_duration_ms(_source(project, target.filename))
            if any(c.source_end_ms > duration + 1 for _, c in incoming):
                raise ValueError('Intervallo oltre la fine della sorgente audio')
        for track in project.tracks:
            if any(tid == track.id for tid, _ in moving):
                track.clips = [c for c in track.clips if (track.id, c.id) not in moving]
                track.clips_initialized = True
        target.clips = sorted(planned, key=lambda c: c.timeline_start_ms)
        target.clips_initialized = True
        _check_no_overlap(target.clips)
        storage.save_project(project)
    except BaseException:
        ai_upload_transaction.reconcile(project.id)
        raise
    ai_upload_transaction.finish(project.id)
    return {'project': project, 'track_id': target.id,
            'clip_ids': [c.id for _, c in incoming], 'changed_track_ids': list({target.id, *(x[0] for x in moving)})}
