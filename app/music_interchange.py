"""Versioned musical interchange shared by transcription and vocal planning."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

from .models import MusicPart  # noqa: F401 -- public shared schema


class MusicResult(BaseModel):
    protocol: Literal['mta-music-1'] = 'mta-music-1'
    parts: list[MusicPart] = Field(min_length=1, max_length=64)
    alternatives: list[MusicPart] = Field(default_factory=list, max_length=128)
    offset_ms: float = Field(default=0, ge=0, le=86400000, allow_inf_nan=False)
    warnings: list[str] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def musical_budget(self):
        if len({p.id for p in [*self.parts, *self.alternatives]}) != len(self.parts)+len(self.alternatives):
            raise ValueError('Duplicate musical part identifier')
        if any(not p.notes and not p.controls for p in self.parts):
            raise ValueError('Empty/fictitious musical parts are not accepted')
        if sum(2*len(p.notes)+len(p.controls) for p in [*self.parts, *self.alternatives]) > 150000:
            raise ValueError('Musical result exceeds expanded event budget')
        if any(n.start_ms+n.duration_ms+self.offset_ms > 86400000 for p in [*self.parts, *self.alternatives] for n in p.notes):
            raise ValueError('Musical result exceeds 24 hours')
        if any(c.time_ms+self.offset_ms > 86400000 for p in [*self.parts, *self.alternatives] for c in p.controls):
            raise ValueError('Musical control exceeds 24 hours')
        if any(len({n.id for n in p.notes}) != len(p.notes) for p in [*self.parts, *self.alternatives]):
            raise ValueError('Duplicate note identifier within a musical part')
        return self


class EmptyTranscription(MusicResult):
    """Explicit successful inference with no detected notes; no placeholder parts."""
    parts: list[MusicPart] = Field(default_factory=list, max_length=0)
    empty_reason: Literal['no-notes'] = 'no-notes'

    @model_validator(mode='after')
    def no_alternatives(self):
        if self.alternatives:
            raise ValueError('Empty transcription cannot hide musical alternatives')
        return self


def no_notes(warnings=None):
    return EmptyTranscription(warnings=warnings or ['The model detected no notes; no MIDI parts were created.'])


def parse_result(data):
    """Decode the bounded no-notes extension without weakening score imports."""
    import json
    value=json.loads(data) if isinstance(data,(str,bytes)) else data
    if isinstance(value,dict) and value.get('empty_reason')=='no-notes':
        return EmptyTranscription.model_validate(value)
    return MusicResult.model_validate(value)
