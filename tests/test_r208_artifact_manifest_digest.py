"""Producer/consumer agreement on durable artifact contents."""
import hashlib
import json
import pytest
from app.ai_unified_adapter import _artifacts
from app.ai_worker_artifacts import package_artifacts


def test_digest_passes_from_producer_to_consumer(tmp_path):
    artifact = tmp_path / 'notes.txt'
    artifact.write_text('generated text', encoding='utf-8')
    _artifacts(tmp_path, [(artifact, 'text/plain')])
    manifest = json.loads((tmp_path / 'output.manifest.json').read_text())
    assert manifest['files'][0]['sha256'] == hashlib.sha256(b'generated text').hexdigest()
    content, media = package_artifacts(tmp_path)
    assert content and media == 'application/zip'


def test_digest_detects_mutation_even_when_size_is_preserved(tmp_path):
    artifact = tmp_path / 'notes.txt'
    artifact.write_bytes(b'original')
    _artifacts(tmp_path, [(artifact, 'text/plain')])
    artifact.write_bytes(b'altered!')
    with pytest.raises(ValueError, match='checksum mismatch'):
        package_artifacts(tmp_path)


def test_digest_rejects_invalid_format(tmp_path):
    artifact = tmp_path / 'notes.txt'
    artifact.write_bytes(b'original')
    (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [{'name': 'notes.txt', 'type': 'text/plain', 'sha256': 'x'*64}]}))
    with pytest.raises(ValueError, match='checksum mismatch'):
        package_artifacts(tmp_path)
