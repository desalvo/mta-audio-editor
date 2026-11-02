"""Readable imported lyric lines, retaining reliable word and syllable timing."""
import re
from .models import LyricWord


CONJUNCTIONS = {'e', 'ma', 'o', 'però', 'perché', 'quando', 'mentre', 'che',
                'and', 'but', 'or', 'because', 'when', 'et', 'mais', 'ou'}


def lyric_groups(tokens, limit=40):
    text = ' '.join(tokens)
    if len(text) < limit or len(tokens) < 2:
        return [tokens]
    def score(i):
        left = ' '.join(tokens[:i])
        right = ' '.join(tokens[i:])
        return (abs(len(left) - len(text) / 2)
                - (5 if re.search(r'[,.;:!?]$', left) else 0)
                - (3 if tokens[i].casefold() in CONJUNCTIONS else 0)
                + (10 if min(len(left), len(right)) < 4 else 0))
    split = min(range(1, len(tokens)), key=score)
    return lyric_groups(tokens[:split], limit) + lyric_groups(tokens[split:], limit)


def split_long_lyrics(lines):
    result = []
    for index, line in enumerate(lines):
        tokens = line.text.split()
        groups = lyric_groups(tokens)
        if len(groups) == 1:
            result.append(line)
            continue
        start = line.time_ms
        next_start = lines[index + 1].time_ms if index + 1 < len(lines) else None
        end = (line.end_ms if line.end_ms is not None and line.end_ms > start else
               next_start if next_start is not None and next_start > start else
               start + max(2000, len(tokens) * 300))
        timed = (len(line.words) == len(tokens)
                 and all(w.text.strip() == t and w.end_ms >= w.start_ms >= start
                         for w, t in zip(line.words, tokens))
                 and all(a.end_ms <= b.start_ms for a, b in zip(line.words, line.words[1:])))
        words = line.words if timed else [LyricWord(text=text,
            start_ms=round(start + (end - start) * i / len(tokens)),
            end_ms=round(start + (end - start) * (i + 1) / len(tokens))) for i, text in enumerate(tokens)]
        offset = 0
        for i, group in enumerate(groups):
            chunk = words[offset:offset + len(group)]
            offset += len(group)
            begin = start if i == 0 else chunk[0].start_ms
            finish = max(chunk[-1].end_ms, end) if i == len(groups) - 1 else chunk[-1].end_ms
            result.append(line.model_copy(deep=True, update={
                'text': ' '.join(group), 'time_ms': begin, 'end_ms': finish,
                'words': [w.model_copy(deep=True) for w in chunk]}))
    return result
