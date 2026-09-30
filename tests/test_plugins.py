from pathlib import Path

from fastapi.testclient import TestClient

from app.models import Clip, InsertPlugin, Track
from app.plugins import chain_filter, plugin_catalog

WRITE_HEADERS = {"X-MTA-Request": "1"}


def test_plugin_catalog_and_safe_chain():
    catalog = plugin_catalog()
    assert {"eq", "normalizer", "compressor", "limiter"} <= set(catalog)
    chain = chain_filter(
        [
            InsertPlugin(id="eq1", plugin="eq", preset="vocals-presence"),
            InsertPlugin(id="c1", plugin="compressor", preset="vocal"),
            InsertPlugin(id="l1", plugin="limiter", preset="brickwall-1"),
        ]
    )
    assert "equalizer=" in chain
    assert "acompressor=" in chain
    assert "alimiter=" in chain


def test_disabled_insert_is_not_rendered():
    item = InsertPlugin(id="x1", plugin="eq", preset="flat", enabled=False)
    assert chain_filter([item]) == ""


def test_render_mix_builds_master_chain(tmp_path, monkeypatch):
    import app.audio_engine as engine
    from app.models import Project

    source = tmp_path / "source.wav"
    source.write_bytes(b"audio")
    project = Project(id="p", title="Mix")
    project.tracks = [
        Track(
            id="t1",
            name="Vocals",
            type="melody",
            filename="source.wav",
            duration_ms=1000,
            pan=0.25,
            inserts=[InsertPlugin(id="c1", plugin="compressor", preset="vocal")],
            clips=[Clip(id="cl1", source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)],
        )
    ]
    project.master_inserts = [InsertPlugin(id="l1", plugin="limiter", preset="brickwall-1")]
    seen = []

    monkeypatch.setattr(engine, "render_track", lambda track, source, out, apply_inserts=True: Path(out).write_bytes(b"wav"))
    monkeypatch.setattr(engine, "_run", lambda cmd: seen.append(cmd) or "")
    out = tmp_path / "mix.mp3"
    engine.render_mix(project, lambda pid, name: source, out, fmt="mp3")
    command = seen[-1]
    filters = command[command.index("-filter_complex") + 1]
    assert "stereotools=balance_out=0.2500" in filters
    assert "alimiter=" in filters
    assert "libmp3lame" in command


def test_export_wav_and_mp3_routes(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Formats")
    audio = storage.pdir(project.id) / "audio" / "a.wav"
    audio.write_bytes(b"x")
    project.tracks = [Track(id="t1", name="T", filename="a.wav", duration_ms=1000)]
    storage.save_project(project)

    def fake_mix(project, resolver, out, fmt="mp3", bitrate="320k"):
        Path(out).write_bytes(b"mix")
        return out

    monkeypatch.setattr(main, "render_mix", fake_mix)
    client = TestClient(main.app, headers=WRITE_HEADERS)
    assert client.get(f"/api/projects/{project.id}/export?format=wav").status_code == 200
    assert client.get(f"/api/projects/{project.id}/export?format=mp3").status_code == 200


def test_stem_split_imports_generated_tracks(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    monkeypatch.setattr(main.STEM_SPLITTER, "available", staticmethod(lambda: True))
    monkeypatch.setattr(main, "ffprobe", lambda path: {"streams": [{"codec_type": "audio"}]})
    monkeypatch.setattr(main, "media_duration_ms", lambda path: 1500)

    def fake_split(source, output_dir, model="htdemucs_6s"):
        output_dir.mkdir(parents=True, exist_ok=True)
        drums = output_dir / "drums.wav"
        vocals = output_dir / "vocals.wav"
        drums.write_bytes(b"d")
        vocals.write_bytes(b"v")
        return [drums, vocals]

    monkeypatch.setattr(main.STEM_SPLITTER, "split", staticmethod(fake_split))
    client = TestClient(main.app, headers=WRITE_HEADERS)
    response = client.post(
        "/api/stems/split?target=MTA8&model=htdemucs_6s",
        files={"file": ("song.mp3", b"mp3", "audio/mpeg")},
        headers=WRITE_HEADERS,
    )
    assert response.status_code == 200
    tracks = response.json()["tracks"]
    assert [track["type"] for track in tracks] == ["drums", "melody"]
