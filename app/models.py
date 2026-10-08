from pathlib import Path
from typing import Any, Literal

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


class ProjectClip(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(max_length=200)
    filename: str = Field(min_length=1, max_length=128)
    duration_ms: int = Field(default=0, ge=0)
    type: TrackType = "other"
    channels: int = Field(default=0, ge=0, le=32)
    channel_layout: str = Field(default="", max_length=64)
    format: str = Field(default="", max_length=160)
    bitrate_bps: int = Field(default=0, ge=0)
    sample_rate: Literal[44100, 48000, 96000] = 44100
    size_bytes: int = Field(default=0, ge=0)
    provenance: str = Field(default="Audio del progetto", max_length=500)
    current_location: str = Field(default="", max_length=512)
    embedded_metadata: dict[str, str] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=4000)
    metadata_scanned: bool = False


class InstantiateProjectClipRequest(BaseModel):
    timeline_start_ms: int = Field(default=0, ge=0, le=86_400_000)


class UpdateProjectClipRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)


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
    mta_slot: int | None = Field(default=None, ge=1, le=16)
    filename: str = Field(min_length=1, max_length=128)
    source_clip_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    duration_ms: int = Field(default=0, ge=0)
    volume_db: float = Field(default=0.0, ge=-120.0, le=24.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    mute: bool = False
    solo: bool = False
    color: str = Field(default="#2f81f7", pattern=r"^#[0-9A-Fa-f]{6}$")
    clips: list[Clip] = Field(default_factory=list)
    inserts: list[InsertPlugin] = Field(default_factory=list, max_length=16)
    waveform_peaks: list[float] = Field(default_factory=list, max_length=8192)
    waveform_revision: str = Field(default="", max_length=128)
    channels: int = Field(default=0, ge=0, le=32)
    channel_layout: str = Field(default="", max_length=64)
    sample_rate: Literal[44100, 48000, 96000] = 44100
    delay_ms: int = Field(default=0, ge=-86_400_000, le=86_400_000)
    height_px: int = Field(default=78, ge=78, le=420)


class Marker(BaseModel):
    time_ms: int = Field(ge=0)
    label: str = Field(max_length=500)
    color: str = Field(default="#204A87", pattern=r"^#[0-9A-Fa-f]{6}$")
    # Optional document-layout settings for the section starting at this marker.
    # The value is expressed in millimetres so it maps directly to print layout.
    section_indent_enabled: bool = False
    section_indent_mm: float = Field(default=0.0, ge=0.0, le=100.0)
    disabled: bool = False
    deleted: bool = False
    manual_override: bool = False
    source_snapshot: dict[str, Any] | None = None


class LyricSyllable(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str = Field(max_length=120)


class LyricWord(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    text: str = Field(max_length=500)
    syllables: list[LyricSyllable] = Field(default_factory=list, max_length=64)


class LyricLine(BaseModel):
    time_ms: int = Field(ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    text: str = Field(max_length=4000)
    words: list[LyricWord] = Field(default_factory=list, max_length=500)
    disabled: bool = False
    deleted: bool = False
    manual_override: bool = False
    source_snapshot: dict[str, Any] | None = None


class Chord(BaseModel):
    time_ms: int = Field(ge=0)
    chord: str = Field(max_length=200)
    # Optional manual layout override used by the joint Lyrics + Chords editor.
    # Playback timing remains time_ms; these fields affect document/layout placement only.
    anchor_line_time_ms: int | None = Field(default=None, ge=0)
    anchor_word_index: int | None = Field(default=None, ge=0)
    anchor_word_text: str = Field(default="", max_length=500)
    # r183 granular layout anchors: start/end of line, word/syllable offset, and
    # stable ordering for chord sequences sharing the same anchor.
    anchor_kind: Literal["start", "word", "end"] = "word"
    anchor_syllable_index: int | None = Field(default=None, ge=0)
    # Optional character offset inside anchor_word_text for words without reliable syllable timing.
    anchor_char_offset: int | None = Field(default=None, ge=0)
    anchor_order: int = Field(default=0, ge=0)
    manual_anchor: bool = False
    # Joint Lyrics + Chords editor can hide a detected chord without deleting the
    # source analysis event. Excluded chords are ignored by playback, documents and
    # synchronized MTA export events, while remaining recoverable in the project.
    excluded: bool = False
    deleted: bool = False
    manual_override: bool = False
    source_snapshot: dict[str, Any] | None = None


class PdfTextStyle(BaseModel):
    style: Literal["normal", "bold", "italic"] = "normal"
    size: float = Field(default=11.0, ge=6.0, le=48.0)
    color: str = Field(default="#111111", pattern=r"^#[0-9A-Fa-f]{6}$")


class LyricsPdfStyle(BaseModel):
    title: PdfTextStyle = Field(default_factory=lambda: PdfTextStyle(style="bold", size=18, color="#111111"))
    subtitle: PdfTextStyle = Field(default_factory=lambda: PdfTextStyle(style="normal", size=11, color="#333333"))
    bpm: PdfTextStyle = Field(default_factory=lambda: PdfTextStyle(style="normal", size=11, color="#333333"))
    lyrics: PdfTextStyle = Field(default_factory=lambda: PdfTextStyle(style="normal", size=11, color="#111111"))
    chords: PdfTextStyle = Field(default_factory=lambda: PdfTextStyle(style="bold", size=9, color="#7B1FA2"))
    markers: PdfTextStyle = Field(default_factory=lambda: PdfTextStyle(style="bold", size=12, color="#204A87"))
    line_spacing: float = Field(default=8.0, ge=0.0, le=48.0)
    marker_section_spacing: float = Field(default=10.0, ge=0.0, le=72.0)


class RightsRecord(BaseModel):
    uid: str = Field(min_length=1, max_length=160)
    society: str = Field(min_length=1, max_length=80)
    title: str = Field(default="", max_length=300)
    original_title: str = Field(default="", max_length=300)
    authors: list[str] = Field(default_factory=list, max_length=64)
    performers: list[str] = Field(default_factory=list, max_length=64)
    publishers: list[str] = Field(default_factory=list, max_length=64)
    identifiers: dict[str, str] = Field(default_factory=dict)
    source_url: str = Field(default="", max_length=2048)


class DeleteRangeRequest(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    track_ids: list[str] | None = None
    ripple: bool = False




class SampleEditorRequest(BaseModel):
    action: Literal["copy", "cut", "remove", "paste", "process"]
    start_sample: int = Field(default=0, ge=0)
    end_sample: int = Field(default=0, ge=0)
    insert_sample: int = Field(default=0, ge=0)
    processor: Literal["pitch", "autotune", "normalizer", "maximizer", "eq32"] | None = None
    params: dict[str, float | int | str | bool | list[float]] = Field(default_factory=dict)
    preview: bool = False

class MoveTrackRequest(BaseModel):
    offset_ms: int = Field(ge=-86_400_000, le=86_400_000)


class TrackDelayRequest(BaseModel):
    delay_ms: int = Field(ge=-86_400_000, le=86_400_000)


class AddInsertRequest(BaseModel):
    plugin: PluginType
    preset: str = Field(default="default", max_length=80)


class ReorderInsertRequest(BaseModel):
    ordered_ids: list[str] = Field(max_length=16)


class StemSplitRequest(BaseModel):
    target: Literal["MTA8", "MTA16", "DAW", "existing"] = "existing"
    project_id: str | None = None
    model: str = Field(default="htdemucs", max_length=80)


class MtaSlotMapping(BaseModel):
    slot: int = Field(ge=1, le=16)
    name: str = Field(max_length=200)
    type: TrackType = "other"
    track_ids: list[str] = Field(min_length=1)


class MtaExportRequest(BaseModel):
    slots: list[MtaSlotMapping] = Field(default_factory=list, max_length=16)


class TrackExportRequest(BaseModel):
    format: Literal["wav", "mp3", "flac"] = "wav"
    mp3_bitrate_kbps: int = Field(default=320, ge=96, le=320)
    sample_rate: Literal[44100, 48000, 96000] = 44100
    wav_bit_depth: Literal[16, 24, 32] = 24
    flac_compression: int = Field(default=8, ge=0, le=12)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=32)


class ProjectExportRequest(BaseModel):
    format: Literal["mta", "wav", "mp3", "mlive_mp3", "mp3g", "flac", "mp4"] = "mta"
    filename: str = Field(default="project", min_length=1, max_length=240)
    mta_target: Literal["MTA8", "MTA16"] | None = None
    mta_device_profile: Literal["auto", "merish5_xynthia2", "bbeat_divo", "mlive_mta16_default", "merish5_plus_mta16", "generic"] = "auto" 
    mp3_bitrate_kbps: int = Field(default=320, ge=96, le=320)
    sample_rate: Literal[44100, 48000, 96000] = 44100
    wav_bit_depth: Literal[16, 24, 32] = 24
    flac_compression: int = Field(default=8, ge=0, le=12)
    normalize_audio: bool = False
    normalize_peak_db: float = Field(default=-1.0, ge=-30.0, le=0.0)
    karaoke_resolution: Literal["1280x720", "1920x1080"] = "1920x1080"
    karaoke_chords: bool = True
    karaoke_background: str | None = Field(default=None, max_length=180)
    slots: list[MtaSlotMapping] = Field(default_factory=list, max_length=16)
    output_path: str | None = Field(default=None, max_length=4096)


class SampleEditRequest(BaseModel):
    action: Literal["copy", "cut", "delete", "paste"]
    start_sample: int = Field(default=0, ge=0)
    end_sample: int = Field(default=0, ge=0)
    cursor_sample: int = Field(default=0, ge=0)


class SampleEffectRequest(BaseModel):
    effect: Literal["pitch", "autotune", "normalizer", "maximizer", "eq32"]
    start_sample: int = Field(default=0, ge=0)
    end_sample: int = Field(default=0, ge=0)
    preset: str = Field(default="default", max_length=80)
    params: dict[str, float | str | bool | list[float]] = Field(default_factory=dict)




class AdaptiveTempoPoint(BaseModel):
    time_ms: int = Field(ge=0)
    bpm: float = Field(gt=0, le=500)
    beat_index: int = Field(ge=0)

class Project(BaseModel):
    id: str
    owner_user_id: int | None = Field(default=None, ge=1)
    shared_with_user_ids: list[int] = Field(default_factory=list)
    title: str = Field(max_length=200)
    artist: str = Field(default="", max_length=200)
    original_title: str = Field(default="", max_length=300)
    authors: list[str] = Field(default_factory=list, max_length=64)
    bpm: float = Field(default=120.0, gt=0, le=500)
    time_signature: str = Field(default="4/4", pattern=r"^(?:2/4|3/4|4/4|5/4|6/8|7/8|9/8|12/8)$")
    key: str = Field(default="", max_length=40)
    target: Literal["MTA8", "MTA16", "DAW"] = "MTA8"
    sample_rate: Literal[44100, 48000, 96000] = 44100
    mta_device_profile: Literal["auto", "merish5_xynthia2", "bbeat_divo", "mlive_mta16_default", "merish5_plus_mta16", "generic"] = "auto"
    tracks: list[Track] = Field(default_factory=list)
    clip_library: list[ProjectClip] = Field(default_factory=list, max_length=512)
    markers: list[Marker] = Field(default_factory=list)
    lyrics: list[LyricLine] = Field(default_factory=list)
    chords: list[Chord] = Field(default_factory=list)
    lyrics_pdf_style: LyricsPdfStyle = Field(default_factory=LyricsPdfStyle)
    lyrics_engine: str = Field(default="", max_length=80)
    lyrics_model: str = Field(default="", max_length=80)
    chords_engine: str = Field(default="", max_length=80)
    chords_model: str = Field(default="", max_length=120)
    rights_records: list[RightsRecord] = Field(default_factory=list, max_length=32)
    rights_societies: list[str] = Field(default_factory=lambda: ["SIAE", "SOUNDREEF"], max_length=16)
    preserved_attachments: list[str] = Field(default_factory=list)
    master_volume_db: float = Field(default=0.0, ge=-120.0, le=24.0)
    master_inserts: list[InsertPlugin] = Field(default_factory=list, max_length=16)
    auto_mix_enabled: bool = False
    auto_mix_style: Literal["balanced", "live", "studio", "gentle"] = "balanced"
    auto_mix_snapshot: AutoMixSnapshot | None = None
    base_bpm: float | None = Field(default=None, gt=0, le=500)
    metronome_mode: Literal["fixed", "zones", "adaptive"] = "fixed"
    metronome_sensitivity: float = Field(default=0.35, ge=0.0, le=1.0)
    show_markers_playback: bool = False
    metronome_reference_track_id: str = Field(default="", max_length=80)
    metronome_reference_track_name: str = Field(default="", max_length=200)
    metronome_zone_bpms: dict[str, float] = Field(default_factory=dict)
    metronome_grid_origin_ms: int = Field(default=0, ge=-3600000, le=3600000)
    metronome_shift_ms: int = Field(default=0, ge=-3600000, le=3600000)
    transport_time_mode: Literal["time", "musical"] = "time"
    adaptive_tempo_map: list[AdaptiveTempoPoint] = Field(default_factory=list, max_length=20000)
    pitch_semitones: float = Field(default=0.0, ge=-6.0, le=6.0)
    track_panel_width_px: int = Field(default=225, ge=160, le=520)
    realtime_meter_enabled: bool = False
    render_preview_enabled: bool = False
    follow_playback_enabled: bool = False
    show_lyrics_playback: bool = False
    show_chords_playback: bool = False
    export_panel_visible: bool = True
    metadata_panel_visible: bool = True
    chord_manual_recency: list[str] = Field(default_factory=list)
    piano_panel_visible: bool = False
    piano_panel_width_px: int = Field(default=360, ge=250, le=620)
    inspector_visible: bool = True
    timeline_zoom_px_per_sec: int = Field(default=70, ge=25, le=1200)
    mixer_height_px: int = Field(default=320, ge=180, le=900)
    mixer_meta_tab: Literal["lyrics", "chords", "markers"] = "lyrics"
    export_format: Literal["mta", "wav", "mp3", "mlive_mp3", "mp3g", "flac", "mp4"] = "mta"

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


class DeleteTracksRequest(BaseModel):
    track_ids: list[str] = Field(default_factory=list, max_length=256)
    project: Project | None = None
