"""SMF 0/1/2 with independent type-2 patterns and rational SMPTE timing.

All imported event times are source milliseconds; project BPM is never changed.
"""
import bisect
from collections import defaultdict, deque
from fractions import Fraction
import io
import math

from .models import MidiNote, MidiControl, MidiSysEx

MAX_EVENTS = 150000
MAX_MS = 86400000


def division_rate(division):
    if type(division) is not int or division == 0 or not -32768 <= division <= 32767:
        raise ValueError('MIDI: invalid time division')
    if division > 0:
        return None
    code = ((division & 65535) >> 8) - 256
    ticks = division & 255
    if code not in (-24, -25, -29, -30) or not ticks:
        raise ValueError('MIDI: invalid SMPTE frame rate or ticks per frame')
    return (Fraction(30000, 1001) if code == -29 else Fraction(-code)) * ticks


class TempoIndex:
    def __init__(self, division, changes):
        self.division = division
        self.rate = division_rate(division)
        self.ticks = [0]
        self.times = [Fraction(0)]
        self.tempos = [500000]
        for tick, tempo in sorted(changes, key=lambda item: item[0]):
            if not 1 <= tempo <= 16777215:
                raise ValueError('MIDI: invalid tempo')
            if tick == self.ticks[-1]:
                self.tempos[-1] = tempo
            else:
                self.times.append(self.to_ms(tick))
                self.ticks.append(tick)
                self.tempos.append(tempo)

    def to_ms(self, tick):
        if self.rate:
            return Fraction(tick * 1000, self.rate)
        index = bisect.bisect_right(self.ticks, tick) - 1
        return self.times[index] + Fraction((tick - self.ticks[index]) * self.tempos[index], self.division * 1000)

    def to_tick(self, milliseconds):
        ms = Fraction(str(milliseconds))
        if self.rate:
            return round(ms * self.rate / 1000)
        index = bisect.bisect_right(self.times, ms) - 1
        return round(self.ticks[index] + (ms - self.times[index]) * self.division * 1000 / self.tempos[index])


