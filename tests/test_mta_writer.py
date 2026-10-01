import shutil
import subprocess

import pytest

from app.models import Clip, Track


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="FFmpeg tools required")
def test_proprietary_mta_writer_transport_and_import_roundtrip(tmp_path, monkeypatch):
    import app.storage as storage
    from app.codec import export_mta, ffprobe, import_mta
    from app.mta_reverse import deobfuscate_media_copy, inspect_cluster_transport

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    source = tmp_path / "tone.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1",
            "-ar", "44100", "-ac", "2", str(source),
        ],
        check=True,
    )

    project = storage.create_project("Writer smoke", owner_user_id=1)
    shutil.copy2(source, storage.audio_path(project.id, "tone.wav"))
    project.tracks = [
        Track(
            id="track1",
            name="Tone",
            filename="tone.wav",
            duration_ms=1000,
            clips=[Clip(id="clip1", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)],
        )
    ]
    storage.save_project(project)

    output = tmp_path / "writer-smoke.MTA"
    export_mta(project, output)

    transport = inspect_cluster_transport(output)
    assert transport["validated"] is True
    assert transport["first_cluster_is_canonical"] is False
    assert transport["media_xor_validated"] is True
    assert transport["seek_cluster_absolute"] is not None
    assert transport["cue_point_count"] >= 1

    canonical = tmp_path / "canonical.mka"
    deobfuscate_media_copy(output, canonical)
    streams = [s for s in ffprobe(canonical)["streams"] if s.get("codec_type") == "audio"]
    assert len(streams) == 1

    imported = storage.create_project("Imported", owner_user_id=1)
    import_mta(output, imported)
    assert len(imported.tracks) == 1
    assert imported.tracks[0].name == "Tone"
    assert (storage.pdir(imported.id) / "mta-analysis.json").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_mta_layout_places_cues_before_first_cluster(tmp_path):
    from app.mta_reverse import inspect_cluster_transport
    from app.mta_writer import normalize_matroska_for_mta

    source = tmp_path / "canonical.mka"
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=220:duration=1",
            "-ar", "44100", "-ac", "2", "-c:a", "libmp3lame",
            "-b:a", "320k", "-f", "matroska", str(source),
        ],
        check=True,
    )
    normalized = tmp_path / "normalized.mka"
    cluster_offset = normalize_matroska_for_mta(source, normalized)
    info = inspect_cluster_transport(normalized)
    assert info["first_cluster_is_canonical"] is True
    assert info["seek_cluster_absolute"] == cluster_offset
    assert info["cue_positions_match_seek_cluster"] is True
    assert info["cue_point_count"] >= 1
