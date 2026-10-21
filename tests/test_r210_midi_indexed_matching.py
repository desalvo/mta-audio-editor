"""Exact matching parity and high-density passages for indexed MIDI benchmark."""
import random
import pytest
from app.studio_midi_benchmark import _match, evaluate


def _brute_match(reference, prediction, onset, offset):
    adjacency = [sorted((j for j, (rp, rs, re) in enumerate(reference)
                         if pitch == rp and abs(start-rs) <= onset and abs(end-re) <= offset),
                        key=lambda j: (abs(start-reference[j][1])+abs(end-reference[j][2]), j))
                 for pitch, start, end in prediction]
    assigned = {}
    for source in range(len(prediction)):
        queue = [source]
        previous = {source: None}
        discovered = set()
        finish = None
        head = 0
        while head < len(queue) and finish is None:
            candidate = queue[head]
            head += 1
            for ref in adjacency[candidate]:
                if ref in discovered:
                    continue
                discovered.add(ref)
                if ref not in assigned:
                    finish = (candidate, ref)
                    break
                alternate = assigned[ref]
                if alternate not in previous:
                    previous[alternate] = (candidate, ref)
                    queue.append(alternate)
        if finish:
            candidate, ref = finish
            while True:
                assigned[ref] = candidate
                prior = previous[candidate]
                if prior is None:
                    break
                candidate, ref = prior
    return len(assigned)


def test_indexed_matching_agrees_with_exhaustive_for_random_polyphony():
    rng = random.Random(20261020)
    for _ in range(100):
        reference = [(rng.randrange(48, 56), rng.randrange(0, 1200), rng.randrange(1200, 2100))
                     for _ in range(rng.randrange(0, 35))]
        prediction = [(rng.randrange(48, 56), rng.randrange(0, 1200), rng.randrange(1200, 2100))
                      for _ in range(rng.randrange(0, 35))]
        assert _match(reference, prediction, 100, 130) == _brute_match(reference, prediction, 100, 130)


def test_indexed_matching_many_distinct_onsets():
    notes = [(60 + n % 12, n * 250, n * 250 + 180) for n in range(5000)]
    assert _match(notes, notes, 50, 100) == len(notes)


@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), float('-inf')])
def test_benchmark_rejects_nonfinite_tolerances(invalid):
    from app.music_interchange import MusicResult, MusicPart
    from app.models import MidiNote
    empty = MusicResult(parts=[MusicPart(id="p", name="Piano", program=0, percussion=False, notes=[MidiNote(id="n",pitch=60,start_ms=0,duration_ms=100)])])
    with pytest.raises(ValueError, match='tolerance'):
        evaluate(empty, empty, onset_ms=invalid)
    with pytest.raises(ValueError, match='tolerance'):
        evaluate(empty, empty, offset_ms=invalid)
