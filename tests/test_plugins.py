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


def test_extended_plugin_catalog_and_custom_filters(tmp_path, monkeypatch):
    import app.plugins as plugins

    monkeypatch.setattr(plugins, "CUSTOM_FILE", tmp_path / "custom.json")
    catalog = plugins.plugin_catalog()
    expected = {
        "delay", "reverb_lexicon", "room_ambience", "graphic_eq_32", "amplify",
        "stereo_imager", "maximizer_loudness", "mastering_wizard", "denoise", "crackle_cleaner",
    }
    assert expected <= set(catalog)
    assert "aecho=" in plugins.custom_filter("delay", {"delay_ms": 220, "decay": 0.25})
    assert "volume=-4.00dB" in plugins.custom_filter("amplify", {"gain_db": -4})
    assert "afftdn=" in plugins.custom_filter("denoise", {"reduction_db": 12, "noise_floor_db": -52})
    assert "adeclick=" in plugins.custom_filter("crackle_cleaner", {"strength": 0.7})
    params = plugins.save_user_preset("amplify", "Quiet take", {"gain_db": -5.5})
    assert params["gain_db"] == -5.5
    assert "user:Quiet take" in plugins.plugin_catalog()["amplify"]
    item = InsertPlugin(id="amp1", plugin="amplify", preset="user:Quiet take")
    assert "volume=-5.50dB" == plugins.plugin_filter(item)


def test_graphic_eq_32_custom_is_bounded():
    import app.plugins as plugins

    params = {f"g{freq}": 0 for freq in plugins.BANDS_32}
    params["g1000"] = 3.5
    expr = plugins.custom_filter("graphic_eq_32", params)
    assert "f=1000" in expr and "g=3.50" in expr
    params["g1000"] = 99
    import pytest
    with pytest.raises(ValueError):
        plugins.custom_filter("graphic_eq_32", params)


def test_auto_mix_is_reversible():
    from app.auto_mix import disable_auto_mix, enable_auto_mix
    from app.models import Project

    project = Project(id="p", title="Auto")
    project.tracks = [
        Track(id="drums1", name="Drums", type="drums", filename="d.wav", volume_db=-1.5, pan=0.1),
        Track(id="gtr1", name="Guitar L", type="guitars", filename="g1.wav", volume_db=-2.0, pan=0.0),
        Track(id="gtr2", name="Guitar R", type="guitars", filename="g2.wav", volume_db=-2.5, pan=0.0),
    ]
    enable_auto_mix(project, "balanced")
    assert project.auto_mix_enabled is True
    assert project.tracks[0].volume_db == -4.0
    assert any(x.plugin == "compressor" for x in project.tracks[0].inserts)
    assert project.tracks[1].pan < 0 < project.tracks[2].pan
    assert any(x.plugin == "mastering_wizard" for x in project.master_inserts)
    disable_auto_mix(project)
    assert project.auto_mix_enabled is False
    assert project.tracks[0].volume_db == -1.5
    assert project.tracks[0].pan == 0.1
    assert project.tracks[0].inserts == []


def test_custom_preset_api_and_auto_mix_route(tmp_path, monkeypatch):
    import app.main as main
    import app.plugins as plugins
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setattr(plugins, "CUSTOM_FILE", tmp_path / "_custom_presets.json")
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    project = storage.create_project("Auto route")
    audio = storage.pdir(project.id) / "audio" / "d.wav"
    audio.write_bytes(b"x")
    project.tracks = [Track(id="drums1", name="Drums", type="drums", filename="d.wav", duration_ms=1000)]
    storage.save_project(project)
    client = TestClient(main.app, headers=WRITE_HEADERS)
    r = client.post("/api/presets", json={"plugin": "amplify", "name": "Trim", "params": {"gain_db": -3}})
    assert r.status_code == 200
    assert r.json()["preset"] == "user:Trim"
    r = client.post(f"/api/projects/{project.id}/auto-mix", json={"enabled": True, "style": "balanced"})
    assert r.status_code == 200 and r.json()["auto_mix_enabled"] is True
    r = client.post(f"/api/projects/{project.id}/auto-mix", json={"enabled": False, "style": "balanced"})
    assert r.status_code == 200 and r.json()["auto_mix_enabled"] is False
