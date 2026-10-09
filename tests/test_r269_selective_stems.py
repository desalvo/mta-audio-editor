from pathlib import Path
import numpy as np
import soundfile as sf
from app.main import _split_drums_percussions, _STEM_TARGETS


def test_r269_targets_and_workflow():
    source = Path('app/static/app.js').read_text()
    assert {'all','lead_vocals','percussions','drums_without_percussions','other'} <= _STEM_TARGETS
    for target in ['lead_vocals','percussions','drums_without_percussions','other']:
        assert f'value="{target}"' in source
    assert 'split_percussions:String(splitPercussions)' in source
    assert 'stem_targets:stemTargets' in source


def test_r269_percussion_split_is_complementary(tmp_path):
    rate = 8000
    t = np.arange(rate, dtype=np.float32) / rate
    source = (.15*np.sin(2*np.pi*120*t)).astype('float32')
    source[::800] += .65
    stereo = np.column_stack([source,source])
    inp=tmp_path/'drums.wav'
    sf.write(inp, stereo, rate, subtype='FLOAT')
    body, perc = _split_drums_percussions(inp,tmp_path/'result')
    a,_=sf.read(body,always_2d=True);b,_=sf.read(perc,always_2d=True)
    assert len(a)==len(b)==len(stereo)
    assert np.max(np.abs((a+b)-stereo)) < 1e-3
