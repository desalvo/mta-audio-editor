import numpy as np

from app.models import Chord, Clip, LyricLine, LyricSyllable, LyricWord, Track
from app import music_text as mt


def test_transpose_helpers_cover_sharps_flats_and_slash_bass():
    assert mt.transpose_chord_symbol("Cmaj7/G", 2) == "Dmaj7/A"
    assert mt.transpose_chord_symbol("Bb7/F", 2) == "C7/G"
    assert mt.transpose_chord_symbol("N.C.", 2) == "N.C."
    assert mt.transpose_key_name("Eb minor", 2) == "F minor"
    assert mt.transpose_key_name("", 2) == ""
    assert mt.transpose_key_name("mode unknown", 2) == "mode unknown"


def test_normalize_lyrics_deduplicates_segment_and_word_entries():
    a = LyricLine(
        time_ms=0,
        end_ms=500,
        text="  Hello   world ",
        words=[
            LyricWord(start_ms=0, end_ms=100, text=" Hello "),
            LyricWord(start_ms=0, end_ms=100, text=" Hello "),
        ],
    )
    b = LyricLine(
        time_ms=100,
        end_ms=700,
        text="hello world",
        words=[LyricWord(start_ms=120, end_ms=300, text="world")],
    )
    out = mt._normalize_lyric_items([b, a])
    assert len(out) == 1
    assert out[0].time_ms == 0
    assert out[0].end_ms == 700
    assert [w.text for w in out[0].words] == ["Hello", "world"]


def test_syllable_parts_handles_punctuation_vowels_and_empty_values():
    assert mt._syllable_parts("") == []
    assert mt._syllable_parts("!!!") == ["!!!"]
    assert mt._syllable_parts("hello!")[-1].endswith("!")
    assert "" not in mt._syllable_parts("musica")


def test_snap_to_energy_minimum_covers_empty_short_and_real_window():
    assert mt._snap_to_energy_minimum(np.zeros(0, dtype=np.float32), 16000, 123) == 123
    assert mt._snap_to_energy_minimum(np.zeros(10, dtype=np.float32), 16000, 0) == 0
    samples = np.ones(16000, dtype=np.float32)
    samples[7900:8100] = 0.0
    snapped = mt._snap_to_energy_minimum(samples, 16000, 500, 80)
    assert 420 <= snapped <= 580


def test_forced_align_lyrics_adds_syllable_timing(monkeypatch, tmp_path):
    samples = np.ones(32000, dtype=np.float32)
    samples[0:100] = 0
    samples[7800:8100] = 0
    samples[15800:16100] = 0
    monkeypatch.setattr(mt, "_pcm_mono", lambda path, sample_rate=16000: (samples, 16000))
    items = [
        LyricLine(
            time_ms=0,
            end_ms=1000,
            text="Musica bella",
            words=[
                LyricWord(start_ms=0, end_ms=500, text="Musica"),
                LyricWord(start_ms=500, end_ms=1000, text="bella"),
            ],
        )
    ]
    out = mt.forced_align_lyrics(tmp_path / "unused.wav", items)
    assert len(out) == 1
    assert len(out[0].words) == 2
    assert out[0].words[0].syllables
    assert out[0].words[1].start_ms >= out[0].words[0].end_ms


