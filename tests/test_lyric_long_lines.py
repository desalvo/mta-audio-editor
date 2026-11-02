from app.lyric_layout import lyric_groups, split_long_lyrics
from app.models import LyricLine, LyricWord, LyricSyllable


TEXT = 'Questa è una frase piuttosto lunga, ma dovrebbe essere separata in righe leggibili'


def test_long_lyrics_preserve_every_word_and_syllable_timing():
    words = [LyricWord(text=t, start_ms=1000 + i * 200, end_ms=1150 + i * 200,
        syllables=[LyricSyllable(text=t, start_ms=1000 + i * 200, end_ms=1150 + i * 200)]) for i, t in enumerate(TEXT.split())]
    lines = split_long_lyrics([LyricLine(time_ms=1000, end_ms=5000, text=TEXT, words=words)])
    assert len(lines) > 1 and all(len(x.text) < 40 for x in lines)
    assert ' '.join(x.text for x in lines) == TEXT
    assert [w for x in lines for w in x.words] == words
    assert lines[1].time_ms == lines[1].words[0].start_ms
    assert lines[0].time_ms == 1000 and lines[-1].end_ms == 5000


def test_untimed_lines_guess_inside_next_event_boundary():
    lines = split_long_lyrics([LyricLine(time_ms=1000, text=TEXT), LyricLine(time_ms=7000, text='Fine')])
    assert lines[-1].text == 'Fine'
    assert lines[0].time_ms == 1000
    assert lines[-2].end_ms == 7000
    assert all(a.time_ms < b.time_ms for a, b in zip(lines, lines[1:]))
    assert all(a.end_ms <= b.time_ms for a, b in zip(lines, lines[1:]))


def test_exact_40_characters_split_and_single_long_token_is_kept():
    text = 'a' * 19 + ' ' + 'b' * 20
    assert len(text) == 40
    assert len(lyric_groups(text.split())) == 2
    token = 'x' * 60
    lines = split_long_lyrics([LyricLine(time_ms=0, text=token)])
    assert len(lines) == 1 and lines[0].text == token


def test_mismatched_word_tokens_receive_consistent_estimated_times():
    lines = split_long_lyrics([LyricLine(time_ms=0, end_ms=3000, text=TEXT,
        words=[LyricWord(text='wrong transcript', start_ms=0, end_ms=100)])])
    assert ' '.join(w.text for line in lines for w in line.words) == TEXT
    assert lines[-1].end_ms == 3000
    assert all(w.end_ms >= w.start_ms for line in lines for w in line.words)
