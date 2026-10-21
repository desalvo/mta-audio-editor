"""Offline regression for isolated MIDI worker: never publish partial audio."""
import json
import numpy as np
import pytest
from app.models import Track, InsertPlugin
from app import midi_render


def _run(tmp_path, monkeypatch, fail=False):
    target = tmp_path / 'output.wav'
    target.write_bytes(b'keep-previous-render')
    track = Track(id='test', name='test', filename='a.wav', kind='midi',
                  instrument=InsertPlugin(id='instrument', plugin='gm_soundfont', params={'program': 0}))
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'track': track.model_dump(mode='json'),
                                  'target': str(target), 'rate': 48000, 'duration_ms': 100}))

    class FakeInstrument:
        calls = 0
        def __init__(self, *args, **kwargs): pass
        def read(self, count):
            self.calls += 1
            if fail and self.calls > 1:
                raise RuntimeError('simulated renderer failure')
            return np.zeros((count, 2), dtype=np.float32)
    monkeypatch.setattr(midi_render, 'Instrument', FakeInstrument)
    if fail:
        with pytest.raises(RuntimeError, match='simulated renderer failure'):
            midi_render.run(config)
        assert target.read_bytes() == b'keep-previous-render'
    else:
        assert midi_render.run(config) == 0
        import soundfile as sf
        audio, rate = sf.read(target)
        assert rate == 48000 and audio.shape == (4800, 2)
    assert not list(tmp_path.glob('.mta-midi-*'))


def test_worker_atomic_success(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch)


def test_worker_atomic_failure_preserves_destination(tmp_path, monkeypatch):
    _run(tmp_path, monkeypatch, fail=True)


@pytest.mark.parametrize('duration', [float('nan'), float('inf'), -1, 0, '100'])
def test_worker_rejects_invalid_duration(tmp_path, duration):
    track = Track(id='test', name='test', filename='a.wav', kind='midi',
                  instrument=InsertPlugin(id='instrument', plugin='gm_soundfont', params={'program': 0}))
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'track': track.model_dump(mode='json'), 'target': str(tmp_path/'out.wav'),
                                  'rate': 48000, 'duration_ms': duration}))
    with pytest.raises(ValueError, match='Invalid MIDI render duration'):
        midi_render.run(config)
    assert not (tmp_path/'out.wav').exists()


def test_worker_invalid_pcm_preserves_existing_output(tmp_path, monkeypatch):
    target = tmp_path / 'out.wav'
    target.write_bytes(b'original')
    track = Track(id='test', name='test', filename='a.wav', kind='midi',
                  instrument=InsertPlugin(id='instrument', plugin='gm_soundfont', params={'program': 0}))
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'track': track.model_dump(mode='json'), 'target': str(target),
                                  'rate': 48000, 'duration_ms': 100}))
    class InvalidInstrument:
        def __init__(self, *a, **kw): pass
        def read(self, count): return np.full((count, 2), np.nan, dtype=np.float32)
    monkeypatch.setattr(midi_render, 'Instrument', InvalidInstrument)
    with pytest.raises(RuntimeError, match='invalid audio'):
        midi_render.run(config)
    assert target.read_bytes() == b'original'
    assert not list(tmp_path.glob('.mta-midi-*'))
