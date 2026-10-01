from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

TrackType = Literal["drums", "bass", "guitars", "keyboards", "orchestra", "winds", "melody", "click", "choirs", "other"]
PluginType = Literal[
    "eq", "normalizer", "compressor", "limiter", "delay", "reverb_lexicon",
    "room_ambience", "graphic_eq_32", "amplify", "stereo_imager",
    "maximizer_loudness", "mastering_wizard", "denoise", "crackle_cleaner"
]


class Clip(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    source_start_ms: int = Field(default=0, ge=0)
    source_end_ms: int = Field(ge=0)
    timeline_start_ms: int = Field(default=0, ge=0)

    @property
    def duration_ms(self) -> int:
        return max(0, self.source_end_ms - self.source_start_ms)


class InsertPlugin(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    plugin: PluginType
    preset: str = Field(default="default", max_length=80)
    enabled: bool = True
    params: dict[str, float | int | str | bool] = Field(default_factory=dict)


class CustomPresetRequest(BaseModel):
    plugin: PluginType
    name: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}$")
    params: dict[str, float | int | str | bool] = Field(default_factory=dict)


class AutoMixRequest(BaseModel):
    enabled: bool
    style: Literal["balanced", "live", "studio", "gentle"] = "balanced"


class AutoMixTrackSnapshot(BaseModel):
    volume_db: float
    pan: float
    inserts: list[InsertPlugin] = Field(default_factory=list)


class AutoMixSnapshot(BaseModel):
    tracks: dict[str, AutoMixTrackSnapshot] = Field(default_factory=dict)
    master_volume_db: float = 0.0
    master_inserts: list[InsertPlugin] = Field(default_factory=list)


class Track(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(max_length=200)
    type: TrackType = "other"
    filename: str = Field(min_length=1, max_length=128)
    duration_ms: int = Field(default=0, ge=0)
    volume_db: float = Field(default=0.0, ge=-120.0, le=24.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    mute: bool = False
    solo: bool = False
    color: str = Field(default="#2f81f7", pattern=r"^#[0-9A-Fa-f]{6}$")
    clips: list[Clip] = Field(default_factory=list)
    inserts: list[InsertPlugin] = Field(default_factory=list, max_length=16)


class Marker(BaseModel):
    time_ms: int = Field(ge=0)
    label: str = Field(max_length=500)


class LyricLine(BaseModel):
    time_ms: int = Field(ge=0)
    text: str = Field(max_length=4000)


class Chord(BaseModel):
    time_ms: int = Field(ge=0)
    chord: str = Field(max_length=200)


class DeleteRangeRequest(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    track_ids: list[str] | None = None
    ripple: bool = False


class MoveTrackRequest(BaseModel):
    offset_ms: int = Field(ge=-86_400_000, le=86_400_000)


class AddInsertRequest(BaseModel):
    plugin: PluginType
    preset: str = Field(default="default", max_length=80)


class ReorderInsertRequest(BaseModel):
    ordered_ids: list[str] = Field(max_length=16)


class StemSplitRequest(BaseModel):
    target: Literal["MTA8", "MTA16", "existing"] = "existing"
    project_id: str | None = None
    model: str = Field(default="htdemucs", max_length=80)


class MtaSlotMapping(BaseModel):
    slot: int = Field(ge=1, le=16)
    name: str = Field(max_length=200)
    type: TrackType = "other"
    track_ids: list[str] = Field(min_length=1)


class MtaExportRequest(BaseModel):
    slots: list[MtaSlotMapping] = Field(default_factory=list, max_length=16)


class Project(BaseModel):
    id: str
    owner_user_id: int | None = Field(default=None, ge=1)
    shared_with_user_ids: list[int] = Field(default_factory=list)
    title: str = Field(max_length=200)
    artist: str = Field(default="", max_length=200)
    bpm: float = Field(default=120.0, gt=0, le=500)
    key: str = Field(default="", max_length=40)
    target: Literal["MTA8", "MTA16"] = "MTA8"
    tracks: list[Track] = Field(default_factory=list)
    markers: list[Marker] = Field(default_factory=list)
    lyrics: list[LyricLine] = Field(default_factory=list)
    chords: list[Chord] = Field(default_factory=list)
    preserved_attachments: list[str] = Field(default_factory=list)
    master_volume_db: float = Field(default=0.0, ge=-120.0, le=24.0)
    master_inserts: list[InsertPlugin] = Field(default_factory=list, max_length=16)
    auto_mix_enabled: bool = False
    auto_mix_style: Literal["balanced", "live", "studio", "gentle"] = "balanced"
    auto_mix_snapshot: AutoMixSnapshot | None = None

    @field_validator("shared_with_user_ids")
    @classmethod
    def unique_shared_users(cls, values: list[int]) -> list[int]:
        return sorted(set(values))

    @field_validator("preserved_attachments")
    @classmethod
    def attachments_must_be_local(cls, values: list[str]) -> list[str]:
        for value in values:
            if not value or Path(value).name != value or value in {".", ".."}:
                raise ValueError("attachment names must be local basenames")
        return values
