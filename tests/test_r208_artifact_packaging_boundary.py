"""Consumer-side manifest/package boundaries for externally controlled worker outputs."""
import json
import os
import pytest
from app.ai_worker_artifacts import package_artifacts


def test_reject_hardlinked_artifact(tmp_path):
    outside = tmp_path.parent / ('outside-' + tmp_path.name + '.txt')
    outside.write_text('private')
    try:
        os.link(outside, tmp_path / 'notes.txt')
        (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [{'name': 'notes.txt', 'type': 'text/plain'}]}))
        with pytest.raises(ValueError, match='private regular file'):
            package_artifacts(tmp_path)
    finally:
        outside.unlink(missing_ok=True)


def test_reject_symlinked_manifest(tmp_path):
    target = tmp_path / 'manifest.json'
    target.write_text(json.dumps({'version': 1, 'files': []}))
    (tmp_path / 'output.manifest.json').symlink_to(target)
    with pytest.raises(ValueError, match='safely opened'):
        package_artifacts(tmp_path)


def test_reject_symlinked_output_artifact(tmp_path):
    target = tmp_path / 'actual.txt'
    target.write_text('content')
    (tmp_path / 'notes.txt').symlink_to(target)
    (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [{'name': 'notes.txt', 'type': 'text/plain'}]}))
    with pytest.raises(ValueError, match='safely opened'):
        package_artifacts(tmp_path)


def test_reject_hardlinked_legacy_wav(tmp_path):
    outside = tmp_path.parent / ('legacy-' + tmp_path.name + '.wav')
    outside.write_bytes(b'RIFF'+bytes(100))
    try:
        os.link(outside, tmp_path / 'preview.wav')
        with pytest.raises(ValueError, match='private regular file'):
            package_artifacts(tmp_path)
    finally:
        outside.unlink(missing_ok=True)
