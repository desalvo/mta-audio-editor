"""MTA container adapter with non-destructive DAW rendering and export-slot merging."""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import uuid
from pathlib import Path

from .audio_engine import media_duration_ms, project_time_pitch_filter, render_track
from .models import Chord, Clip, LyricLine, MtaSlotMapping, Project, Track
from .mta_writer import normalize_matroska_for_mta
from .mta_reverse import (
    analyze_mta,
    deobfuscate_media_copy,
    inspect_cluster_transport,
    obfuscate_media_copy,
)
from .storage import attachment_path, audio_path, pdir, save_project
from .music_text import synchronized_plain_text

MTA8_STABLE_TYPES = ["drums", "bass", "guitars", "keyboards", "orchestra", "winds"]
LOGGER = logging.getLogger(__name__)


def infer_mta_track_type(index: int, tags: dict) -> str:
    explicit = str(tags.get("MTA_TYPE") or "").strip().lower()
    allowed = Track.model_fields["type"].annotation.__args__
    if explicit in allowed:
        return explicit
    title = str(tags.get("title") or "").strip().lower()
    if any(token in title for token in ("click", "metronome", "metronomo")):
        return "click"
    if any(token in title for token in ("melody", "melodia")):
        return "melody"
    return MTA8_STABLE_TYPES[index] if index < len(MTA8_STABLE_TYPES) else "other"


MTA8_DEVICE_LAYOUTS = {
    "merish5_xynthia2": {
        "drums": 1, "bass": 2, "guitars": 3, "keyboards": 4,
        "orchestra": 5, "winds": 6, "melody": 7, "click": 8,
    },
    "bbeat_divo": {
        "drums": 1, "bass": 2, "guitars": 3, "keyboards": 4,
        "orchestra": 5, "winds": 6, "click": 7, "melody": 8,
    },
}
MTA8_SLOT_TYPES = {
    "merish5_xynthia2": ["drums","bass","guitars","keyboards","orchestra","winds","melody","click"],
    "bbeat_divo": ["drums","bass","guitars","keyboards","orchestra","winds","click","melody"],
}

# Corpus-derived MTA16 convention (4 real M-Live MTA files available to the
# project): Metronome was stream 1 in all 4; explicit Melody Track was stream
# 9 in 2/3 files carrying that label and stream 10 in 1/3.
MTA16_DEFAULT_LAYOUT = {"click": 1, "melody": 9}
MTA16_PROFILE_ALIASES = {"mlive_mta16_default", "merish5_plus_mta16"}


def resolve_mta_device_profile(project: Project, requested: str | None = None) -> str:
    # A direct/legacy backend export with no profile argument preserves the
    # historical stream layout when the project itself is still "auto".
    # The configured export UI explicitly sends requested="auto", which opts
    # into the device-aware defaults below.
    stored = (project.mta_device_profile or "auto").strip()
    if requested is None:
        return "generic" if stored == "auto" else stored
    profile = (requested or "auto").strip()
    if profile != "auto":
        return profile
    if project.target == "MTA8":
        return "bbeat_divo"
    if project.target == "MTA16":
        return "mlive_mta16_default"
    return "generic"


def detect_imported_mta_profile(project: Project) -> str:
    if project.target == "MTA8" and len(project.tracks) >= 8:
        pair = (project.tracks[6].type, project.tracks[7].type)
        if pair == ("melody", "click"):
            return "merish5_xynthia2"
        if pair == ("click", "melody"):
            return "bbeat_divo"
    if project.target == "MTA16" and project.tracks:
        first_is_click = project.tracks[0].type == "click"
        melody_positions = [i + 1 for i, track in enumerate(project.tracks) if track.type == "melody"]
        if first_is_click and (not melody_positions or melody_positions[0] in {9, 10}):
            return "mlive_mta16_default"
    return "auto"


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or "command failed")
    return p.stdout


def ffprobe(path: Path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))


