import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from compare_multitrack_models import compare, parse_prediction, score


def test_strict_and_agnostic():
    ref = [(0, 60, 0.1, 0.5), (1, 64, 1.0, 1.5)]
    pred = [(0, 60, 0.1, 0.5), (2, 64, 1.0, 1.5)]
    s = score(ref, pred)
    assert s['matched'] == 1
    assert s['matched_ignoring_program_diagnostic'] == 2
    assert s['f1'] == 0.5


def test_no_predictions():
    assert score([(0, 60, 0, 1)], [])['f1'] == 0


@pytest.mark.parametrize('bad', [
    {'notes': [{'is_drum': False, 'program': 0, 'pitch': 60, 'start_time': 2, 'end_time': 1}]},
    {'notes': [{'is_drum': False, 'program': 128, 'pitch': 60, 'start_time': 0, 'end_time': 1}]},
    {'notes': [{'is_drum': False, 'program': 0, 'pitch': 60, 'start_time': float('nan'), 'end_time': 1}]},
    {'foo': []},
])
def test_invalid_notes(tmp_path, bad):
    p = tmp_path / 'prediction.json'
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        parse_prediction(p)
