"""Non-destructive timeline edits shared by authenticated project endpoints."""
import math
import tempfile
from pathlib import Path

from .models import Project
from .audio_engine import ensure_clips, project_duration_ms, render_mix


def unique_track_name(project, name):
    base = str(name).strip()[:190] or 'Stem'
    names = {t.name.casefold() for t in project.tracks}
    value, number = base, 2
    while value.casefold() in names:
        value = f'{base} {number}'
        number += 1
    return value


def validate_new_overlaps(old, new):
    previous = {t.id: t for t in old.tracks}
    for track in new.tracks:
        old_clips = {c.id: c.model_dump() for c in previous.get(track.id, track).clips} if track.id in previous else {}
        clips = sorted((c for c in track.clips if c.duration_ms), key=lambda c: c.timeline_start_ms)
        for i, left in enumerate(clips):
            for right in clips[i+1:]:
                if right.timeline_start_ms >= left.timeline_start_ms + left.duration_ms:
                    break
                # Preserve legacy overlapping projects, but never introduce or move overlaps.
                if (old_clips.get(left.id) != left.model_dump() or old_clips.get(right.id) != right.model_dump()):
                    raise ValueError('Segments on the same track cannot overlap')


def retime(value, delta, upper=None):
    if isinstance(value, list):
        return [retime(item, delta, upper) for item in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, item in value.items():
        if key in {'time_ms', 'start_ms', 'end_ms', 'anchor_line_time_ms', 'anchor_lyric_time_ms'} and isinstance(item, (int, float)):
            out[key] = max(0, item + delta)
            if upper is not None:
                out[key] = min(upper, out[key])
        else:
            out[key] = retime(item, delta, upper)
    return out


def shift_project(project, delta):
    project = project.model_copy(deep=True)
    for track in [*project.tracks, *project.archived_tracks]:
        ensure_clips(track)
        for clip in track.clips:
            clip.timeline_start_ms += delta
    data = project.model_dump()
    for field in ('lyrics', 'chords', 'markers', 'adaptive_tempo_map'):
        data[field] = retime(data.get(field, []), delta)
    for field in ('metronome_start_ms', 'metronome_stop_ms', 'metronome_insertion_ms', 'metronome_grid_origin_ms', 'musical_origin_ms', 'timeline_end_ms'):
        if data.get(field) is not None:
            data[field] += delta
    data['metronome_zone_bpms'] = {str(int(k)+delta) if str(k).isdigit() else k: v for k, v in data.get('metronome_zone_bpms', {}).items()}
    data['metronome_zone_signatures'] = {str(int(k)+delta) if str(k).isdigit() else k: v for k, v in data.get('metronome_zone_signatures', {}).items()}
    return Project.model_validate(data)


def prepare_metronome_insert(project, start, bars):
    if isinstance(start, bool) or not isinstance(start, int) or not 0 <= start <= 86400000:
        raise ValueError('Invalid insertion time')
    if isinstance(bars, bool) or not isinstance(bars, int) or not 0 <= bars <= 64:
        raise ValueError('Pre-roll must be between 0 and 64 bars')
    from .metronome_grid import source_grid_settings
    bpm, signature = source_grid_settings(project)
    beats = int(signature.split('/')[0])
    pre = round(bars * beats * 60000 / bpm)
    extra = max(0, pre-start)
    if project_duration_ms(project)+extra > 86400000 or start+extra > 86400000:
        raise ValueError('Project duration exceeds 24 hours')
    project = shift_project(project, extra) if extra else project.model_copy(deep=True)
    if start+extra >= project_duration_ms(project):
        project.timeline_end_ms = min(86400000, start+extra+round(beats*60000/bpm))
    project.metronome_start_ms = start+extra-pre
    project.metronome_insertion_ms = start+extra
    project.metronome_pre_roll_bars = bars
    project.metronome_grid_origin_ms = project.metronome_start_ms
    project.musical_origin_ms = project.metronome_start_ms
    for t in project.tracks:
        if t.type == 'click':
            t.delay_ms = 0
    return project, extra


def preroll_beats(project, beats):
    if not project.metronome_pre_roll_bars:
        return beats
    from .metronome_grid import source_grid_settings
    bpm, signature = source_grid_settings(project)
    count = project.metronome_pre_roll_bars * int(signature.split('/')[0])
    interval = 60000/bpm
    return [round(project.metronome_insertion_ms-(count-i)*interval) for i in range(count)] + [b for b in beats if b >= project.metronome_insertion_ms]


def trim_project(project, left, right):
    if left < 0 or right <= left:
        raise ValueError('Invalid trim interval')
    for track in [*project.tracks, *project.archived_tracks]:
        ensure_clips(track)
        kept = []
        for clip in track.clips:
            start = clip.timeline_start_ms+track.delay_ms
            lo, hi = max(left, start), min(right, start+clip.duration_ms)
            if hi <= lo:
                continue
            source = clip.source_start_ms+lo-start
            kept.append(clip.model_copy(update={'source_start_ms': source, 'source_end_ms': source+hi-lo, 'timeline_start_ms': lo-left}))
        track.clips, track.delay_ms, track.clips_initialized = kept, 0, True
    data = project.model_dump()
    for field in ('lyrics', 'chords', 'markers', 'adaptive_tempo_map'):
        events = [e for e in data.get(field, []) if (e.get('end_ms') if e.get('end_ms') is not None else e.get('time_ms', 0)) >= left and e.get('time_ms', 0) <= right]
        data[field] = retime(events, -left, right-left)
    for field in ('metronome_start_ms', 'metronome_stop_ms', 'metronome_insertion_ms', 'metronome_grid_origin_ms', 'musical_origin_ms'):
        if data.get(field) is not None:
            data[field] = max(0, min(right-left, data[field]-left))
    data['metronome_zone_bpms'] = {str(max(0, int(k)-left)) if str(k).isdigit() else k: v for k, v in data.get('metronome_zone_bpms', {}).items()}
    data['metronome_zone_signatures'] = {str(max(0, int(k)-left)) if str(k).isdigit() else k: v for k, v in data.get('metronome_zone_signatures', {}).items()}
    data['timeline_end_ms'] = right-left
    return Project.model_validate(data)


def audible_bounds(project, resolver):
    import numpy as np
    import soundfile as sf
    dry = project.model_copy(deep=True)
    dry.master_fade_enabled, dry.master_volume_db, dry.master_inserts = False, 0, []
    dry.bpm, dry.pitch_semitones = dry.base_bpm or dry.bpm, 0
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)/'bounds.wav'
        render_mix(dry, resolver, out, fmt='wav', wav_bit_depth=32)
        first = last = None
        offset = 0
        with sf.SoundFile(out) as f:
            rate = f.samplerate
            for block in f.blocks(blocksize=65536, dtype='float32', always_2d=True):
                indices = np.flatnonzero(np.max(np.abs(block), axis=1) > 1e-6)
                if indices.size:
                    if first is None:
                        first = offset+int(indices[0])
                    last = offset+int(indices[-1])+1
                offset += len(block)
    if first is None:
        raise ValueError('No audible audio to trim')
    return math.floor(first*1000/rate), math.ceil(last*1000/rate)
