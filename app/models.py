from pathlib import Path
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

TrackType = Literal["drums", "bass", "guitars", "keyboards", "orchestra", "winds", "melody", "click", "choirs", "other"]
PluginType = Literal[
    "eq", "normalizer", "compressor", "limiter", "delay", "reverb_lexicon",
    "room_ambience", "graphic_eq_32", "amplify", "stereo_imager",
    "maximizer_loudness", "mastering_wizard", "denoise", "crackle_cleaner", "vst3", "gm_soundfont"
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
    sidechain_track_id: str | None = Field(default=None,pattern=r"^[A-Za-z0-9_-]{1,64}$")
    sidechain_bus: int = Field(default=1,ge=1,le=16)
    sidechain_gain_db: float = Field(default=0,ge=-120,le=24,allow_inf_nan=False)


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


class MidiNote(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12], pattern=r"^[A-Za-z0-9_-]{1,64}$")
    start_ms: float = Field(default=0, ge=0, le=86400000, allow_inf_nan=False)
    duration_ms: float = Field(default=500, gt=0, le=86400000, allow_inf_nan=False)
    pitch: int = Field(default=60, ge=0, le=127)
    velocity: int = Field(default=100, ge=1, le=127)
    channel: int = Field(default=0, ge=0, le=15)
    origin: Literal['manual', 'predicted', 'generated'] = 'manual'
    source_model: str = Field(default='', max_length=160)
    # A model activation is not a calibrated probability of note correctness.
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    confidence_metric: str = Field(default='', max_length=160)


class MidiControl(BaseModel):
    time_ms: float = Field(default=0, ge=0, le=86400000, allow_inf_nan=False)
    # Channel voice messages only; no SysEx, system messages or executable data.
    data: list[int] = Field(min_length=2, max_length=3)

    @field_validator('data')
    @classmethod
    def channel_message(cls, value):
        status=value[0] & 0xF0
        if status not in (0xA0,0xB0,0xC0,0xD0,0xE0) or len(value)!=(2 if status in (0xC0,0xD0) else 3) or any(not 0<=x<=127 for x in value[1:]) or not 0x80<=value[0]<=0xEF:
            raise ValueError('Invalid MIDI channel control')
        return value


class MusicPart(BaseModel):
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    name: str = Field(min_length=1, max_length=200)
    instrument: str = Field(default='unknown', max_length=80)
    program: int | None = Field(default=None, ge=0, le=127)
    percussion: bool = False
    notes: list[MidiNote] = Field(default_factory=list, max_length=50000)
    controls: list[MidiControl] = Field(default_factory=list, max_length=100000)
    source_model: str = Field(default='', max_length=160)
    source_result_id: str = Field(default='', max_length=64)
    review: Literal['unreviewed', 'accepted', 'edited'] = 'unreviewed'


class MidiUmp(BaseModel):
    time_ms: float = Field(default=0,ge=0,le=86400000,allow_inf_nan=False)
    words: list[int] = Field(min_length=1,max_length=4)

    @field_validator('words')
    @classmethod
    def ump_packet(cls,value):
        from .midi_ump import packet
        return packet(value)


class MidiSysEx(BaseModel):
    time_ms: float = Field(default=0,ge=0,le=86400000,allow_inf_nan=False)
    data: list[int] = Field(min_length=2,max_length=65536)

    @field_validator('data')
    @classmethod
    def packet(cls,value):
        if value[0]!=0xF0 or value[-1]!=0xF7 or any(not 0<=n<=127 for n in value[1:-1]):raise ValueError('Invalid complete MIDI SysEx packet')
        return value


class MidiMetronome(BaseModel):
    channel: int = Field(default=9, ge=0, le=15)
    accent_note: int = Field(default=76, ge=0, le=127)
    secondary_note: int = Field(default=77, ge=0, le=127)
    beat_note: int = Field(default=77, ge=0, le=127)
    accent_velocity: int = Field(default=120, ge=1, le=127)
    secondary_velocity: int = Field(default=100, ge=1, le=127)
    beat_velocity: int = Field(default=85, ge=1, le=127)
    gate_ms: float = Field(default=40, gt=0, le=1000, allow_inf_nan=False)