def import_mta(path: Path, project: Project) -> Project:
    d = pdir(project.id)
    audio = d / "audio"
    att = d / "attachments"

    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        source = path
        transport = inspect_cluster_transport(path)
        if transport.get("media_xor_validated"):
            source = td / "canonical-import.mka"
            deobfuscate_media_copy(path, source, int(transport["seek_cluster_absolute"]))

        info = ffprobe(source)
        audio_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
        tracks = []
        for i, stream in enumerate(audio_streams):
            tags = stream.get("tags") or {}
            name = tags.get("title") or f"Track {i+1}"
            typ = infer_mta_track_type(i, tags)
            out = audio / f"track-{i+1:02d}.mp3"
            try:
                run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-map", f"0:a:{i}", "-c:a", "copy", str(out)])
            except Exception:
                run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-map", f"0:a:{i}", "-c:a", "libmp3lame", "-b:a", "320k", str(out)])
            dur = media_duration_ms(out)
            allowed = Track.model_fields["type"].annotation.__args__
            tracks.append(
                Track(
                    id=uuid.uuid4().hex[:10],
                    name=name,
                    type=typ if typ in allowed else "other",
                    mta_slot=i + 1,
                    filename=out.name,
                    duration_ms=dur,
                    channels=int(stream.get("channels") or 0),
                    channel_layout=str(stream.get("channel_layout") or ""),
                    clips=[Clip(id=uuid.uuid4().hex[:10], source_start_ms=0, source_end_ms=dur, timeline_start_ms=0)],
                )
            )

        preserved = []
        attachment_streams = [s for s in info.get("streams", []) if s.get("codec_type") == "attachment"]
        for aidx, stream in enumerate(attachment_streams):
            idx = stream.get("index")
            tags = stream.get("tags") or {}
            fname = tags.get("filename") or f"attachment-{idx}.bin"
            safe = "".join(ch for ch in fname if ch.isalnum() or ch in "._-") or f"attachment-{idx}.bin"
            out = att / safe
            try:
                run(["ffmpeg", "-y", "-v", "error", f"-dump_attachment:t:{aidx}", str(out), "-i", str(source), "-f", "null", "-"])
                if out.exists():
                    preserved.append(out.name)
                    if out.name == "mta-synchronized-text.json":
                        try:
                            sync = json.loads(out.read_text(encoding="utf-8"))
                            project.lyrics = [LyricLine(**item) for item in sync.get("lyrics", [])]
                            project.chords = [Chord(**item) for item in sync.get("chords", [])]
                            project.original_title = str(sync.get("original_title") or project.original_title or "")[:300]
                            project.authors = [str(x)[:200] for x in (sync.get("authors") or []) if str(x).strip()][:64]
                            project.rights_records = [RightsRecord(**item) for item in (sync.get("rights_records") or [])][:32]
                            project.rights_societies = [str(x).strip().upper() for x in (sync.get("rights_societies") or project.rights_societies) if str(x).strip()][:16]
                        except Exception as sync_exc:
                            LOGGER.warning("Unable to restore synchronized text attachment %s: %s", out, sync_exc)
            except Exception as exc:
                LOGGER.warning("Unable to preserve attachment %s from %s: %s", safe, path, exc)

    project.tracks = tracks
    project.preserved_attachments = preserved
    project.target = "MTA16" if len(tracks) > 8 else "MTA8"
    project.mta_device_profile = detect_imported_mta_profile(project)
    try:
        report = analyze_mta(path, att / "reverse-analysis")
        (d / "mta-analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        # Recover stock synchronized lyrics/chords when a verified SYL decoder is available.
        for item in report.get("attachments", []):
            sections = ((item.get("embedded_id3") or {}).get("proprietary_sections") or {})
            lyr = (((sections.get("LYRICS") or {}).get("observed_record_decoder") or {}).get("records") or [])
            chd = (((sections.get("CHORDS") or {}).get("observed_record_decoder") or {}).get("records") or [])
            if lyr and not project.lyrics:
                project.lyrics = [LyricLine(time_ms=int(row["time_ms"]), text=str(row.get("text") or "")) for row in lyr if "time_ms" in row and str(row.get("text") or "").strip()]
            if chd and not project.chords:
                project.chords = [Chord(time_ms=int(row["time_ms"]), chord=str(row.get("text") or "")) for row in chd if "time_ms" in row and str(row.get("text") or "").strip()]
    except Exception as exc:
        LOGGER.warning("Unable to analyze imported MTA %s: %s", path, exc)
    save_project(project)
    return project

def _metadata_attachment(project: Project) -> Path:
    out = pdir(project.id) / "attachments" / "mta-editor.json"
    out.write_text(json.dumps({
        "schema": "mta-audio-editor/v3", "title": project.title, "original_title": project.original_title, "artist": project.artist, "authors": project.authors, "bpm": project.bpm, "key": project.key, "mta_device_profile": project.mta_device_profile,
        "tracks": [{"id": t.id, "name": t.name, "type": t.type, "mta_slot": t.mta_slot, "pan": t.pan, "clips": [c.model_dump() for c in t.clips], "inserts": [x.model_dump() for x in t.inserts]} for t in project.tracks],
        "master": {"volume_db": project.master_volume_db, "inserts": [x.model_dump() for x in project.master_inserts]},
        "lyrics": [x.model_dump() for x in project.lyrics], "chords": [x.model_dump() for x in project.chords], "markers": [x.model_dump() for x in project.markers],
        "rights_records": [x.model_dump(mode="json") for x in project.rights_records],
        "rights_societies": project.rights_societies,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _synchronized_text_attachments(project: Project) -> list[Path]:
    """Create timestamped project attachments embedded in every exported MTA.

    These attachments preserve exact millisecond synchronization independently of
    the audio slot mapping. Stock proprietary SYL attachments are preserved too;
    the editor-specific JSON/LRC/TSV payloads provide a lossless round trip for
    newly extracted or edited lyrics/chords.
    """
    out: list[Path] = []
    adir = pdir(project.id) / "attachments"
    adir.mkdir(parents=True, exist_ok=True)
    if project.lyrics:
        lrc = adir / "lyrics-synchronized.lrc"
        lrc.write_text(synchronized_plain_text(project.lyrics, []), encoding="utf-8")
        out.append(lrc)
    if project.chords:
        chords = adir / "chords-synchronized.tsv"
        chords.write_text("\n".join(f"{item.time_ms}\t{item.chord}" for item in sorted(project.chords, key=lambda x: x.time_ms)) + "\n", encoding="utf-8")
        out.append(chords)
    if project.lyrics or project.chords or project.rights_records or project.original_title or project.authors:
        sync = adir / "mta-synchronized-text.json"
        sync.write_text(json.dumps({
            "schema": "mta-audio-editor/synchronized-text-v1",
            "timebase": "milliseconds-from-project-start",
            "title": project.title,
            "original_title": project.original_title,
            "artist": project.artist,
            "authors": project.authors,
            "lyrics": [x.model_dump() for x in project.lyrics],
            "chords": [x.model_dump() for x in project.chords],
            "rights_records": [x.model_dump(mode="json") for x in project.rights_records],
            "rights_societies": project.rights_societies,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        out.append(sync)
    return out


def suggested_slots(project: Project, profile: str | None = None) -> list[dict]:
    if project.target == "DAW":
        raise ValueError("DAW project requires an explicit MTA8/MTA16 export target")
    limit = 8 if project.target == "MTA8" else 16
    effective = resolve_mta_device_profile(project, profile)
    if project.target == "MTA8":
        layout = MTA8_DEVICE_LAYOUTS.get(effective)
    elif project.target == "MTA16" and effective in MTA16_PROFILE_ALIASES:
        layout = MTA16_DEFAULT_LAYOUT
    else:
        layout = None
    if not layout:
        grouped: dict[int, list] = {}
        free = list(range(1, limit + 1))
        remaining = []
        for track in project.tracks:
            explicit = int(track.mta_slot) if track.mta_slot and 1 <= int(track.mta_slot) <= limit else None
            if explicit:
                grouped.setdefault(explicit, []).append(track)
                if explicit in free:
                    free.remove(explicit)
            else:
                remaining.append(track)
        for track in remaining:
            if not free:
                break
            grouped.setdefault(free.pop(0), []).append(track)
        return [
            {"slot": slot, "name": " + ".join(t.name for t in tracks)[:200],
             "type": tracks[0].type if len(tracks) == 1 else "other",
             "track_ids": [t.id for t in tracks]}
            for slot, tracks in sorted(grouped.items())
        ]
    grouped: dict[int, list] = {}
    remaining = []
    for track in project.tracks:
        explicit_slot = int(track.mta_slot) if track.mta_slot and 1 <= int(track.mta_slot) <= limit else None
        slot = explicit_slot or layout.get(track.type)
        if slot:
            grouped.setdefault(slot, []).append(track)
        else:
            remaining.append(track)
    free = [slot for slot in range(1, limit + 1) if slot not in grouped]
    for track in remaining:
        if free:
            grouped.setdefault(free.pop(0), []).append(track)
        else:
            # No free family slot remains: merge into the last non-special
            # musical slot rather than displacing Click/Melody.
            fallback = 6 if limit >= 8 else limit
            grouped.setdefault(fallback, []).append(track)
    result = []
    for slot in sorted(grouped):
        tracks = grouped[slot]
        if project.target == "MTA8":
            typ = MTA8_SLOT_TYPES[effective][slot - 1]
        elif slot == 1 and effective in MTA16_PROFILE_ALIASES:
            typ = "click"
        elif slot == 9 and effective in MTA16_PROFILE_ALIASES:
            typ = "melody"
        else:
            typ = tracks[0].type if len(tracks) == 1 else "other"
        result.append({
            "slot": slot,
            "name": " + ".join(t.name for t in tracks)[:200],
            "type": typ,
            "track_ids": [t.id for t in tracks],
        })
    return result


def validate_slot_mapping(project: Project, slots: list[MtaSlotMapping] | None, profile: str | None = None) -> list[MtaSlotMapping]:
    if project.target == "DAW":
        raise ValueError("DAW project requires an explicit MTA8/MTA16 export target")
    limit = 8 if project.target == "MTA8" else 16
    if not slots:
        if len(project.tracks) > limit:
            raise ValueError(f"{project.target} export requires a merge mapping for {len(project.tracks)} project tracks into at most {limit} slots")
        suggested = suggested_slots(project, profile)
        flattened = [tid for slot in suggested for tid in slot["track_ids"]]
        if set(flattened) != {t.id for t in project.tracks}:
            raise ValueError(f"{project.target} export requires an explicit mapping for all project tracks")
        return [MtaSlotMapping(**x) for x in suggested]
    if len(slots) > limit:
        raise ValueError(f"{project.target} supports at most {limit} output slots")
    if len({s.slot for s in slots}) != len(slots):
        raise ValueError("duplicate MTA output slot")
    known = {t.id for t in project.tracks}
    flattened = [tid for s in slots for tid in s.track_ids]
    if set(flattened) != known or len(flattened) != len(known):
        raise ValueError("every project track must be assigned exactly once to an MTA output slot")
    if len(set(flattened)) != len(flattened):
        raise ValueError("a project track cannot be assigned to multiple MTA slots")
    if any(s.slot > limit for s in slots):
        raise ValueError("MTA slot is outside target capacity")
    return sorted(slots, key=lambda x: x.slot)


def export_mta(project: Project, out: Path, slots: list[MtaSlotMapping] | None = None, profile: str | None = None) -> Path:
    effective_profile = resolve_mta_device_profile(project, profile)
    slots = validate_slot_mapping(project, slots, effective_profile)
    by_id = {t.id: t for t in project.tracks}
    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        rendered: dict[str, Path] = {}
        for i, track in enumerate(project.tracks):
            rw = td / f"source-{i:02d}.wav"
            render_track(track, audio_path(project.id, track.filename), rw)
            rendered[track.id] = rw

        slot_files: list[Path] = []
        physical_slots: list[MtaSlotMapping] = []
        slot_by_number = {slot.slot: slot for slot in slots}
        force_full_mta8 = project.target == "MTA8" and effective_profile in MTA8_DEVICE_LAYOUTS
        force_mta16_roles = project.target == "MTA16" and effective_profile in MTA16_PROFILE_ALIASES
        max_slot = 8 if force_full_mta8 else max(slot_by_number, default=0)
        if force_mta16_roles and any(t.type == "melody" for t in project.tracks):
            max_slot = max(max_slot, 9)
        max_duration_ms = max((t.duration_ms for t in project.tracks), default=1000)
        for slot_number in range(1, max_slot + 1):
            slot = slot_by_number.get(slot_number)
            if slot is None:
                if force_full_mta8:
                    typ = MTA8_SLOT_TYPES[effective_profile][slot_number - 1]
                elif force_mta16_roles and slot_number == 1:
                    typ = "click"
                elif force_mta16_roles and slot_number == 9:
                    typ = "melody"
                else:
                    typ = "other"
                silent = td / f"slot-{slot_number:02d}-silence.wav"
                run([
                    "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", f"{max(0.001, max_duration_ms / 1000):.3f}",
                    "-c:a", "pcm_s24le", str(silent),
                ])
                slot_files.append(silent)
                physical_slots.append(MtaSlotMapping(slot=slot_number, name=typ.title(), type=typ, track_ids=[project.tracks[0].id]))
                continue
            tracks = [by_id[tid] for tid in slot.track_ids]
            cmd = ["ffmpeg", "-y", "-v", "error"]
            for t in tracks:
                cmd += ["-i", str(rendered[t.id])]
            any_solo = any(t.solo for t in project.tracks)
            filters = []
            labels = []
            for idx, t in enumerate(tracks):
                muted = t.mute or (any_solo and not t.solo)
                gain = -120.0 if muted else t.volume_db
                pan = min(1.0, max(-1.0, t.pan))
                filters.append(f"[{idx}:a]aformat=channel_layouts=stereo,volume={gain:.3f}dB,stereotools=balance_out={pan:.4f}[s{idx}]")
                labels.append(f"[s{idx}]")
            transform = project_time_pitch_filter(project)
            if len(labels) == 1:
                filters.append(f"{labels[0]}{transform}[out]")
            else:
                filters.append("".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0[mix]")
                filters.append(f"[mix]{transform}[out]")
            merged = td / f"slot-{slot_number:02d}.wav"
            cmd += ["-filter_complex", ";".join(filters), "-map", "[out]", "-ar", "44100", "-c:a", "pcm_s24le", str(merged)]
            run(cmd)
            slot_files.append(merged)
            physical_slots.append(slot)

        cmd = ["ffmpeg", "-y", "-v", "error"]
        for r in slot_files: cmd += ["-i", str(r)]
        for i in range(len(slot_files)): cmd += ["-map", f"{i}:a:0"]
        cmd += ["-c:a", "libmp3lame", "-q:a", "2"]
        for i, slot in enumerate(physical_slots):
            cmd += [f"-metadata:s:a:{i}", f"title={slot.name}", f"-metadata:s:a:{i}", f"MTA_TYPE={slot.type}"]
        attachments = []
        for name in project.preserved_attachments:
            try: f = attachment_path(project.id, name)
            except ValueError: continue
            if f.exists(): attachments.append(f)
        meta = _metadata_attachment(project)
        if meta not in attachments: attachments.append(meta)
        for synced in _synchronized_text_attachments(project):
            if synced not in attachments:
                attachments.append(synced)
        for a in attachments:
            mimetype = "application/json" if a.suffix.lower() == ".json" else ("text/plain" if a.suffix.lower() in {".lrc", ".tsv", ".txt"} else "application/octet-stream")
            cmd += ["-attach", str(a), "-metadata:s:t", f"filename={a.name}", "-metadata:s:t", f"mimetype={mimetype}"]
        canonical = td / "canonical-export.mka"
        cmd += [
            "-metadata", f"TITLE={project.title}",
            "-metadata", f"ARTIST={project.artist}",
            "-metadata", f"BPM={project.bpm}",
            "-f", "matroska", str(canonical),
        ]
        run(cmd)

        normalized = td / "mta-layout.mka"
        media_offset = normalize_matroska_for_mta(canonical, normalized)
        normalized_info = inspect_cluster_transport(normalized)
        if not normalized_info.get("first_cluster_is_canonical"):
            raise RuntimeError("normalized MTA layout does not expose a canonical first Cluster")
        obfuscate_media_copy(normalized, out, media_offset)

        written = inspect_cluster_transport(out)
        if not written.get("media_xor_validated"):
            out.unlink(missing_ok=True)
            raise RuntimeError("generated MTA media transport failed XOR validation")
    return out
