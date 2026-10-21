"""Only explicit non-neural fallback may bypass DrumSep checkpoint policy."""
from app.model_license_policy import selected, evaluate, LicenseDenied


def test_drumsep_explicit_dsp_has_distinct_license_identity():
    assert selected('drumsep', {'model': 'dsp'}) == 'mta-analysis'
    assert selected('drumsep', {}) == 'drumsep-weights'
    assert selected('drumsep', {'model': 'drumsep-onnx'}) == 'drumsep-weights'


def test_drumsep_no_implicit_replacement(monkeypatch, tmp_path):
    from app import model_license_policy as p
    monkeypatch.setattr(p, '_path', lambda: tmp_path / 'policy.json')
    assert evaluate('drumsep', {'model': 'dsp'}).model_id == 'mta-analysis'
    try:
        evaluate('drumsep', {})
    except LicenseDenied:
        pass
    else:
        raise AssertionError('Blocked neural checkpoint was admitted')


def test_dsp_worker_produces_actual_wav_stems(monkeypatch, tmp_path):
    import numpy as np
    import soundfile as sf
    from app import model_license_policy as p
    from app.ai_unified_adapter import infer
    monkeypatch.setattr(p, '_path', lambda: tmp_path / 'policy.json')
    folder = tmp_path / 'job'
    folder.mkdir()
    t = np.arange(8192, dtype=np.float32) / 16000
    sf.write(folder / 'source.wav', np.sin(2*np.pi*440*t)*0.15, 16000)
    infer({'kind': 'drumsep', 'model': 'dsp', 'source_audio': str(folder/'source.wav')}, folder/'output.manifest.json')
    assert (folder/'drums_without_percussions.wav').is_file()
    assert (folder/'percussions.wav').is_file()
    assert (folder/'output.manifest.json').is_file()
