"""Regression tests for three-iteration r42-r44 batch transaction."""
import json
from pathlib import Path
import wave

from native.vst3_probe import batch_wav_cli


def _manifest(tmp_path: Path) -> Path:
    for i in range(2):
        with wave.open(str(tmp_path / f'in{i}.wav'), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(b'\0\0' * 12)
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'schema': 1, 'jobs': [
        {'source': f'in{i}.wav', 'destination': f'out{i}.wav',
         'plugins': [['plugin.vst3', 'a' * 32]]} for i in range(2)]}))
    return manifest


def test_atomic_batch_stages_before_publication(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    (tmp_path / 'out0.wav').write_bytes(b'old')
    seen = []

    def render(src, dst, plugins, executable, *, timeout):
        seen.append((Path(src), Path(dst)))
        # The original destination must remain untouched through all renders.
        assert (tmp_path / 'out0.wav').read_bytes() == b'old'
        Path(dst).write_bytes(Path(src).read_bytes())

    monkeypatch.setattr(batch_wav_cli, 'render_native_wav', render)
    result = batch_wav_cli.run_batch(manifest, 'probe', atomic_batch=True)
    assert result['status'] == 'ok'
    assert len(seen) == 2
    assert (tmp_path / 'out0.wav').read_bytes() != b'old'
    assert (tmp_path / 'out1.wav').exists()
    assert not list(tmp_path.glob('.mta-*'))


def test_atomic_batch_render_failure_does_not_publish(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    (tmp_path / 'out0.wav').write_bytes(b'old')
    calls = 0

    def render(src, dst, plugins, executable, *, timeout):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError('bad plugin')
        Path(dst).write_bytes(b'new')

    monkeypatch.setattr(batch_wav_cli, 'render_native_wav', render)
    result = batch_wav_cli.run_batch(manifest, 'probe', atomic_batch=True)
    assert result['status'] == 'rolled_back'
    assert (tmp_path / 'out0.wav').read_bytes() == b'old'
    assert not (tmp_path / 'out1.wav').exists()
    assert not list(tmp_path.glob('.mta-*'))


def test_atomic_batch_publication_failure_rolls_back(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    (tmp_path / 'out0.wav').write_bytes(b'old')
    actual_replace = batch_wav_cli.os.replace
    count = 0

    def replace(src, dst):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('publish failure')
        return actual_replace(src, dst)

    def render(src, dst, plugins, executable, *, timeout):
        Path(dst).write_bytes(b'new')

    monkeypatch.setattr(batch_wav_cli, 'render_native_wav', render)
    monkeypatch.setattr(batch_wav_cli.os, 'replace', replace)
    result = batch_wav_cli.run_batch(manifest, 'probe', atomic_batch=True)
    assert result['status'] == 'rolled_back'
    assert (tmp_path / 'out0.wav').read_bytes() == b'old'
    assert not (tmp_path / 'out1.wav').exists()


def test_atomic_dry_run_never_calls_plugin(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    def fail(*args, **kwargs):
        raise AssertionError('plugin invoked in dry-run')
    monkeypatch.setattr(batch_wav_cli, 'render_native_wav', fail)
    result = batch_wav_cli.run_batch(manifest, 'probe', dry_run=True, atomic_batch=True)
    assert result['status'] == 'ready'
