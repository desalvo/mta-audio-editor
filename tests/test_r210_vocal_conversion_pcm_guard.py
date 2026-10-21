"""PCM guards are applied after resampling and blending, not only on raw output."""
import numpy as np
import pytest
from app.vocal_conversion import _check_pcm

@pytest.mark.parametrize('bad', [[], [float('nan')], [float('inf')], [1.02], [-1.02], [1.005], [-1.005]])
def test_reject_invalid_or_clipped_converted_pcm(bad):
    with pytest.raises(ValueError, match='invalid or clipped PCM'):
        _check_pcm(np.array(bad, dtype=np.float32), 'Resampled conversion output')

def test_accept_finite_valid_pcm():
    _check_pcm(np.array([-1.0, 0., 0.5, 1.0], dtype=np.float32), 'Converted blend')


def test_reject_empty_channel_axis_and_non_numeric_pcm():
    for bad in (np.empty((2, 0), dtype=np.float32),
                np.empty((0, 2), dtype=np.float32),
                np.array([['n/a']], dtype=str),
                np.array([0.5+0.5j], dtype=np.complex64),
                np.zeros((1, 2, 3), dtype=np.float32)):
        with pytest.raises(ValueError, match='invalid or clipped PCM'):
            _check_pcm(bad, 'Converted blend')
