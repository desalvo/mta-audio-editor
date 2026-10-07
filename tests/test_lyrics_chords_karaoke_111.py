from pathlib import Path
from types import SimpleNamespace

from app.models import Chord, LyricLine, LyricWord, Project
from app.music_text import _whisper_result_to_lines, build_karaoke_ass


def test_whisper_word_timestamps_are_preserved():
    rows = _whisper_result_to_lines({"segments": [{"start": 1.0, "end": 2.5, "text": "hello world", "words": [
        {"start": 1.0, "end": 1.4, "word": "hello"}, {"start": 1.5, "end": 2.1, "word": "world"}
    ]}]})
    assert rows[0].time_ms == 1000
    assert rows[0].end_ms == 2500
    assert [(w.start_ms, w.end_ms, w.text) for w in rows[0].words] == [(1000, 1400, "hello"), (1500, 2100, "world")]


def test_karaoke_ass_contains_word_level_karaoke_and_chords(tmp_path: Path):
    out = tmp_path / "karaoke.ass"
    lyric = LyricLine(time_ms=1000, end_ms=3000, text="hello world", words=[
        LyricWord(start_ms=1000, end_ms=1500, text="hello"),
        LyricWord(start_ms=1600, end_ms=2200, text="world"),
    ])
    build_karaoke_ass(out, title="Song", artist="Artist", lyrics=[lyric], chords=[Chord(time_ms=900, chord="C")])
    text = out.read_text(encoding="utf-8-sig")
    assert "{\\kf50}hello" in text
    assert "{\\kf60}world" in text
    assert ",Chord," in text and "C" in text
    assert "Song · Artist" in text


def test_karaoke_ass_line_level_and_can_hide_chords(tmp_path: Path):
    out = tmp_path / "plain.ass"
    build_karaoke_ass(
        out, title="", artist="", lyrics=[LyricLine(time_ms=0, text="line")],
        chords=[Chord(time_ms=0, chord="Am")], include_chords=False,
    )
    text = out.read_text(encoding="utf-8-sig")
    assert "{\\kf" in text
    assert ",Chord," not in text


def test_chordino_backend_parses_stdout(monkeypatch, tmp_path: Path):
    import app.music_text as mt
    import app.chordino_runtime as cr
    monkeypatch.setattr(cr, "chordino_status", lambda: {"available": True, "host": "/usr/bin/sonic-annotator", "host_kind": "sonic-annotator", "plugin": True})
    monkeypatch.setattr(cr, "chordino_host_path", lambda: "/usr/bin/sonic-annotator")
    monkeypatch.setattr(cr, "host_kind", lambda path=None: "sonic-annotator")
    monkeypatch.setattr(
        mt.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout='file,0.000,"C"\nfile,1.000,"G"\nfile,2.000,"G"\n', stderr=""),
    )
    result = mt._extract_chords_chordino(tmp_path / "song.wav")
    assert [(x.time_ms, x.chord) for x in result] == [(0, "C"), (1000, "G")]


def test_extract_lyrics_python_backend_high_accuracy(monkeypatch, tmp_path: Path):
    import sys
    import app.music_text as mt

    audio = tmp_path / "x.wav"
    audio.write_bytes(b"x")

    class Model:
        def transcribe(self, path, **kwargs):
            assert kwargs["word_timestamps"] is True
            assert kwargs["beam_size"] >= 8
            assert kwargs["patience"] >= 1.0
            return {"segments": [{"start": 0.2, "end": 1.0, "text": "Hi", "words": [{"start": 0.2, "end": 0.7, "word": "Hi"}]}]}

    fake = SimpleNamespace(load_model=lambda name, download_root=None: Model())
    monkeypatch.setitem(sys.modules, "whisper", fake)
    original_find_spec = mt.importlib.util.find_spec
    monkeypatch.setattr(mt.importlib.util, "find_spec", lambda name: object() if name == "whisper" else original_find_spec(name))
    rows = mt.extract_lyrics(audio, model_name="large-v3")
    assert rows[0].words[0].text == "Hi"


