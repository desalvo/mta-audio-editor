import hashlib
import pytest
from app import uvr_kara_integrity as integrity


def test_checkpoint_repair_is_atomic_and_skips_valid(tmp_path, monkeypatch):
    content = b'known-official-fixture'
    monkeypatch.setattr(integrity, 'UVR_KARA_2_SHA256', hashlib.sha256(content).hexdigest())
    target = tmp_path / 'UVR_MDXNET_KARA_2.onnx'
    target.write_bytes(b'wrong file')
    called = []
    def download(directory):
        called.append(True)
        (directory / target.name).write_bytes(content)
    assert integrity.ensure_kara_2(target, download) == hashlib.sha256(content).hexdigest()
    assert target.read_bytes() == content
    integrity.ensure_kara_2(target, download)
    assert len(called) == 1


def test_invalid_download_never_replaces_existing(tmp_path):
    target = tmp_path / 'UVR_MDXNET_KARA_2.onnx'
    target.write_bytes(b'old invalid')
    with pytest.raises(ValueError, match='SHA-256'):
        integrity.ensure_kara_2(target, lambda directory: (directory / target.name).write_bytes(b'new invalid'))
    assert target.read_bytes() == b'old invalid'


def test_symlink_is_not_replaced(tmp_path):
    dest = tmp_path / 'dest'
    dest.write_bytes(b'invalid')
    target = tmp_path / 'UVR_MDXNET_KARA_2.onnx'
    target.symlink_to(dest)
    with pytest.raises(ValueError, match='symlink'):
        integrity.ensure_kara_2(target, lambda directory: (directory / target.name).write_bytes(b'other'))
