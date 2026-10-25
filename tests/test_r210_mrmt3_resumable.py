"""Resumable MR-MT3 checkpoints: integrity guards only, never claimed model accuracy."""
import pytest
import numpy as np
from scripts.run_mrmt3_resumable import accept_window, atomic_json, budget_exhausted, serializable_tokens


def test_window_roundtrip(tmp_path):
    identity = {'audio_pcm_sha256': 'a' * 64, 'model_sha256': 'b' * 64}
    target = tmp_path / 'window-00000.json'
    payload = {'identity': identity, 'index': 0, 'window_count': 2,
               'tokens': [1, 2, 0], 'start_time': 0.0}
    assert accept_window(target, identity, 0, 2) is None
    atomic_json(target, payload)
    assert accept_window(target, identity, 0, 2) == payload
    with pytest.raises(ValueError, match='does not belong'):
        accept_window(target, {**identity, 'model_sha256': 'c' * 64}, 0, 2)
    with pytest.raises(ValueError, match='does not belong'):
        accept_window(target, identity, 1, 2)


@pytest.mark.parametrize('tokens', [[-1], [1.5], ['1'], [True], None, [1]*8193])
def test_reject_invalid_tokens(tmp_path, tokens):
    target = tmp_path / 'window.json'
    atomic_json(target, {'identity': {}, 'index': 0, 'window_count': 1,
                         'tokens': tokens, 'start_time': 0})
    with pytest.raises(ValueError, match='Invalid tokens'):
        accept_window(target, {}, 0, 1)


def test_reject_corruption_and_bad_time(tmp_path):
    target = tmp_path / 'window.json'
    target.write_text('{broken')
    with pytest.raises(ValueError, match='Corrupted'):
        accept_window(target, {}, 0, 1)
    atomic_json(target, {'identity': {}, 'index': 0, 'window_count': 1,
                         'tokens': [1], 'start_time': -1})
    with pytest.raises(ValueError, match='Invalid start_time'):
        accept_window(target, {}, 0, 1)


def test_time_budget_stops_only_between_completed_windows():
    assert not budget_exhausted(10, 120, 0, 30)
    assert not budget_exhausted(10, 15, 1, 30)
    assert not budget_exhausted(10, 120, 1, 0)
    assert budget_exhausted(10, 40, 1, 30)


def test_numpy_output_tokens_are_serializable():
    assert serializable_tokens(np.array([10, -1, 42], dtype=np.int64)) == [10, 42]


def test_torch_output_tokens_are_serializable():
    torch = pytest.importorskip('torch')
    assert serializable_tokens(torch.tensor([5, -1, 7], dtype=torch.int64)) == [5, 7]


@pytest.mark.parametrize('values', [np.array([[1, 2]]), np.array([1.5]), np.array(['1'])])
def test_reject_invalid_model_token_shape_or_dtype(values):
    with pytest.raises(ValueError, match='non-integral or non-vector'):
        serializable_tokens(values)