def test_ui_exposes_import_analysis_pdf_color_and_mp4_chords():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "stemExtractLyrics" in js
    assert "stemExtractChords" in js
    assert "extract_lyrics=${extractLyrics}" in js
    assert "extract_chords=${extractChords}" in js
    assert "lyricsPdfChordColor" in js
    assert "MP4 Karaoke" in js
    assert "exportKaraokeBackground" in js
    assert "karaokeIncludeChords" in js
    assert "include_chords=${includeChords}" in js
    assert "L’export MP4 richiede lyrics sincronizzate" in js


def test_backend_exposes_dedicated_karaoke_endpoint_and_analysis_flags():
    main = Path("app/main.py").read_text(encoding="utf-8")
    assert '"/api/projects/{pid}/karaoke-export-jobs"' in main
    assert "include_chords: bool = True" in main
    assert "extract_lyrics: bool = False" in main
    assert "extract_chords: bool = False" in main
    assert "vocal_stem" in main
    assert '"analysis": job.get("analysis", {})' in main
    assert "L'export MP4 richiede lyrics sincronizzate" in main


def test_karaoke_worker_passes_chords_and_include_flag(monkeypatch, tmp_path: Path):
    import app.main as main

    project = Project(
        id="a" * 12, title="Song", artist="Artist",
        lyrics=[LyricLine(time_ms=0, text="hello")],
        chords=[Chord(time_ms=0, chord="C")],
    )
    monkeypatch.setattr(main, "load_project", lambda pid: project)
    monkeypatch.setattr(main, "pdir", lambda pid: tmp_path)
    monkeypatch.setattr(main, "audio_path", lambda *a: tmp_path / "unused.wav")
    monkeypatch.setattr(main, "render_mix", lambda project, resolver, out, **kwargs: out.write_bytes(b"wav"))
    seen = {}

    def fake_ass(out, **kwargs):
        seen.update(kwargs)
        out.write_text("ass", encoding="utf-8")
        return out

    monkeypatch.setattr(main, "build_karaoke_ass", fake_ass)
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stderr=""))
    updates = []
    monkeypatch.setattr(main, "_media_job_update", lambda job_id, **changes: updates.append(changes))

    # ffmpeg is mocked, so create the expected output in the subprocess shim.
    def fake_run(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"mp4")
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr(main.subprocess, "run", fake_run)

    main._karaoke_export_worker("job", project.id, None, False)
    assert seen["chords"] == project.chords
    assert seen["include_chords"] is False
    assert updates[-1]["status"] == "completed"


def test_karaoke_worker_rejects_projects_without_lyrics(monkeypatch, tmp_path: Path):
    import app.main as main
    project = Project(id="b" * 12, title="No lyrics")
    monkeypatch.setattr(main, "load_project", lambda pid: project)
    updates = []
    monkeypatch.setattr(main, "_media_job_update", lambda job_id, **changes: updates.append(changes))
    main._karaoke_export_worker("job", project.id, None, True)
    assert updates[-1]["status"] == "failed"
    assert "lyrics" in updates[-1]["error"].lower()


def test_ios_local_import_and_separate_runs_optional_text_analysis():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "runTextAnalysisAndWait" in js
    assert "extractLyrics=false,extractChords=false" in js
    assert "vocal?.id||original?.id" in js
    assert "original?.id||vocal?.id" in js


def test_extract_lyrics_cli_backend_uses_upstream_model_cache(monkeypatch, tmp_path: Path):
    import app.music_text as mt

    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"audio")
    monkeypatch.setattr(mt.importlib.util, "find_spec", lambda name: None if name == "whisper" else None)
    monkeypatch.setattr(mt.shutil, "which", lambda name: "/usr/bin/whisper" if name == "whisper" else None)

    def fake_run(cmd):
        out_dir = Path(cmd[cmd.index("--output_dir") + 1])
        (out_dir / "voice.json").write_text(
            '{"segments":[{"start":0.0,"end":1.0,"text":"hello","words":[{"start":0.0,"end":0.5,"word":"hello"}]}]}',
            encoding="utf-8",
        )

    monkeypatch.setattr(mt, "_run", fake_run)
    rows = mt.extract_lyrics(audio, model_name="large-v3", language="en")
    assert rows[0].text == "hello"
    assert rows[0].words[0].end_ms == 500
