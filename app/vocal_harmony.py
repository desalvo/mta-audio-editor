"""Model-independent, editable vocal voicings; no synthetic audio or fake singer."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from .models import MidiNote
from .music_interchange import MusicPart, MusicResult

ROOTS = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}


class HarmonySettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    voices: int = Field(default=4, ge=2, le=8)
    style: Literal['satb'] = 'satb'
    key: str = Field(default='C', max_length=20)
    ranges: list[tuple[int, int]] = Field(default_factory=list, max_length=8)
    retain_melody: bool = True


def pitch_classes(text):
    text = str(text).strip().replace('♭', 'b').replace('♯', '#')
    match = re.fullmatch(r'([A-G])([#b]?)([^/]*)(?:/[A-G][#b]?)?', text)
    if not match:
        raise ValueError('Unsupported chord/key symbol: ' + text[:40])
    root = (ROOTS[match[1]] + (1 if match[2] == '#' else -1 if match[2] == 'b' else 0)) % 12
    suffix = match[3].strip().removeprefix(':')
    aliases = {'major':'', 'maj':'', 'M':'', 'minor':'m', 'min':'m', 'min7':'m7',
               'M7':'maj7', '+':'aug', 'o':'dim', 'o7':'dim7', 'sus':'sus4'}
    suffix = aliases.get(suffix, suffix)
    intervals = {'':[0,4,7], 'm':[0,3,7], '7':[0,4,7,10], 'maj7':[0,4,7,11], 'm7':[0,3,7,10],
                 'dim':[0,3,6], 'dim7':[0,3,6,9], 'ø7':[0,3,6,10], 'aug':[0,4,8],
                 'sus2':[0,2,7], 'sus4':[0,5,7], '6':[0,4,7,9], 'm6':[0,3,7,9]}
    if suffix not in intervals:
        raise ValueError('Unsupported chord quality; edit it before automatic harmony: '+text[:40])
    degrees = intervals[suffix]
    minor = suffix in {'m','m7','m6','dim','dim7','ø7'}
    return root, {(root + value) % 12 for value in degrees}, minor


def arrange(notes, chords, settings):
    cfg = HarmonySettings.model_validate(settings)
    notes = sorted((MidiNote.model_validate(n) for n in notes), key=lambda n: (n.start_ms, -n.pitch))
    if not notes:
        raise ValueError('Choose a non-empty MIDI melody')
    # Polyphonic inputs remain editable; one explicit upper melody is used for
    # automatic voicing rather than pretending one singer can sing a chord.
    melody = []
    for note in notes:
        if melody and note.start_ms < melody[-1].start_ms+melody[-1].duration_ms:
            continue
        melody.append(note)
    root, _, minor = pitch_classes(cfg.key)
    scale = {(root+i) % 12 for i in ([0, 2, 3, 5, 7, 8, 10] if minor else [0, 2, 4, 5, 7, 9, 11])}
    ranges = cfg.ranges or ([(40, 60), (48, 67), (55, 74), (60, 84)] if cfg.voices == 4 else [(40+round(i*20/(cfg.voices-1)), 64+round(i*20/(cfg.voices-1))) for i in range(cfg.voices)])
    if len(ranges) != cfg.voices or any(not 0 <= low < high <= 127 for low, high in ranges):
        raise ValueError('Configure a valid range for each voice')
    parts = [[] for _ in ranges]
    previous = None
    active_chords = [c for c in chords if not c.deleted and not c.excluded]
    for source in melody:
        choices = [c for c in active_chords if c.time_ms <= source.start_ms and (c.end_ms is None or source.start_ms < c.end_ms)]
        confirmed = [c for c in choices if c.manual_override]
        chord = max(confirmed or choices, key=lambda c: c.time_ms) if choices else None
        classes = pitch_classes(chord.chord)[1] if chord else scale
        candidate_sets = [[n for n in range(low, high+1) if n % 12 in classes] for low, high in ranges]
        if cfg.retain_melody:
            low, high = ranges[-1]
            if not low <= source.pitch <= high:
                raise ValueError('Melody exceeds the highest voice range; adjust ranges or disable retained melody')
            candidate_sets[-1] = [source.pitch]
        # Preserve a feasible upper continuation before beam pruning. Otherwise
        # eight-voice searches can fill all beam slots with prefixes that leave
        # no room for the retained melody, despite valid lower voicings.
        ceiling = 128
        for voice in range(len(ranges)-1, -1, -1):
            candidate_sets[voice] = [n for n in candidate_sets[voice] if n < ceiling]
            if not candidate_sets[voice]:
                raise ValueError('Voice ranges cannot produce a non-crossing harmony for this melody')
            ceiling = max(candidate_sets[voice])
        states = [(0., [])]
        for voice, (low, high) in enumerate(ranges):
            candidates = candidate_sets[voice]
            expanded = []
            for cost, pitches in states:
                for pitch in candidates:
                    if pitches and pitch <= pitches[-1]:
                        continue
                    target = previous[voice] if previous else (low+high)/2
                    score = cost+abs(pitch-target)+(max(0, abs(pitch-target)-7)*2 if previous else 0)
                    if previous and pitches:
                        for index, other in enumerate(pitches):
                            if abs(pitch-other) % 12 in (0, 7) and abs(previous[voice]-previous[index]) % 12 == abs(pitch-other) % 12:
                                if (pitch-previous[voice])*(other-previous[index]) > 0:
                                    score += 8
                    expanded.append((score, [*pitches, pitch]))
            if not expanded:
                raise ValueError('Voice ranges cannot produce a non-crossing harmony for this melody')
            states = sorted(expanded, key=lambda s: (s[0], s[1]))[:32]
        pitches = states[0][1]
        for voice, pitch in enumerate(pitches):
            parts[voice].append(source.model_copy(update={'id': f'voice-{voice}-{len(parts[voice])}', 'pitch': pitch, 'channel': voice,
                                                         'origin': 'generated', 'source_model': 'mta-voice-leading-1',
                                                         'confidence': None, 'confidence_metric': ''}))
        previous = pitches
    labels = ['Bass', 'Tenor', 'Alto', 'Soprano'] if cfg.voices == 4 and cfg.style == 'satb' else [f'Voice {i+1}' for i in range(cfg.voices)]
    return MusicResult(parts=[MusicPart(id=f'voice-{i}', name=labels[i], instrument='voice', notes=part, source_model='mta-voice-leading-1') for i, part in enumerate(parts)],
                       warnings=['Automatic harmony uses the upper non-overlapping melody; review voice leading before synthesis.'] if len(melody) != len(notes) else [])
