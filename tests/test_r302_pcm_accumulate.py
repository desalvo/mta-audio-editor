import math
import pytest
from app.native_dsp import pcm_accumulate


def test_pcm_mix_reference():
    out = pcm_accumulate([.25, -.5, 0, 1], [.5, 1, -1, 0], .5, channels=2)
    assert out == pytest.approx([.5, 0, -.5, 1], abs=1e-6)


@pytest.mark.parametrize('dest,src,gain,channels', [
    ([], [], 1, 1), ([1], [1, 2], 1, 1), ([1], [1], math.nan, 1),
    ([1], [1], 1, 0), ([float('inf')], [1], 1, 1),
])
def test_pcm_mix_rejects_invalid(dest, src, gain, channels):
    with pytest.raises(ValueError):
        pcm_accumulate(dest, src, gain, channels)
