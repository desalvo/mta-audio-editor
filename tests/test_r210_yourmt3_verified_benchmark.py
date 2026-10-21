"""Offline contract coverage for verified YourMT3+ benchmark export."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_yourmt3_verified_benchmark.py'
spec = importlib.util.spec_from_file_location('yourmt3_benchmark', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_prediction_converts_notes_and_percussion():
    result = SimpleNamespace(parts=[
        SimpleNamespace(percussion=False, program=4, notes=[SimpleNamespace(pitch=64, start_ms=1250, duration_ms=500)]),
        SimpleNamespace(percussion=True, program=None, notes=[SimpleNamespace(pitch=36, start_ms=2000, duration_ms=300)]),
    ])
    assert module.prediction(result) == {'notes': [
        {'program': 4, 'is_drum': False, 'pitch': 64, 'start_time': 1.25, 'end_time': 1.75},
        {'program': 0, 'is_drum': True, 'pitch': 36, 'start_time': 2, 'end_time': 2.3},
    ]}


def test_prediction_rejects_unknown_melodic_instrument():
    result = SimpleNamespace(parts=[SimpleNamespace(percussion=False, program=None, notes=[SimpleNamespace(pitch=60)])])
    with pytest.raises(ValueError, match='GM program'):
        module.prediction(result)


def test_checksum_is_chunked(tmp_path):
    from hashlib import sha256
    p = tmp_path/'fixture'
    p.write_bytes(b'abc' * 100)
    assert module.file_hash(p) == sha256(p.read_bytes()).hexdigest()
