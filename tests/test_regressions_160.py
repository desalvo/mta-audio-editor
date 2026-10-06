from pathlib import Path
import zipfile

from app import music_text as mt
from app.models import LyricLine, LyricWord


def test_lyrics_normalizer_keeps_real_repeated_phrase_at_distinct_times():
    first = LyricLine(
        time_ms=0,
        end_ms=700,
        text="love love",
        words=[
            LyricWord(start_ms=0, end_ms=300, text="love"),
            LyricWord(start_ms=350, end_ms=700, text="love"),
        ],
    )
    repeated = LyricLine(
        time_ms=900,
        end_ms=1600,
        text="love love",
        words=[
            LyricWord(start_ms=900, end_ms=1200, text="love"),
            LyricWord(start_ms=1250, end_ms=1600, text="love"),
        ],
    )
    out = mt._normalize_lyric_items([first, repeated])
    assert len(out) == 2
    assert [x.time_ms for x in out] == [0, 900]
    assert [w.text for w in out[0].words] == ["love", "love"]


def test_lyrics_normalizer_drops_same_audio_duplicate_but_keeps_true_repeat():
    original = LyricLine(time_ms=100, end_ms=800, text="hello again")
    duplicate = LyricLine(time_ms=150, end_ms=820, text="hello again")
    repeat = LyricLine(time_ms=1200, end_ms=1900, text="hello again")
    out = mt._normalize_lyric_items([original, duplicate, repeat])
    assert len(out) == 2
    assert out[0].time_ms == 100
    assert out[1].time_ms == 1200


def test_sample_editor_timer_name_is_consistent():
    js = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text(encoding="utf-8")
    assert "samplePreviewTimer" not in js
    assert "clearTimeout(sampleEditorPreviewTimer);sampleEditorPreviewTimer=null" in js


def test_project_archive_write_is_atomic_and_valid(tmp_path, monkeypatch):
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "workspace").resolve())
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = storage.create_project("Atomic", "MTA16")
    target = tmp_path / "Atomic.maeproj"
    storage.write_project_archive(project.id, target)

    with zipfile.ZipFile(target, "r") as z:
        assert z.testzip() is None
        assert "project/project.json" in z.namelist()

    # No temporary archive is left behind after a successful autosave/sync.
    assert not list(tmp_path.glob(".Atomic.maeproj.*.tmp"))


def test_project_json_save_leaves_no_partial_temp(tmp_path, monkeypatch):
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", (tmp_path / "workspace").resolve())
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = storage.create_project("Atomic JSON", "MTA16")
    project.title = "Updated"
    storage.save_project(project)
    loaded = storage.load_project(project.id)
    assert loaded.title == "Updated"
    assert not list(storage.pdir(project.id).glob(".project.json.*.tmp"))