def read_parts(data):
    import mido
    from .models import MidiMeta
    if len(data) > 8 * 1024 * 1024 or not data.startswith(b'MThd'):
        raise ValueError('MIDI: expected an SMF file of at most 8 MiB')
    midi = mido.MidiFile(file=io.BytesIO(data))
    division_rate(midi.ticks_per_beat)
    if midi.type not in (0, 1, 2) or not 1 <= len(midi.tracks) <= 256:
        raise ValueError('MIDI: invalid file type or track count')
    tracks = []
    total = 0
    for track in midi.tracks:
        tick = 0
        messages = []
        for message in track:
            total += 1
            if total > MAX_EVENTS or message.time < 0:
                raise ValueError('MIDI: too many events or invalid delta time')
            tick += message.time
            messages.append((tick, message))
        tracks.append(messages)
    source_ratio = 1.
    ratio_markers = [message.text for track in tracks for _, message in track if message.type == 'marker' and message.text.startswith('MTA-MUSICAL-RATIO:')] if midi.type != 2 else []
    if ratio_markers:
        try:
            ratios = {float(value.split(':', 1)[1]) for value in ratio_markers}
            if len(ratios) != 1 or not all(math.isfinite(r) and .25 <= r <= 4 for r in ratios):
                raise ValueError
            source_ratio = ratios.pop()
        except (ValueError, OverflowError) as exc:
            raise ValueError('MIDI: invalid MTA musical time ratio') from exc
    shared_changes = [(tick, message.tempo) for track in tracks for tick, message in track if message.type == 'set_tempo']
    result = []
    total_sysex = 0
    expanded = 0
    for index, messages in enumerate(tracks):
        changes = [(tick, message.tempo) for tick, message in messages if message.type == 'set_tempo'] if midi.type == 2 else shared_changes
        clock = TempoIndex(midi.ticks_per_beat, changes)
        notes, controls, sysex, metadata = [], [], [], []
        active = defaultdict(deque)
        now = 0
        name = ''
        for tick, message in messages:
            now = float(clock.to_ms(tick))*source_ratio
            if not math.isfinite(now) or now > MAX_MS:
                raise ValueError('MIDI: duration exceeds 24 hours')
            if message.is_meta:
                if message.type != 'end_of_track':
                    values = message.dict()
                    values.pop('time', None)
                    if values.get('type') == 'set_tempo':values['tempo'] = round(values['tempo']*source_ratio)
                    metadata.append(MidiMeta(time_ms=now, message=values))
                if message.type == 'track_name':
                    name = message.name
            elif message.type == 'note_on' and message.velocity:
                active[(message.channel, message.note)].append((now, message.velocity))
            elif message.type == 'note_off' or (message.type == 'note_on' and not message.velocity):
                pending = active[(message.channel, message.note)]
                if pending:
                    start, velocity = pending.popleft()
                    notes.append(MidiNote(start_ms=start, duration_ms=max(.01, now-start), pitch=message.note, velocity=velocity, channel=message.channel))
            elif message.type == 'sysex':
                packet = message.bytes()
                total_sysex += len(packet)
                if len(packet) > 65536 or len(sysex) >= 1024 or total_sysex > 8 * 1024**2:
                    raise ValueError('MIDI SysEx exceeds project limits')
                sysex.append(MidiSysEx(time_ms=now, data=packet))
            elif message.type in ('control_change', 'program_change', 'pitchwheel', 'aftertouch', 'polytouch'):
                controls.append(MidiControl(time_ms=now, data=message.bytes()))
        for (channel, pitch), pending in active.items():
            for start, velocity in pending:
                notes.append(MidiNote(start_ms=start, duration_ms=max(1, now-start), pitch=pitch, velocity=velocity, channel=channel))
        if len(notes) > 50000 or len(controls) > 100000:
            raise ValueError('MIDI: event limit exceeded')
        # Global tempo/signature events in a conductor track accompany each
        # independently editable part. Type 2 never borrows another pattern's map.
        if midi.type != 2:
            for other_index, other in enumerate(tracks):
                if other_index == index:
                    continue
                for tick, message in other:
                    if message.type in ('set_tempo', 'time_signature', 'key_signature', 'smpte_offset') or (message.type == 'marker' and message.text.startswith(('MTA-MUSICAL-ORIGIN:', 'MTA-MUSICAL-RATIO:'))):
                        values = message.dict()
                        values.pop('time', None)
                        if values.get('type') == 'set_tempo':values['tempo'] = round(values['tempo']*source_ratio)
                        metadata.append(MidiMeta(time_ms=float(clock.to_ms(tick))*source_ratio, message=values))
        expanded += len(notes)*2+len(controls)+len(sysex)+len(metadata)
        if expanded>MAX_EVENTS or len(metadata)>10000:raise ValueError('MIDI: expanded metadata/event limit exceeded')
        if notes or controls or sysex:
            result.append({'name': name[:200] or f'MIDI {index+1}', 'notes': notes, 'controls': controls,
                           'sysex': sysex, 'midi_meta': metadata, 'midi_smf_type': midi.type,
                           'midi_division': midi.ticks_per_beat,
                           'duration_ms': max(1000, math.ceil(now), math.ceil(max((n.start_ms+n.duration_ms for n in notes), default=0)))})
    if not result:
        raise ValueError('MIDI: no musical parts')
    return result


def meta_message(values):
    import mido
    values = dict(values)
    kind = values.pop('type')
    values.pop('time', None)
    if kind == 'unknown_meta':
        return mido.UnknownMetaMessage(**values)
    return mido.MetaMessage(kind, **values)


