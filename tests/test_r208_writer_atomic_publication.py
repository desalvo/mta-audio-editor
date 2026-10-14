"""Regression coverage for r208 Matroska/MTA atomic publication."""
import shutil
import subprocess

import pytest

from app.mta_writer import normalize_matroska_for_mta


@pytest.fixture
def matroska(tmp_path):
    if shutil.which('ffmpeg') is None:
        pytest.skip('ffmpeg unavailable')
    source = tmp_path / 'source.mka'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:duration=0.3', '-c:a', 'libmp3lame',
                    '-f', 'matroska', str(source)], check=True)
    return source


def test_writer_preserves_existing_target_on_replace_failure(matroska, tmp_path, monkeypatch):
    import app.mta_writer as writer
    target = tmp_path / 'output.mka'
    target.write_bytes(b'original-output')
    def fail_replace(*args):
        raise OSError('injected rename failure')
    monkeypatch.setattr(writer.os, 'replace', fail_replace)
    with pytest.raises(OSError, match='injected'):
        normalize_matroska_for_mta(matroska, target)
    assert target.read_bytes() == b'original-output'
    assert not list(tmp_path.glob('.mta-layout-*'))


def test_writer_rejects_symlink_target(matroska, tmp_path):
    target = tmp_path / 'real.mka'
    target.write_bytes(b'unchanged')
    link = tmp_path / 'link.mka'
    link.symlink_to(target)
    with pytest.raises(ValueError, match='symlink'):
        normalize_matroska_for_mta(matroska, link)
    assert target.read_bytes() == b'unchanged'


def test_writer_rejects_same_source_and_target(matroska):
    before = matroska.read_bytes()
    with pytest.raises(ValueError, match='differ'):
        normalize_matroska_for_mta(matroska, matroska)
    assert matroska.read_bytes() == before


def test_writer_safely_replaces_preexisting_file(matroska, tmp_path):
    target = tmp_path / 'existing.mka'
    target.write_bytes(b'old')
    offset = normalize_matroska_for_mta(matroska, target)
    assert offset > 0
    assert target.read_bytes()[:4] == b'\x1a\x45\xdf\xa3'
    assert not list(tmp_path.glob('.mta-layout-*'))
