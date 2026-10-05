from pathlib import Path
import shutil
import subprocess
import time
import types
import sys

import pytest
from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def test_ui_regressions_for_import_split_tracks_and_transport():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    css = (root / "app/static/app.css").read_text(encoding="utf-8")
    html = (root / "app/templates/index.html").read_text(encoding="utf-8")

    assert "createProjectFromDialog" in js
    assert 'value="MTA8"' in js and 'value="MTA16"' in js
    assert "utility-btn primary" in js
    assert "Importa e separa" in js and "Annulla" in js
    assert ".utility-actions .utility-btn" in css
    assert ".track-select-wrap" in css
    assert "position:static!important" in css
    assert "renameTrack(" in js
    assert "STEREO" in js and "MONO" in js
    assert "lastSelectedAudioFile" in js
    assert "togglePlayback()" in html
    assert "function pausePlayback()" in js
    assert "function resumePlayback()" in js
    assert "e.code==='Space'" in js
    assert "e.key==='Spacebar'" in js
    assert "stopPlayback();else previewMaster()" in js
    assert 'class="nav-item import-action"' in html
    assert ".nav-item.import-action span" in css


def test_native_icons_and_metadata_are_wired():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    installer = (root / "native/windows-installer.iss").read_text(encoding="utf-8")

    for name in ("mta-audio-editor.ico", "mta-audio-editor.icns", "mta-audio-editor-1024.png"):
        assert (root / "native/icons" / name).is_file()

    assert "windows_icon" in spec and "mac_icon" in spec
    assert "CFBundleShortVersionString" in spec
    assert "MTAEditorBuild" in spec
    assert "MTAEditorCreator" in spec
    assert "MTAEditorRepository" in spec
    assert "windows-version-info.txt" in spec
    assert "generate_native_metadata.py" in workflow
    assert "SetupIconFile=icons\\mta-audio-editor.ico" in installer


def test_frozen_demucs_runs_in_process_without_spawning_native_gui(tmp_path, monkeypatch):
    import app.plugins as plugins

    source = tmp_path / "song.mp3"
    source.write_bytes(b"x")
    out = tmp_path / "out"

    monkeypatch.setattr(plugins.DemucsStemSplitter, "available", staticmethod(lambda: True))
    monkeypatch.setattr(plugins.sys, "frozen", True, raising=False)

    separate_mod = types.ModuleType("demucs.separate")
    def fake_main():
        target = out / "htdemucs_6s" / "song"
        target.mkdir(parents=True, exist_ok=True)
        (target / "vocals.wav").write_bytes(b"wav")
        return 0
    separate_mod.main = fake_main
    demucs_mod = types.ModuleType("demucs")
    demucs_mod.separate = separate_mod
    monkeypatch.setitem(sys.modules, "demucs", demucs_mod)
    monkeypatch.setitem(sys.modules, "demucs.separate", separate_mod)
    monkeypatch.setattr(plugins.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not spawn frozen GUI")))

    result = plugins.DemucsStemSplitter.split(source, out, model="htdemucs_6s")
    assert [item.name for item in result] == ["vocals.wav"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_stem_split_without_original_mix_never_adds_original_track(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")

    mp3 = tmp_path / "song.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
         "-ar", "44100", "-ac", "2", "-b:a", "192k", str(mp3)],
        check=True,
    )

    class FakeSplitter:
        @classmethod
        def available(cls):
            return True
        @classmethod
        def status(cls):
            return {"available": True, "models": ["htdemucs_6s"], "recommended_model": "htdemucs_6s"}
        @classmethod
        def split(cls, source, output_dir, model="htdemucs_6s", *, stem_count=0, progress=None, cancel_event=None):
            output_dir.mkdir(parents=True, exist_ok=True)
            out = output_dir / "vocals.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(source), str(out)], check=True)
            return [out]

    monkeypatch.setattr(main, "STEM_SPLITTER", FakeSplitter)
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.clear()

    client = TestClient(main.app, headers=WRITE)
    with mp3.open("rb") as fh:
        response = client.post(
            "/api/stems/jobs?project_title=No%20Original&target=MTA16&model=htdemucs_6s&keep_original_track=false",
            files={"file": ("song.mp3", fh, "audio/mpeg")},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["project"]["target"] == "MTA16"
    assert all(track["name"] != "Original Mix" for track in payload["project"]["tracks"])

    job_id = payload["job"]["id"]
    deadline = time.time() + 8
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/stems/jobs/{job_id}").json()
        if status["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)

    assert status and status["status"] == "completed"
    project = storage.load_project(payload["project"]["id"])
    assert all(track.name != "Original Mix" for track in project.tracks)
    assert [track.name for track in project.tracks] == ["Vocals"]
    assert project.tracks[0].channels == 2
