from pathlib import Path


def test_excluded_chord_round_trip_and_transpose():
    from app.models import Chord, Project
    from app.music_text import transpose_chords

    chord = Chord(time_ms=1200, chord="C", excluded=True)
    project = Project(id="p", title="Song", chords=[chord])
    restored = Project.model_validate_json(project.model_dump_json())
    assert restored.chords[0].excluded is True
    shifted = transpose_chords(restored.chords, 2)[0]
    assert shifted.chord == "D"
    assert shifted.excluded is True


def test_documents_ignore_excluded_chords():
    from app.models import Chord, LyricLine
    from app.music_text import build_chordpro, synchronized_plain_text

    lyrics = [LyricLine(time_ms=1000, text="hello world")]
    chords = [Chord(time_ms=900, chord="C", excluded=True), Chord(time_ms=950, chord="G")]
    text = synchronized_plain_text(lyrics, chords)
    assert "[G]" in text
    assert "[C]" not in text
    chordpro = build_chordpro(title="Song", artist="", key="", bpm=None, lyrics=lyrics, chords=chords)
    assert "[G]" in chordpro
    assert "[C]" not in chordpro


def test_mta_sync_attachments_use_editor_override_and_filter_excluded(tmp_path, monkeypatch):
    import json
    import app.codec as codec
    import app.storage as storage
    from app.models import Chord, LyricLine

    monkeypatch.setattr(storage, "ROOT", tmp_path)
    monkeypatch.setattr(codec, "pdir", storage.pdir)
    project = storage.create_project("Song", "MTA8")
    project.lyrics = [
        LyricLine(time_ms=1000, end_ms=1800, text="hello"),
        LyricLine(time_ms=1801, end_ms=2600, text="world"),
    ]
    project.chords = [
        Chord(time_ms=900, chord="C", excluded=True),
        Chord(time_ms=1700, chord="G", manual_anchor=True, anchor_line_time_ms=1801, anchor_word_index=0, anchor_word_text="world"),
    ]
    codec._synchronized_text_attachments(project)
    adir = storage.pdir(project.id) / "attachments"
    tsv = (adir / "chords-synchronized.tsv").read_text(encoding="utf-8")
    assert "\tG" in tsv
    assert "\tC" not in tsv
    payload = json.loads((adir / "mta-synchronized-text.json").read_text(encoding="utf-8"))
    assert payload["editor_overrides_applied"] is True
    assert [x["text"] for x in payload["lyrics"]] == ["hello", "world"]
    assert [x["chord"] for x in payload["chords"]] == ["G"]
    assert payload["chords"][0]["manual_anchor"] is True


def test_joint_editor_has_exclude_split_merge_and_mta_save():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    css = Path("app/static/app.css").read_text(encoding="utf-8")
    for token in (
        "toggleSelectedLyricsChordExcluded",
        "splitLyricsEditorLine",
        "mergeLyricsEditorLine",
        "lyricsChordsEditorLyricsDraft",
        "Salva editor e sincronizzazione MTA",
        "ch.excluded=!ch.excluded",
    ):
        assert token in js
    assert ".lc-chord.excluded" in css
    assert ".lc-split-word" in css


def test_render_playback_warns_while_master_is_prepared():
    js = Path("app/static/app.js").read_text(encoding="utf-8")
    assert "setRenderPlaybackPreparing(true)" in js
    assert "Preparazione del render in corso, attendere…" in js
    assert "setRenderPlaybackPreparing(false)" in js