class MidiMeta(BaseModel):
    time_ms: float = Field(default=0, ge=0, le=86400000, allow_inf_nan=False)
    message: dict = Field(max_length=16)

    @field_validator('message')
    @classmethod
    def meta_event(cls, value):
        import json
        from .midi_smf import meta_message
        if len(json.dumps(value, allow_nan=False)) > 8192 or 'time' in value:
            raise ValueError('MIDI metadata exceeds limits')
        try:
            message = meta_message(value)
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ValueError('Invalid MIDI metadata') from exc
        if message.type == 'end_of_track':
            raise ValueError('End-of-track is managed by the SMF writer')
        return value


class Track(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(max_length=200)
    type: TrackType = "other"
    mta_slot: int | None = Field(default=None, ge=1, le=16)
    filename: str = Field(min_length=1, max_length=128)
    kind: Literal['audio', 'midi'] = 'audio'
    music_result_id: str = Field(default='', max_length=64)
    music_part_id: str = Field(default='', max_length=64)
    music_source_model: str = Field(default='', max_length=160)
    music_generation: dict = Field(default_factory=dict, max_length=32)
    midi_metronome: MidiMetronome | None = None
    midi_metronome_revision: str = Field(default="", max_length=64)
    midi_smf_type: Literal[0, 1, 2] = 1
    midi_division: int = Field(default=960, ge=-32768, le=32767)
    midi_meta: list[MidiMeta] = Field(default_factory=list, max_length=10000)
    midi_notes: list[MidiNote] = Field(default_factory=list, max_length=50000)
    midi_ump: list[MidiUmp] = Field(default_factory=list,max_length=100000)
    mpe_zone: Literal['off','lower','upper'] = 'off'
    mpe_members: int = Field(default=15,ge=1,le=15)
    mpe_pitch_bend: int = Field(default=48,ge=1,le=96)
    midi_sysex: list[MidiSysEx] = Field(default_factory=list,max_length=1024)
    midi_controls: list[MidiControl] = Field(default_factory=list, max_length=100000)
    instrument: InsertPlugin | None = None
    midi_route: Literal['instrument','hardware','both','none'] = 'instrument'
    clips_initialized: bool = False
    derived_source_track_id: str = Field(default="", max_length=64)
    derived_stem_key: str = Field(default="", max_length=200)
    source_clip_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    duration_ms: int = Field(default=0, ge=0)
    gain_db: float = Field(default=0.0, ge=-24.0, le=24.0, allow_inf_nan=False)
    volume_db: float = Field(default=0.0, ge=-120.0, le=24.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    master_bypass: bool = False  # master bounce already includes the master processing
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
    delay_unit: Literal["ms", "beats", "bars", "bars_beats"] | None = None
    delay_ms: int = Field(default=0, ge=-86_400_000, le=86_400_000)
    height_px: int = Field(default=78, ge=78, le=420)

    @field_validator('midi_division')
    @classmethod
    def smf_timebase(cls, value):
        from .midi_smf import division_rate
        division_rate(value)
        return value

    @field_validator('instrument')
    @classmethod
    def midi_instrument(cls,value):
        if value is not None and value.plugin not in ('vst3','gm_soundfont'):raise ValueError('MIDI instruments must use VST3 or General MIDI')
        if value is not None and value.plugin=='gm_soundfont':
            from .gm_instruments import validate
            value.params=validate(value.params)
        return value


class Marker(BaseModel):
    end_ms: int | None = Field(default=None, ge=0)
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    time_ms: int = Field(ge=0)
    label: str = Field(max_length=500)
    color: str = Field(default="#204A87", pattern=r"^#[0-9A-Fa-f]{6}$")
    # Optional document-layout settings for the section starting at this marker.
    # The value is expressed in millimetres so it maps directly to print layout.
    section_indent_enabled: bool = False
    section_indent_mm: float = Field(default=0.0, ge=0.0, le=100.0)
    manual_lyric_anchor: bool = False
    anchor_lyric_time_ms: int | None = Field(default=None, ge=0)
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
    end_ms: int | None = Field(default=None, ge=0)
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
    target: Literal["MTA8", "MTA16", "DAW", "DAW_MIDI", "existing"] = "existing"
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
    master_fade_enabled: bool = False
    master_fade_in_ms: int = Field(default=0, ge=0, le=86400000)
    master_fade_out_ms: int = Field(default=0, ge=0, le=86400000)
    timeline_end_ms: int | None = Field(default=None, ge=0, le=86400000)
    timeline_snap: Literal["off", "beats", "bars"] = "off"
    timeline_magnetic: bool = False
    metronome_insertion_ms: int = Field(default=0, ge=0, le=86400000)
    metronome_pre_roll_bars: int = Field(default=0, ge=0, le=64)
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
    target: Literal["MTA8", "MTA16", "DAW", "DAW_MIDI", "MIDI"] = "MTA8"
    project_kind_version: Literal[0, 1] = 0
    sample_rate: Literal[44100, 48000, 96000] = 44100
    audio_storage_mode: Literal["wav", "flac"] = "wav"
    mta_device_profile: Literal["auto", "merish5_xynthia2", "bbeat_divo", "mlive_mta16_default", "merish5_plus_mta16", "generic"] = "auto"
    tracks: list[Track] = Field(default_factory=list)
    archived_tracks: list[Track] = Field(default_factory=list, max_length=1024)
    clip_library: list[ProjectClip] = Field(default_factory=list, max_length=512)
    markers: list[Marker] = Field(default_factory=list)
    lyrics: list[LyricLine] = Field(default_factory=list)
    chords: list[Chord] = Field(default_factory=list)
    ai_publication_token: str = Field(default="", max_length=64)
    music_imports: dict[Annotated[str, Field(pattern=r'^[a-f0-9]{32}$')], Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]] = Field(default_factory=dict, max_length=1024)
    music_alternatives: list[MusicPart] = Field(default_factory=list, max_length=128)
    recovered_ai_imports: list[str] = Field(default_factory=list, max_length=2048)
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
    original_bpm: float | None = Field(default=None, gt=0, le=500)
    metronome_mode: Literal["fixed", "zones", "adaptive"] = "fixed"
    vst_host_sync: bool = True
    vst_loop_enabled: bool = False
    vst_loop_start_ms: int = Field(default=0,ge=0,le=86400000)
    vst_loop_end_ms: int = Field(default=0,ge=0,le=86400000)
    metronome_bpm: float | None = Field(default=None, ge=20, le=400)
    metronome_time_signature: Literal["2/4", "3/4", "4/4", "5/4", "6/8", "7/8", "9/8", "12/8"] | None = None
    metronome_zone_signatures: dict[str, Literal["2/4", "3/4", "4/4", "5/4", "6/8", "7/8", "9/8", "12/8"]] = Field(default_factory=dict)
    metronome_manual_zone_signatures: dict[str, Literal["2/4", "3/4", "4/4", "5/4", "6/8", "7/8", "9/8", "12/8"]] = Field(default_factory=dict)
    metronome_sensitivity: float = Field(default=0.35, ge=0.0, le=1.0)
    metronome_start_ms: int = Field(default=0, ge=0, le=86_400_000)
    metronome_stop_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    show_markers_playback: bool = False
    metronome_reference_track_id: str = Field(default="", max_length=80)
    metronome_reference_track_name: str = Field(default="", max_length=200)
    metronome_zone_bpms: dict[str, float] = Field(default_factory=dict)
    metronome_manual_zone_bpms: dict[str, float] = Field(default_factory=dict)
    metronome_grid_origin_ms: int = Field(default=0, ge=-86400000, le=86400000)
    metronome_shift_ms: int = Field(default=0, ge=-86400000, le=86400000)
    tempo_known: bool | None = None
    musical_origin_ms: int | None = Field(default=None, ge=-86400000, le=86400000)
    transport_time_mode: Literal["auto", "time", "musical"] = "auto"
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
    timeline_zoom_px_per_sec: float = Field(default=70, ge=25, le=1200, allow_inf_nan=False)
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