def write_parts(tracks, *, file_type=1, division=960, bpm=120, time_signature='4/4', project=None, time_domain='audible'):
    import mido
    from .midi import events, chase
    tracks = list(tracks)
    if file_type not in (0, 1, 2) or not 1 <= len(tracks) <= 64:
        raise ValueError('MIDI: select 1–64 parts and SMF type 0, 1 or 2')
    division_rate(division)
    if not math.isfinite(bpm) or not 20 <= bpm <= 400:
        raise ValueError('MIDI: invalid BPM')
    tempo = mido.bpm2tempo(bpm)
    numerator, denominator = map(int, time_signature.split('/'))
    midi = mido.MidiFile(type=file_type, ticks_per_beat=division)
    conductor = [(0, mido.MetaMessage('set_tempo', tempo=tempo)),
                 (0, mido.MetaMessage('time_signature', numerator=numerator, denominator=denominator))]
    if time_domain not in ('source', 'audible'):
        raise ValueError('MIDI time domain must be source or audible')
    export_ratio = 1.
    project_clock = None
    if project is not None and file_type != 2:
        from .musical_clock import MusicalClock
        musical = MusicalClock(project)
        project_data = project.model_dump() if hasattr(project, 'model_dump') else project
        if time_domain == 'audible':
            export_ratio = max(.25, min(4., float(project_data.get('bpm') or 120)/float(project_data.get('base_bpm') or project_data.get('bpm') or 120)))
        at_zero = musical.sections[max(0, bisect.bisect_right(musical.times, 0)-1)]
        tempo = mido.bpm2tempo(at_zero['quarter_bpm']*export_ratio)
        project_clock = TempoIndex(division, [(0, tempo)])
        conductor = [(0, mido.MetaMessage('set_tempo', tempo=tempo)),
                     (0, mido.MetaMessage('time_signature', numerator=at_zero['n'], denominator=at_zero['d']))]
        for piece in musical.sections:
            if piece['at'] <= 0:
                continue
            tick = project_clock.to_tick(piece['at']/export_ratio)
            next_tempo = mido.bpm2tempo(piece['quarter_bpm']*export_ratio)
            conductor.extend([(tick, mido.MetaMessage('set_tempo', tempo=next_tempo)),
                              (tick, mido.MetaMessage('time_signature', numerator=piece['n'], denominator=piece['d']))])
            project_clock = TempoIndex(division, list(zip(project_clock.ticks, project_clock.tempos, strict=True)) + [(tick, next_tempo)])
        # Absolute note times are retained; the origin marker permits lossless
        # re-import without adding the project start for a second time.
        conductor.append((project_clock.to_tick(max(0, musical.origin)/export_ratio),
                          mido.MetaMessage('marker', text=f'MTA-MUSICAL-ORIGIN:{musical.origin:g}')))
        conductor.append((0, mido.MetaMessage('marker', text=f'MTA-MUSICAL-RATIO:{export_ratio:g}')))
    total = 0
    prepared = []
    for track in tracks:
        if track.midi_ump:
            raise ValueError('MIDI 2 events require lossless UMP JSON export')
        seq = events(track, timeline=True, ump=False)
        seq = [(0, message) for message in chase(seq, 0)] + [(ms, message) for ms, message in seq if ms >= 0]
        # Independent type-2 source patterns retain their own tempo/signature.
        # Simultaneous exports use one conductor map, preserving absolute timing.
        metas = [(item.time_ms, meta_message(item.message)) for item in track.midi_meta
                 if file_type == 2 or item.message.get('type') not in ('set_tempo', 'time_signature', 'smpte_offset')]
        if project is not None and file_type != 2:
            metas = [(ms, message) for ms, message in metas if not (message.type == 'marker' and message.text.startswith(('MTA-MUSICAL-ORIGIN:', 'MTA-MUSICAL-RATIO:')))]
        tempos = [(ms, message.tempo) for ms, message in metas if message.type == 'set_tempo']
        clock = project_clock or TempoIndex(division, [(0, tempo)])
        if file_type == 2:
            # Reconstruct ticks from millisecond tempo changes incrementally.
            for ms, value in sorted(tempos):
                tick = clock.to_tick(ms)
                clock = TempoIndex(division, list(zip(clock.ticks, clock.tempos, strict=True)) + [(tick, value)])
        values = [(clock.to_tick(ms/export_ratio), mido.Message.from_bytes(message)) for ms, message in seq]
        values += [(clock.to_tick(ms/export_ratio), message) for ms, message in metas]
        if not any(message.type == 'track_name' for _, message in values):
            values.insert(0, (0, mido.MetaMessage('track_name', name=track.name)))
        if file_type == 2:
            for _, message in conductor:
                if not any(candidate.type == message.type for _, candidate in values):
                    values.insert(0, (0, message.copy()))
        total += len(values)
        if total > MAX_EVENTS:
            raise ValueError('MIDI: export event limit exceeded')
        prepared.append(values)
    if file_type == 0:
        prepared = [[*conductor, *(item for part in prepared for item in part)]]
    elif file_type == 1:
        prepared.insert(0, conductor)
    for sequence in prepared:
        part = mido.MidiTrack()
        midi.tracks.append(part)
        last = 0
        for tick, message in sorted(sequence, key=lambda item: (item[0], 0 if item[1].is_meta else 1)):
            if tick < last or tick > 0x0fffffff:
                raise ValueError('MIDI: time exceeds SMF tick range')
            part.append(message.copy(time=tick-last))
            last = tick
        part.append(mido.MetaMessage('end_of_track', time=0))
    output = io.BytesIO()
    midi.save(file=output)
    if output.tell() > 8 * 1024**2:
        raise ValueError('MIDI: export exceeds 8 MiB')
    return output.getvalue()
