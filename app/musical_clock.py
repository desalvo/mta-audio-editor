"""Project musical position in source milliseconds, independent of audio stretching.

BPM counts the audible denominator pulse. Four divisions per pulse and 960
MIDI ticks per quarter are explicit; bar 1 starts at the musical project origin.
"""
import bisect
import math
import re


def _manual(data, name, left, right, fallback):
    values = data.get(name, {})
    key = f'{left}|{right}'
    if key in values:
        return values[key]
    matches = [v for k, v in values.items() if k.split('|')[0] == left or k.split('|')[-1] == right]
    return matches[0] if len(matches) == 1 else fallback


def project_origin(data):
    explicit = data.get('musical_origin_ms')
    if explicit is not None:
        return float(explicit) + float(data.get('metronome_shift_ms', 0))
    if data.get('metronome_pre_roll_bars'):
        return float(data.get('metronome_start_ms', 0)) + float(data.get('metronome_shift_ms', 0))
    if data.get('metronome_mode') == 'adaptive' and data.get('adaptive_tempo_map') and not data.get('metronome_grid_origin_ms'):
        return float(min(p['time_ms'] for p in data['adaptive_tempo_map'])) + float(data.get('metronome_shift_ms', 0))
    return float(data.get('metronome_grid_origin_ms', 0)) + float(data.get('metronome_shift_ms', 0))


