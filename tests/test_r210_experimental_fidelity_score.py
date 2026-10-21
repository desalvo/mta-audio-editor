from app.studio_midi_benchmark import evaluate
from app.music_interchange import MusicResult, MusicPart
from app.models import MidiNote


def score(programs, missing=()):
    ref=MusicResult(parts=[MusicPart(id=f'p{p}',name=f'Program {p}',instrument='gm',program=p,notes=[MidiNote(pitch=60,start_ms=0,duration_ms=200)]) for p in programs])
    pred=MusicResult(parts=[MusicPart(id=f'p{p}',name=f'Program {p}',instrument='gm',program=p,notes=[MidiNote(pitch=60,start_ms=0,duration_ms=200)]) for p in programs if p not in missing]) if any(p not in missing for p in programs) else __import__("app.music_interchange",fromlist=["no_notes"]).no_notes()
    return evaluate(ref,pred)


def test_perfect_ten_instruments_reaches_100():
    r=score(range(10))
    assert r['fidelity_score_0_100']==100
    assert r['at_least_10_instruments_verified']
    assert r['all_reference_instruments_verified']
    assert not r['certified_10_to_16_instruments']


def test_missing_instruments_reduce_fidelity_and_coverage():
    r=score(range(16), missing=tuple(range(6)))
    assert 0<r['fidelity_score_0_100']<100
    assert r['matched_reference_instruments']==10
    assert not r['all_reference_instruments_verified']


def test_empty_prediction_has_zero_score():
    r=score(range(10),missing=tuple(range(10)))
    assert r['fidelity_score_0_100']==0
