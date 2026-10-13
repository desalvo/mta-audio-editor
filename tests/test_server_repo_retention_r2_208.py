import importlib.util
import io
import json
from pathlib import Path
import tarfile
import hashlib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


RET = module('retention', ROOT / 'scripts/repositories/retain_channel_packages.py')
PREV = module('previous', ROOT / 'scripts/repositories/restore_previous_channel.py')
R2 = module('r2', ROOT / 'scripts/repositories/r2_publish.py')


def test_debian_versions_use_native_comparator():
    assert RET.compare_deb('0.3.0~early.208', '0.3.0~early.207') > 0
    assert RET.compare_deb('0.3.0~early.210', '0.3.0~early.209') > 0
    assert RET.compare_deb('0.3.0~early.208', '0.3.0-1') < 0


def test_keep_only_two_versions(tmp_path):
    for n in (207, 208, 209):
        (tmp_path / f'package_{n}.deb').write_bytes(b'a')
    def inspect(p):
        return 'mta-audio-editor-server', 'amd64', p.stem.split('_')[1]
    RET.retain(tmp_path, '.deb', inspect, lambda a, b: (int(a) > int(b)) - (int(a) < int(b)))
    assert sorted(p.name for p in tmp_path.iterdir()) == ['package_208.deb', 'package_209.deb']


def test_previous_channel_rejects_mismatched_hash(tmp_path):
    manifest = tmp_path / 'early.json'
    archive = tmp_path / 'old.tar.gz'
    archive.write_bytes(b'invalid')
    manifest.write_text(json.dumps({'channel':'early','repository':'desalvo/mta-audio-editor','sha256':'0'*64}))
    with pytest.raises(ValueError, match='checksum'):
        PREV.restore(manifest, archive, tmp_path, 'early')


def test_previous_channel_only_imports_package_files(tmp_path):
    archive = tmp_path / 'old.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for filename in ('apt/early/pool/old.deb', 'rpm/early/packages/old.rpm', 'rpm/early/el10/packages/new.rpm', 'apt/stable/pool/secret.deb'):
            payload = b'content'
            entry = tarfile.TarInfo(filename)
            entry.size = len(payload)
            tar.addfile(entry, io.BytesIO(payload))
    manifest = tmp_path / 'early.json'
    manifest.write_text(json.dumps({'channel':'early', 'repository':'desalvo/mta-audio-editor',
                                   'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}))
    incoming = tmp_path / 'incoming'
    incoming.mkdir()
    PREV.restore(manifest, archive, incoming, 'early')
    assert sorted(p.name for p in incoming.iterdir()) == ['old.deb', 'rpm']
    assert (incoming / 'rpm/el9/old.rpm').read_bytes() == b'content'
    assert (incoming / 'rpm/el10/new.rpm').read_bytes() == b'content'


def test_r2_disabled_by_default(tmp_path):
    (tmp_path / 'apt/early').mkdir(parents=True)
    (tmp_path / 'rpm/early/el9/repodata').mkdir(parents=True)
    (tmp_path / 'rpm/early/el10/repodata').mkdir(parents=True)
    (tmp_path / 'apt/early/InRelease').write_text('signed')
    (tmp_path / 'rpm/early/el9/repodata/repomd.xml.asc').write_text('signed')
    (tmp_path / 'rpm/early/el10/repodata/repomd.xml.asc').write_text('signed')
    assert len(R2.publish(tmp_path, '', '', 'early')) == 3
    with pytest.raises(RuntimeError, match='disabled'):
        R2.publish(tmp_path, 'bucket', 'https://example.test', 'early', dry_run=False)


def test_workflow_retention_and_pages_limit():
    source = (ROOT / '.github/workflows/server-pages-publish.yml').read_text()
    assert 'retain_channel_packages.py' in source and '--limit 2' in source
    assert 'restore_previous_channel.py' in source
    pages = (ROOT / 'packaging/pages-repository/.github/workflows/pages.yml').read_text()
    assert '1000000000' in pages