class MusicalClock:
    def __init__(self, data):
        if hasattr(data, 'model_dump'):
            data = data.model_dump()
        self.origin = project_origin(data)
        ratio = max(.25, min(4., float(data.get('bpm') or 120)/float(data.get('base_bpm') or data.get('bpm') or 120)))
        audible_bpm = float(data.get('metronome_bpm') or data.get('bpm') or 120)
        bpm = audible_bpm/ratio
        meter = data.get('metronome_time_signature') or data.get('time_signature') or '4/4'
        mode = data.get('metronome_mode', 'fixed')
        points = [(0., bpm, meter, False)]
        if mode == 'zones':
            marks = sorted((m for m in data.get('markers', []) if not m.get('disabled') and not m.get('deleted') and m['time_ms'] > 0), key=lambda m: m['time_ms'])
            bounds = [(0, 'START')] + [(m['time_ms'], m['id']) for m in marks] + [(86400000, 'END')]
            points = []
            for (at, left), (_, right) in zip(bounds, bounds[1:]):
                tempo = _manual(data, 'metronome_manual_zone_bpms', left, right, data.get('metronome_zone_bpms', {}).get(str(at), audible_bpm))
                signature = _manual(data, 'metronome_manual_zone_signatures', left, right, data.get('metronome_zone_signatures', {}).get(str(at), meter))
                points.append((float(at), float(tempo)/ratio, signature, True))
        elif mode == 'adaptive' and data.get('adaptive_tempo_map'):
            shift = float(data.get('metronome_shift_ms', 0))
            raw = sorted(data['adaptive_tempo_map'], key=lambda p: p['time_ms'])
            points = []
            for i, item in enumerate(raw):
                tempo = float(item['bpm'])
                if i + 1 < len(raw):
                    dt = raw[i+1]['time_ms'] - item['time_ms']
                    beats = raw[i+1]['beat_index'] - item['beat_index']
                    if dt > 0 and beats > 0:
                        tempo = 60000 * beats / dt
                points.append((float(item['time_ms']) + shift, tempo, data.get('time_signature') or '4/4', False))
            # Pre-roll is generated at project BPM, not the first analyzed interval.
            if self.origin < points[0][0]:
                points.insert(0, (self.origin, bpm, meter, False))
        points = sorted({p[0]: p for p in points}.values())
        active = points[max(0, bisect.bisect_right([p[0] for p in points], self.origin)-1)]
        if not any(p[0] == self.origin for p in points):
            points.append((self.origin, active[1], active[2], True))
            points.sort()
        self.sections = []
        previous = None
        quarter = 0.
        for at, tempo, signature, rephase in points:
            n, d = map(int, signature.split('/'))
            if not math.isfinite(tempo) or tempo <= 0 or n < 1 or d not in (4, 8):
                raise ValueError('Invalid project musical tempo map')
            if previous:
                quarter += (at-previous['at']) * previous['quarter_bpm'] / 60000
            item = {'at': at, 'bpm': tempo, 'quarter_bpm': tempo*4/d, 'n': n, 'd': d, 'q': quarter, 'rephase': rephase}
            self.sections.append(item)
            previous = item
        self.times = [p['at'] for p in self.sections]
        offset = self._quarter(self.origin)
        for p in self.sections:
            p['q'] -= offset
        self.quarters = [p['q'] for p in self.sections]
        self.anchors = []
        previous = None
        for p in self.sections:
            if previous is None or p['at'] == self.origin or p['rephase'] or p['n'] != previous['n'] or p['d'] != previous['d']:
                self.anchors.append({**p, 'bar': 1})
            previous = p
        origin_index = next(i for i, p in enumerate(self.anchors) if p['at'] == self.origin)
        for i in range(origin_index+1, len(self.anchors)):
            a, b = self.anchors[i-1:i+1]
            b['bar'] = a['bar'] + max(1, math.ceil((b['q']-a['q'])/(a['n']*4/a['d'])-1e-9))
        for i in range(origin_index-1, -1, -1):
            a, b = self.anchors[i:i+2]
            a['bar'] = b['bar'] - max(1, math.ceil((b['q']-a['q'])/(a['n']*4/a['d'])-1e-9))
        self.anchor_times = [p['at'] for p in self.anchors]

    def _quarter(self, ms):
        p = self.sections[max(0, bisect.bisect_right(self.times, ms)-1)]
        return p['q'] + (ms-p['at'])*p['quarter_bpm']/60000

    def quarter_at(self, ms):
        return self._quarter(ms)

    def time_at_quarter(self, quarter):
        p = self.sections[max(0, bisect.bisect_right(self.quarters, quarter)-1)]
        return p['at'] + (quarter-p['q'])*60000/p['quarter_bpm']

    def position(self, ms):
        q = math.floor(self.quarter_at(ms)*960+.5)/960
        at = self.time_at_quarter(q)
        anchor = self.anchors[max(0, bisect.bisect_right(self.anchor_times, at+1e-8)-1)]
        pulses = (q-anchor['q'])*anchor['d']/4
        bar_delta = math.floor((pulses+1e-8)/anchor['n'])
        within = max(0., pulses-bar_delta*anchor['n'])
        beat = math.floor(within+1e-8)
        ticks_per_division = 960//anchor['d']
        subticks = round((within-beat)*ticks_per_division*4)
        division, tick = divmod(subticks, ticks_per_division)
        if division == 4:
            division = 0
            beat += 1
        if beat == anchor['n']:
            beat = 0
            bar_delta += 1
        return {'bar': anchor['bar']+bar_delta, 'beat': beat+1, 'division': division+1, 'tick': tick}

    def format(self, ms):
        p = self.position(ms)
        return f"{p['bar']}:{p['beat']}:{p['division']}:{p['tick']:03d}"

    def parse(self, text):
        match = re.fullmatch(r'\s*(-?\d+)\s*:\s*(\d+(?:\.\d+)?)\s*(?::\s*(\d+)\s*:\s*(\d{1,3}))?\s*', str(text))
        if not match:
            raise ValueError('Use Bar:Beat:Division:Ticks')
        bar, beat = int(match[1]), float(match[2])
        a = next((p for p in reversed(self.anchors) if p['bar'] <= bar), self.anchors[0])
        division, ticks = (int(match[3]), int(match[4])) if match[3] else (1, 0)
        if not 1 <= beat < a['n']+1 or not 1 <= division <= 4 or not 0 <= ticks < 960//a['d'] or (match[3] and beat != int(beat)):
            raise ValueError('Musical position is outside the current meter')
        q = a['q'] + ((bar-a['bar'])*a['n'] + beat-1 + (division-1)/4)*4/a['d'] + ticks/960
        result = self.time_at_quarter(q)
        if self.position(result)['bar'] != bar:
            raise ValueError('Musical position falls inside a truncated zone bar')
        return result
