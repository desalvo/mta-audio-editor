import json
import pytest
from app.ai_unified_adapter import _artifacts


def test_manifest_published_atomically(tmp_path):
    audio = tmp_path / 'voice.wav'
    audio.write_bytes(b'example')
    _artifacts(tmp_path, [(audio, 'audio/wav')])
    doc = json.loads((tmp_path / 'output.manifest.json').read_text())
    import hashlib
    assert doc['files'] == [{'name': 'voice.wav', 'type': 'audio/wav', 'sha256': hashlib.sha256(b'example').hexdigest()}]
    assert not list(tmp_path.glob('.manifest-*'))


def test_manifest_remains_unchanged_on_invalid_result(tmp_path):
    old = tmp_path / 'output.manifest.json'
    old.write_text('preserve')
    audio = tmp_path / 'voice.wav'
    audio.write_bytes(b'ok')
    with pytest.raises(RuntimeError):
        _artifacts(tmp_path, [(audio, 'audio/wav'), (audio, 'audio/wav')])
    assert old.read_text() == 'preserve'


def test_manifest_rejects_symlink(tmp_path):
    external = tmp_path / 'real.wav'
    external.write_bytes(b'x')
    link = tmp_path / 'link.wav'
    link.symlink_to(external)
    with pytest.raises(RuntimeError):
        _artifacts(tmp_path, [(link, 'audio/wav')])
    assert not (tmp_path / 'output.manifest.json').exists()


def test_manifest_rejects_empty_and_oversized(tmp_path, monkeypatch):
    from app import ai_worker_artifacts
    with pytest.raises(RuntimeError):
        _artifacts(tmp_path, [])
    audio = tmp_path / 'voice.wav'
    audio.write_bytes(b'1234')
    monkeypatch.setattr(ai_worker_artifacts, 'MAX_ARTIFACT_BYTES', 3)
    with pytest.raises(RuntimeError):
        _artifacts(tmp_path, [(audio, 'audio/wav')])


def test_infer_rejects_source_symlink_before_loading_backend(tmp_path):
    from app.ai_unified_adapter import infer
    target = tmp_path / 'external.wav'
    target.write_bytes(b'fake')
    workspace = tmp_path / 'job'
    workspace.mkdir()
    (workspace / 'source.wav').symlink_to(target)
    with pytest.raises(ValueError, match='private job workspace'):
        infer({'kind': 'whisper', 'source_audio': str(workspace / 'source.wav')}, workspace / 'output.wav')


def test_infer_rejects_aliased_source_path(tmp_path):
    from app.ai_unified_adapter import infer
    (tmp_path / 'source.wav').write_bytes(b'fake')
    with pytest.raises(ValueError, match='private job workspace'):
        infer({'kind': 'whisper', 'source_audio': str(tmp_path / './other.wav')}, tmp_path / 'output.wav')


def test_manifest_rejects_external_hardlink(tmp_path):
    from app.ai_unified_adapter import _artifacts
    import os
    import pytest
    external = tmp_path.parent / (tmp_path.name + '-outside.wav')
    external.write_bytes(b'RIFF')
    linked = tmp_path / 'stem.wav'
    os.link(external, linked)
    with pytest.raises(RuntimeError, match='regular file'):
        _artifacts(tmp_path, [(linked, 'audio/wav')])
    assert not (tmp_path / 'output.manifest.json').exists()

def test_infer_rejects_hardlinked_source_before_import(tmp_path):
    from app.ai_unified_adapter import infer
    import os
    import pytest
    external = tmp_path.parent / (tmp_path.name + '-external.wav')
    external.write_bytes(b'RIFF')
    os.link(external, tmp_path / 'source.wav')
    with pytest.raises(ValueError, match='exclusive regular file'):
        infer({'kind': 'whisper', 'source_audio': str(tmp_path / 'source.wav')}, tmp_path / 'output.wav')