def test_forced_align_lyrics_falls_back_when_pcm_extraction_fails(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise RuntimeError("no ffmpeg")
    monkeypatch.setattr(mt, "_pcm_mono", fail)
    items = [LyricLine(time_ms=10, end_ms=300, text="Hi", words=[LyricWord(start_ms=10, end_ms=300, text="Hi")])]
    out = mt.forced_align_lyrics(tmp_path / "x.wav", items)
    assert out[0].text == "Hi"
    assert out[0].words[0].end_ms >= out[0].words[0].start_ms


def test_lyrics_transcribe_kwargs_and_offset_preserve_syllables(monkeypatch):
    monkeypatch.setenv("MTA_LYRICS_BEAM_SIZE", "5")
    kwargs = mt._lyrics_transcribe_kwargs("it", "cuda")
    assert kwargs["word_timestamps"] is True
    assert kwargs["condition_on_previous_text"] is False
    assert kwargs["fp16"] is True
    assert kwargs["language"] == "it"
    item = LyricLine(
        time_ms=10,
        end_ms=100,
        text="ciao",
        words=[LyricWord(start_ms=10, end_ms=100, text="ciao", syllables=[LyricSyllable(start_ms=10, end_ms=55, text="ci"), LyricSyllable(start_ms=55, end_ms=100, text="ao")])],
    )
    out = mt._offset_lyrics([item], 200)[0]
    assert out.time_ms == 210 and out.end_ms == 300
    assert out.words[0].syllables[1].start_ms == 255


def test_synchronized_text_and_chordpro_cover_word_and_segment_modes():
    lyrics = [
        LyricLine(time_ms=0, end_ms=900, text="hello world", words=[LyricWord(start_ms=0, end_ms=400, text="hello"), LyricWord(start_ms=450, end_ms=900, text="world")]),
        LyricLine(time_ms=1000, end_ms=1500, text="again", words=[]),
    ]
    chords = [Chord(time_ms=0, chord="C"), Chord(time_ms=500, chord="G"), Chord(time_ms=1000, chord="Am")]
    txt = mt.synchronized_plain_text(lyrics, chords)
    assert "[00:00.00][C] hello world" in txt
    cp = mt.build_chordpro(title="Song", artist="Artist", key="C", bpm=120, lyrics=lyrics, chords=chords, authors=["A"])
    assert "{title: Song}" in cp
    assert "[C]" in cp and "[Am]again" in cp


def test_map_source_events_to_timeline_maps_word_and_syllable_offsets():
    track = Track(id="t", name="T", filename="x.wav", clips=[Clip(id="c", timeline_start_ms=1000, source_start_ms=200, source_end_ms=1200)])
    lyric = LyricLine(time_ms=300, end_ms=700, text="word", words=[LyricWord(start_ms=300, end_ms=700, text="word", syllables=[LyricSyllable(start_ms=300, end_ms=500, text="wo")])])
    chord = Chord(time_ms=400, chord="C")
    mapped = mt.map_source_events_to_timeline(track, [lyric])
    assert mapped[0].time_ms == 1100
    assert mapped[0].words[0].start_ms == 1100
    assert mapped[0].words[0].syllables[0].start_ms == 1100
    cm = mt.map_source_events_to_timeline(track, [chord])
    assert cm[0].time_ms == 1200


def test_whisper_result_to_lines_parses_segments_and_words():
    result = {
        "segments": [
            {"start": 0.1, "end": 0.8, "text": " hello ", "words": [
                {"start": 0.1, "end": 0.4, "word": "hello"},
                {"start": 0.4, "end": 0.8, "word": "world"},
            ]},
            {"start": 1.0, "end": 1.2, "text": "   ", "words": []},
        ]
    }
    lines = mt._whisper_result_to_lines(result)
    assert len(lines) == 1
    assert lines[0].time_ms == 100
    assert lines[0].end_ms == 800
    assert [w.text for w in lines[0].words] == ["hello", "world"]


def test_native_ai_device_forced_and_transcribe_kwargs_cpu(monkeypatch):
    monkeypatch.setenv("MTA_AI_DEVICE", "cpu-custom")
    assert mt.native_ai_device() == "cpu-custom"
    kwargs = mt._lyrics_transcribe_kwargs(None, "cpu")
    assert kwargs["fp16"] is False
    assert "language" not in kwargs


def test_duration_seconds_success_and_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(mt, "_run", lambda cmd: "12.5\n")
    assert mt._duration_seconds(tmp_path / "a.wav") == 12.5
    monkeypatch.setattr(mt, "_run", lambda cmd: (_ for _ in ()).throw(RuntimeError("x")))
    assert mt._duration_seconds(tmp_path / "a.wav") == 0.0


def test_madmom_normalize_and_rows_to_events_deduplicate():
    assert mt._normalize_madmom_chord("C:maj") == "C"
    assert mt._normalize_madmom_chord("A:min") == "Am"
    assert mt._normalize_madmom_chord("N") == ""
    rows = [(0.0, 1.0, "C:maj"), (1.0, 2.0, "C:maj"), (2.0, 3.0, "A:min"), ("bad", 4.0, "G:maj"), (5.0, 6.0, "N")]
    out = mt._madmom_rows_to_events(rows, 100)
    assert [(x.time_ms, x.chord) for x in out] == [(100, "C"), (2100, "Am")]


def test_extract_chords_rejects_unknown_and_missing_chordino(monkeypatch, tmp_path):
    with __import__('pytest').raises(ValueError):
        mt.extract_chords(tmp_path / "x.wav", engine="unknown")
    monkeypatch.setattr(mt, "_extract_chords_chordino", lambda path: None)
    with __import__('pytest').raises(RuntimeError):
        mt.extract_chords(tmp_path / "x.wav", engine="chordino")


def test_extract_chords_short_audio_error(monkeypatch, tmp_path):
    monkeypatch.setattr(mt, "_pcm_mono", lambda path: (np.zeros(100, dtype=np.float32), 1000))
    with __import__('pytest').raises(ValueError):
        mt.extract_chords(tmp_path / "x.wav", engine="mta-chromagram")


def test_synchronized_plain_text_empty_and_active_chord_progression():
    assert mt.synchronized_plain_text([], []) == ""
    lyrics = [LyricLine(time_ms=1000, end_ms=1400, text="one"), LyricLine(time_ms=2000, end_ms=2400, text="two")]
    chords = [Chord(time_ms=500, chord="Dm"), Chord(time_ms=1500, chord="G")]
    out = mt.synchronized_plain_text(lyrics, chords)
    assert "[Dm] one" in out
    assert "[G] two" in out


def test_build_lyrics_pdf_covers_word_syllable_chord_and_rights_layout(tmp_path):
    from app.models import RightsRecord
    lyrics = [
        LyricLine(
            time_ms=0,
            end_ms=1400,
            text="musica bella",
            words=[
                LyricWord(start_ms=0, end_ms=650, text="musica", syllables=[LyricSyllable(start_ms=0, end_ms=250, text="mu"), LyricSyllable(start_ms=250, end_ms=650, text="sica")]),
                LyricWord(start_ms=700, end_ms=1400, text="bella", syllables=[LyricSyllable(start_ms=700, end_ms=1000, text="bel"), LyricSyllable(start_ms=1000, end_ms=1400, text="la")]),
            ],
        ),
        LyricLine(time_ms=1500, end_ms=2200, text="plain segment", words=[]),
    ]
    chords = [Chord(time_ms=0, chord="C"), Chord(time_ms=320, chord="G"), Chord(time_ms=900, chord="Am"), Chord(time_ms=1600, chord="F")]
    rights = [RightsRecord(uid="SIAE:T-1", society="SIAE", title="Song", original_title="SONG", authors=["Writer"], performers=["Singer"], publishers=["Pub"], identifiers={"ISWC":"T-1"}, source_url="https://example.invalid/work")]
    out = mt.build_lyrics_pdf(tmp_path / "lyrics.pdf", title="Song", artist="Artist", lyrics=lyrics, chords=chords, key="C", bpm=123.6, rights_records=rights)
    assert out.is_file() and out.stat().st_size > 500
