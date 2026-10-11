"""AI Arranger: validated, non-destructive project-to-model request planning.

No generation is claimed unless a separately installed backend is actually running.
This module is intentionally dependency-free and does not import GPU inference libraries.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator

from .models import Project

AIModelId = Literal['ace-step-1.5', 'diffrhythm-2']
Scope = Literal['project', 'tracks', 'range']
RemixMode = Literal['instrument_swap', 'auto_remix']


PRESETS = {
    'jazz-swing': {'en': 'Jazz / Swing', 'it': 'Jazz / Swing', 'prompt': 'Piano trio, walking double bass and swinging acoustic drums'},
    'orchestral': {'en': 'Orchestral', 'it': 'Orchestrale', 'prompt': 'Symphonic strings, woodwinds, brass and cinematic percussion'},
    'synthwave': {'en': '1980s Synthwave', 'it': 'Synthwave anni 80', 'prompt': 'Analog synthesizers, gated snare and retro electronic bass'},
    'bossa-nova': {'en': 'Bossa nova', 'it': 'Bossa nova', 'prompt': 'Nylon guitar, soft syncopated percussion and acoustic bass'},
    'unplugged': {'en': 'Acoustic / Unplugged', 'it': 'Acustico / Unplugged', 'prompt': 'Acoustic guitar, warm piano and sparse acoustic percussion'},
    'rock': {'en': 'Rock', 'it': 'Rock', 'prompt': 'Electric guitars, live drums and electric bass'},
    'lofi': {'en': 'Lo-fi', 'it': 'Lo-fi', 'prompt': 'Soft dusty drums, mellow keys and warm tape ambience'},
    'dance': {'en': 'Electronic Dance', 'it': 'Dance elettronica', 'prompt': 'Four on the floor rhythm, synth bass and layered electronic textures'},
}

MODELS = {
    'ace-step-1.5': {'name': 'ACE-Step 1.5', 'license': 'MIT (upstream claim; verify third-party dependencies)', 'available': False,
                     'reference': 'https://github.com/ace-step/ACE-Step-1.5'},
    'diffrhythm-2': {'name': 'DiffRhythm 2', 'license': 'Apache-2.0 (upstream code and weights)', 'available': False,
                     'reference': 'https://github.com/xiaomi-research/diffrhythm2'},
}


class RearrangeRequest(BaseModel):
    model_id: AIModelId = 'ace-step-1.5'
    preset_id: str = Field(default='jazz-swing', max_length=64)
    prompt: str = Field(default='', max_length=3000)
    scope: Scope = 'project'
    track_ids: list[str] = Field(default_factory=list, max_length=128)
    start_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    end_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    strength: int = Field(default=60, ge=0, le=100)
    preserve_voice: bool = False
    preserve_melody: bool = True
    preserve_chords: bool = True
    preserve_structure: bool = True
    preserve_tempo: bool = True
    separate_stems: bool = False

    @model_validator(mode='after')
    def validate_scope(self):
        if self.preset_id not in PRESETS:
            raise ValueError('unknown arranger preset')
        if self.scope == 'range' and (self.start_ms is None or self.end_ms is None or self.start_ms >= self.end_ms):
            raise ValueError('range needs start_ms < end_ms')
        if self.scope == 'tracks' and not self.track_ids:
            raise ValueError('track selection cannot be empty')
        if len(self.track_ids) != len(set(self.track_ids)):
            raise ValueError('duplicate track id')
        if self.scope != 'range' and (self.start_ms is not None or self.end_ms is not None):
            raise ValueError('range boundaries are only valid for range scope')
        if self.scope != 'tracks' and self.track_ids:
            raise ValueError('track ids are only valid for tracks scope')
        return self


class InstrumentSwap(BaseModel):
    """One existing source track replaced by a requested target instrument."""
    track_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    target_instrument: str = Field(min_length=2, max_length=100)
    instructions: str = Field(default='', max_length=1000)
    preserve_performance: bool = True


class RemixRequest(RearrangeRequest):
    mode: RemixMode = 'auto_remix'
    instrument_swaps: list[InstrumentSwap] = Field(default_factory=list, max_length=32)
    # Preserve the other RearrangeRequest constraints and defaults.

    @model_validator(mode='after')
    def validate_remix(self):
        if self.mode == 'instrument_swap' and not self.instrument_swaps:
            raise ValueError('instrument_swap needs at least one instrument replacement')
        if self.mode == 'auto_remix' and self.instrument_swaps:
            raise ValueError('instrument replacements are only valid in instrument_swap mode')
        ids = [swap.track_id for swap in self.instrument_swaps]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate instrument replacement source')
        if self.mode == 'auto_remix' and not self.prompt.strip() and self.preset_id not in PRESETS:
            raise ValueError('auto_remix needs a style')
        return self


def prepare_remix_plan(project: Project, request: RemixRequest) -> dict:
    """Plan a non-destructive remix; generation is not claimed or simulated."""
    plan = prepare_plan(project, request)
    tracks = {track.id: track for track in project.tracks}
    swaps = []
    for swap in request.instrument_swaps:
        track = tracks.get(swap.track_id)
        if track is None:
            raise ValueError('unknown instrument source track')
        if request.scope == 'tracks' and swap.track_id not in request.track_ids:
            raise ValueError('instrument source is outside the selected tracks')
        swaps.append({'source_track_id': track.id, 'source_track_name': track.name,
                      'source_track_type': track.type, 'target_instrument': swap.target_instrument,
                      'instructions': swap.instructions, 'preserve_performance': swap.preserve_performance})
    plan['schema'] = 'mta.ai_remix.plan.v1'
    plan['operation'] = 'remix'
    plan['mode'] = request.mode
    plan['instrument_swaps'] = swaps
    if request.mode == 'instrument_swap':
        plan['prompt'] += '\nReplace ONLY the requested instruments; keep unrelated tracks unchanged.'
        for swap in swaps:
            plan['prompt'] += f"\nReplace {swap['source_track_name']} ({swap['source_track_type']}) with {swap['target_instrument']}."
            if swap['preserve_performance']:
                plan['prompt'] += ' Preserve phrasing, timing and performance where feasible.'
            if swap['instructions']:
                plan['prompt'] += ' ' + swap['instructions']
    else:
        plan['prompt'] += '\nCreate a coherent new remix arrangement in the requested style.'
    plan['warnings'].append('Instrument identity and musical fidelity require backend generation and post-generation verification.')
    return plan


def catalog() -> dict:
    return {'models': [{'id': key, **value} for key, value in MODELS.items()],
            'presets': [{'id': key, **value} for key, value in PRESETS.items()],
            'generation_available': False, 'native_host_ready': False, 'operations': ['rearrange', 'remix'], 'remix_modes': ['instrument_swap', 'auto_remix']}


def prepare_plan(project: Project, request: RearrangeRequest) -> dict:
    """Prepare immutable model input; never mutate project data or claim strict guarantees."""
    selected_tracks = {track.id for track in project.tracks}
    if request.scope == 'tracks' and not set(request.track_ids).issubset(selected_tracks):
        raise ValueError('unknown track id')
    sections = [
        {'time_ms': marker.time_ms, 'end_ms': marker.end_ms, 'label': marker.label}
        for marker in sorted(project.markers, key=lambda item: item.time_ms)
        if not marker.disabled and not marker.deleted
    ] if request.preserve_structure else []
    chord_events = [
        {'time_ms': item.time_ms, 'end_ms': item.end_ms, 'chord': item.chord}
        for item in sorted(project.chords, key=lambda chord: chord.time_ms)
        if not item.excluded
    ] if request.preserve_chords else []
    parts = [PRESETS[request.preset_id]['prompt']]
    if request.prompt.strip():
        parts.append(request.prompt.strip())
    if request.preserve_chords:
        parts.append('Preserve the supplied chord progression and harmonic rhythm where feasible.')
    if request.preserve_structure:
        parts.append('Preserve the supplied section order, boundaries and duration where feasible.')
    if request.preserve_melody:
        parts.append('Retain the recognizable main melody where feasible.')
    if request.preserve_voice:
        parts.append('Keep original vocals isolated and unchanged; do not synthesize an imitation of the singer.')
    if request.preserve_tempo:
        parts.append(f'Maintain approximately {project.bpm:g} BPM and {project.time_signature} meter.')
    return {
        'schema': 'mta.ai_arranger.plan.v1', 'project_id': project.id,
        'model_id': request.model_id, 'preset_id': request.preset_id,
        'prompt': '\n'.join(parts), 'strength': request.strength,
        'scope': request.scope, 'track_ids': request.track_ids,
        'start_ms': request.start_ms, 'end_ms': request.end_ms,
        'constraints': {
            'preserve_voice': request.preserve_voice,
            'preserve_melody': request.preserve_melody,
            'preserve_chords': request.preserve_chords,
            'preserve_structure': request.preserve_structure,
            'preserve_tempo': request.preserve_tempo,
            'separate_stems': request.separate_stems,
        },
        'musical_context': {'bpm': project.bpm, 'meter': project.time_signature,
                            'key': project.key, 'sections': sections, 'chords': chord_events},
        'status': 'ready_for_backend', 'backend_available': False,
        'guarantees': {'chords': False, 'structure': False, 'melody': False},
        'warnings': [
            'No AI generator is bundled or enabled; this endpoint only prepares the request.',
            'Text-based preservation is best-effort until musical verification and regeneration are implemented.',
            'Generated audio must be imported as separate non-destructive tracks after explicit approval.',
        ],
    }
