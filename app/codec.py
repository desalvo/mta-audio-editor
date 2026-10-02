"""MTA container adapter with non-destructive DAW rendering and export-slot merging."""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import uuid
from pathlib import Path

from .audio_engine import media_duration_ms, project_time_pitch_filter, render_track
from .models import Clip, MtaSlotMapping, Project, Track
from .mta_writer import normalize_matroska_for_mta
from .mta_reverse import (
    analyze_mta,
    deobfuscate_media_copy,
    inspect_cluster_transport,
    obfuscate_media_copy,
)
from .storage import attachment_path, audio_path, pdir, save_project

MTA8_TYPES = ["drums", "bass", "guitars", "keyboards", "orchestra", "winds", "melody", "click"]
LOGGER = logging.getLogger(__name__)


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
            name = (stream.get("tags") or {}).get("title") or f"Track {i+1}"
            typ = (stream.get("tags") or {}).get("MTA_TYPE") or (MTA8_TYPES[i] if i < len(MTA8_TYPES) else "other")
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
                    filename=out.name,
                    duration_ms=dur,
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
            except Exception as exc:
                LOGGER.warning("Unable to preserve attachment %s from %s: %s", safe, path, exc)

    project.tracks = tracks
    project.preserved_attachments = preserved
    project.target = "MTA16" if len(tracks) > 8 else "MTA8"
    try:
        report = analyze_mta(path, att / "reverse-analysis")
        (d / "mta-analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        LOGGER.warning("Unable to analyze imported MTA %s: %s", path, exc)
    save_project(project)
    return project

def _metadata_attachment(project: Project) -> Path:
    out = pdir(project.id) / "attachments" / "mta-editor.json"
    out.write_text(json.dumps({
        "schema": "mta-audio-editor/v3", "title": project.title, "artist": project.artist, "bpm": project.bpm, "key": project.key,
        "tracks": [{"id": t.id, "name": t.name, "type": t.type, "pan": t.pan, "clips": [c.model_dump() for c in t.clips], "inserts": [x.model_dump() for x in t.inserts]} for t in project.tracks],
        "master": {"volume_db": project.master_volume_db, "inserts": [x.model_dump() for x in project.master_inserts]},
        "lyrics": [x.model_dump() for x in project.lyrics], "chords": [x.model_dump() for x in project.chords], "markers": [x.model_dump() for x in project.markers],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def suggested_slots(project: Project) -> list[dict]:
    limit = 8 if project.target == "MTA8" else 16
    slots = []
    for i, track in enumerate(project.tracks[:limit]):
        slots.append({"slot": i + 1, "name": track.name, "type": track.type, "track_ids": [track.id]})
    return slots


def validate_slot_mapping(project: Project, slots: list[MtaSlotMapping] | None) -> list[MtaSlotMapping]:
    limit = 8 if project.target == "MTA8" else 16
    if not slots:
        if len(project.tracks) > limit:
            raise ValueError(f"{project.target} export requires a merge mapping for {len(project.tracks)} project tracks into at most {limit} slots")
        return [MtaSlotMapping(**x) for x in suggested_slots(project)]
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


def export_mta(project: Project, out: Path, slots: list[MtaSlotMapping] | None = None) -> Path:
    slots = validate_slot_mapping(project, slots)
    by_id = {t.id: t for t in project.tracks}
    with tempfile.TemporaryDirectory() as td_raw:
        td = Path(td_raw)
        rendered: dict[str, Path] = {}
        for i, track in enumerate(project.tracks):
            rw = td / f"source-{i:02d}.wav"
            render_track(track, audio_path(project.id, track.filename), rw)
            rendered[track.id] = rw

        slot_files: list[Path] = []
        for pos, slot in enumerate(slots):
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
            merged = td / f"slot-{pos+1:02d}.wav"
            cmd += ["-filter_complex", ";".join(filters), "-map", "[out]", "-ar", "44100", "-c:a", "pcm_s24le", str(merged)]
            run(cmd)
            slot_files.append(merged)

        cmd = ["ffmpeg", "-y", "-v", "error"]
        for r in slot_files: cmd += ["-i", str(r)]
        for i in range(len(slot_files)): cmd += ["-map", f"{i}:a:0"]
        cmd += ["-c:a", "libmp3lame", "-q:a", "2"]
        for i, slot in enumerate(slots):
            cmd += [f"-metadata:s:a:{i}", f"title={slot.name}", f"-metadata:s:a:{i}", f"MTA_TYPE={slot.type}"]
        attachments = []
        for name in project.preserved_attachments:
            try: f = attachment_path(project.id, name)
            except ValueError: continue
            if f.exists(): attachments.append(f)
        meta = _metadata_attachment(project)
        if meta not in attachments: attachments.append(meta)
        for a in attachments:
            cmd += ["-attach", str(a), "-metadata:s:t", f"filename={a.name}", "-metadata:s:t", "mimetype=application/octet-stream"]
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
