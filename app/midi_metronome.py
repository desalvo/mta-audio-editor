"""Linked MIDI click tracks use exactly the project's audible pulse grid."""
import hashlib
import json
import math

from .models import MidiNote, Clip


def beats(project, duration):
    from .audio_engine import zoned_metronome_beats
    from .metronome_grid import grid_settings
    from .timeline_editing import preroll_beats
    bpm, signature = grid_settings(project)
    if project.metronome_mode == 'adaptive':
        values = [round(point.time_ms) for point in project.adaptive_tempo_map]
    elif project.metronome_mode == 'zones':
        markers = [m for m in project.markers if not m.disabled and not m.deleted and 0 < m.time_ms < duration]
        markers.sort(key=lambda m: m.time_ms)
        boundaries = [(0, 'START'), *((m.time_ms, m.id) for m in markers), (duration, 'END')]
        from .metronome_grid import manual_signature
        zone_bpms = {}
        signatures = {}
        for left, right in zip(boundaries, boundaries[1:]):
            key = f'{left[1]}|{right[1]}'
            candidates = [v for k, v in project.metronome_manual_zone_bpms.items() if k.split('|')[0] == left[1] or k.split('|')[-1] == right[1]]
            zone_bpms[str(left[0])] = project.metronome_manual_zone_bpms.get(key, candidates[0] if len(candidates) == 1 else project.metronome_zone_bpms.get(str(left[0]), bpm))
            signatures[left[0]] = manual_signature(project, left[1], right[1]) or project.metronome_zone_signatures.get(str(left[0]), signature)
        values = zoned_metronome_beats(project, duration, zone_bpms)
    else:
        from .musical_clock import project_origin
        from .metronome_grid import source_grid_settings
        bpm, signature = source_grid_settings(project)
        start = project_origin(project.model_dump())
        end = min(duration, project.metronome_stop_ms or duration)
        count = max(0, math.ceil((end-start)*bpm/60000))
        if count > 50000:
            raise ValueError('MIDI metronome exceeds 50000 notes')
        values = [round(start + i*60000/bpm) for i in range(count)]
    if project.metronome_mode != 'fixed':
        values = preroll_beats(project, values)
    if project.metronome_mode != 'fixed':
        values = [at + project.metronome_shift_ms for at in values]
    if len(values) > 50000:
        raise ValueError('MIDI metronome exceeds 50000 notes')
    result = []
    index = 0
    markers = sorted(m.time_ms for m in project.markers if not m.disabled and not m.deleted and 0 < m.time_ms < duration) if project.metronome_mode == 'zones' else []
    zone = 0
    active_signature = signature
    for at in values:
        if at < 0 or at >= duration or (project.metronome_stop_ms is not None and at >= project.metronome_stop_ms):
            continue
        while zone < len(markers) and at >= markers[zone]:
            zone += 1
            index = 0
        if project.metronome_mode == 'zones':
            active_signature = signatures.get(markers[zone-1] if zone else 0, signature)
        numerator, denominator = map(int, active_signature.split('/'))
        pos = index % numerator
        result.append((at, 'accent' if pos == 0 else 'secondary' if denominator == 8 and numerator in (6, 9, 12) and pos % 3 == 0 else 'beat'))
        index += 1
    return result


def refresh(project):
    targets = [t for t in project.tracks if t.kind == 'midi' and t.midi_metronome is not None]
    if not targets:
        return
    project.tempo_known = True
    if project.musical_origin_ms is None:
        project.musical_origin_ms = project.metronome_start_ms
    from .audio_engine import project_duration_ms
    target_ids = {t.id for t in targets}
    other = project.model_copy(update={'tracks': [t for t in project.tracks if t.id not in target_ids]})
    duration = max(1000, project_duration_ms(other), max((t.duration_ms for t in targets), default=0) if not other.tracks else 0)
    from .vst3_transport import settings
    data = {**settings(project), 'duration': duration, 'start': project.metronome_start_ms, 'stop': project.metronome_stop_ms,
            'insertion': project.metronome_insertion_ms, 'pre_roll': project.metronome_pre_roll_bars}
    grid = None
    for track in targets:
        config = track.midi_metronome
        revision = hashlib.sha256(json.dumps({**data, 'config': config.model_dump()}, sort_keys=True).encode()).hexdigest()
        if track.midi_metronome_revision == revision:
            continue
        if grid is None:
            grid = beats(project, duration)
        track.midi_notes = [MidiNote(id=f'click-{i}', start_ms=at, duration_ms=min(config.gate_ms, max(.01, duration-at)),
                                    pitch=getattr(config, kind+'_note'), velocity=getattr(config, kind+'_velocity'), channel=config.channel)
                            for i, (at, kind) in enumerate(grid)]
        track.duration_ms = duration
        track.clips = [Clip(id='midi-click', source_end_ms=duration)]
        track.clips_initialized = True
        track.midi_metronome_revision = revision
