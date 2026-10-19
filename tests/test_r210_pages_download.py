"""Regression for silent multi-GB Pages downloads and separate retention bundles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'pages_download', ROOT / 'packaging/pages-repository/scripts/assemble_pages.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def manifest(folder, channel='early', **extra):
    data = dict(schema=1, channel=channel, repository=MOD.SOURCE, run_id=123,
                commit='a' * 40, sha256=hashlib.sha256(b'legacy').hexdigest(), **extra)
    folder.mkdir(exist_ok=True)
    (folder / f'{channel}.json').write_text(json.dumps(data))
    return data


@pytest.mark.parametrize('pages_only', [True, False])
def test_bundle_selection_and_checksum_before_extraction(tmp_path, monkeypatch, pages_only):
    content = b'pages' if pages_only else b'legacy'
    manifests = tmp_path / 'manifests'
    extra = {'pages_sha256': hashlib.sha256(content).hexdigest()} if pages_only else {}
    manifest(manifests, **extra)
    downloads, extracted = [], []

    def download(run, artifact, destination):
        downloads.append((run, artifact))
        filename = 'pages-site.tar.gz' if pages_only else 'signed-channel.tar.gz'
        (destination / filename).write_bytes(content)

    monkeypatch.setattr(MOD, 'download_artifact', download)
    monkeypatch.setattr(MOD, 'safe_extract', lambda archive, out, channel: extracted.append(channel))
    MOD.assemble(manifests, tmp_path / 'site')
    assert downloads == [(123, 'signed-mta-pages-' + ('site-' if pages_only else '') + 'early')]
    assert extracted == ['early']


def test_small_bundle_corruption_fails_without_legacy_fallback(tmp_path, monkeypatch):
    manifests = tmp_path / 'manifests'
    manifest(manifests, pages_sha256='0' * 64)
    monkeypatch.setattr(MOD, 'download_artifact',
                        lambda run, artifact, destination: (destination / 'pages-site.tar.gz').write_bytes(b'bad'))
    monkeypatch.setattr(MOD, 'safe_extract', lambda *args: pytest.fail('Must check checksum first'))
    with pytest.raises(ValueError, match='checksum mismatch'):
        MOD.assemble(manifests, tmp_path / 'site')


def test_bad_pages_digest_cannot_downgrade_to_legacy(tmp_path):
    manifest(tmp_path, pages_sha256=None)
    with pytest.raises(ValueError, match='Pages checksum'):
        MOD.load_manifest(tmp_path / 'early.json', 'early')


@pytest.mark.parametrize('code', [0, 7])
def test_real_subprocess_completion_or_failure(tmp_path, monkeypatch, code):
    real_popen = subprocess.Popen
    monkeypatch.setattr(MOD.subprocess, 'Popen',
                        lambda command: real_popen([sys.executable, '-c', f'raise SystemExit({code})']))
    if code:
        with pytest.raises(RuntimeError, match='exit 7'):
            MOD.download_artifact(123, 'test', tmp_path, timeout=2, heartbeat=.02)
    else:
        MOD.download_artifact(123, 'test', tmp_path, timeout=2, heartbeat=.02)


def test_stalled_download_reports_heartbeat_and_reaps_process(tmp_path, monkeypatch, capsys):
    real_popen = subprocess.Popen
    children = []

    def popen(command):
        child = real_popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        children.append(child)
        return child

    monkeypatch.setattr(MOD.subprocess, 'Popen', popen)
    with pytest.raises(TimeoutError, match='timed out'):
        MOD.download_artifact(123, 'test', tmp_path, timeout=.15, heartbeat=.03)
    assert children[0].poll() is not None
    assert 'still active' in capsys.readouterr().out


def test_workflow_produces_small_bundle_preserving_full_retention(tmp_path):
    import os
    import tarfile
    workflow = yaml.safe_load((ROOT / '.github/workflows/server-pages-publish.yml').read_text())
    steps = workflow['jobs']['publish']['steps']
    step = next(s for s in steps if s.get('name', '').startswith('Create Pages-only'))
    tree = tmp_path / 'site-bundle'
    for name in ['apt/early/pool/server.deb', 'apt/early/InRelease',
                 'rpm/early/el9/packages/server.rpm', 'rpm/early/el9/repodata/repomd.xml.asc',
                 'mta-archive-key.asc']:
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'payload')
    subprocess.run(['bash', '-c', step['run']], env={**os.environ, 'RUNNER_TEMP': str(tmp_path), 'CHANNEL': 'early'}, check=True)
    archive = tmp_path / 'pages-site.tar.gz'
    with tarfile.open(archive) as stream:
        names = stream.getnames()
    assert not any(n.endswith('.rpm') for n in names)
    assert './apt/early/pool/server.deb' in names
    assert './rpm/early/el9/repodata/repomd.xml.asc' in names
    assert (tree / 'rpm/early/el9/packages/server.rpm').read_bytes() == b'payload'
    assert (tmp_path / 'pages-site.sha256').read_text().strip() == MOD.sha256_file(archive)
    assert any(s.get('with', {}).get('name') == 'signed-mta-pages-${{ inputs.channel }}' for s in steps)
    assert any(s.get('with', {}).get('name') == 'signed-mta-pages-site-${{ inputs.channel }}' for s in steps)


def test_two_channels_use_independent_download_directories(tmp_path, monkeypatch):
    manifests = tmp_path / 'manifests'
    for channel in ('early', 'stable'):
        manifest(manifests, channel, pages_sha256=hashlib.sha256(b'pages').hexdigest())
    destinations = []

    def download(run, artifact, destination):
        destinations.append(destination)
        (destination / 'pages-site.tar.gz').write_bytes(b'pages')
        (destination / 'extra.txt').write_text('extra')

    monkeypatch.setattr(MOD, 'download_artifact', download)
    monkeypatch.setattr(MOD, 'safe_extract', lambda *args: None)
    MOD.assemble(manifests, tmp_path / 'site')
    assert len(set(destinations)) == 2


def test_actual_publisher_manifest_retains_both_digests(tmp_path):
    workflow = yaml.safe_load((ROOT / '.github/workflows/server-pages-publish.yml').read_text())
    steps = workflow['jobs']['publish']['steps']
    run = next(s['run'] for s in steps if s.get('name', '').startswith('Publish verified channel manifest'))
    script = run.split("<<'PYMANIFEST'\n", 1)[1].split('\nPYMANIFEST', 1)[0]
    (tmp_path / 'manifests').mkdir()
    full = tmp_path / 'full.sha256'
    pages = tmp_path / 'pages.sha256'
    full.write_text('a' * 64 + '\n')
    pages.write_text('b' * 64 + '\n')
    subprocess.run([sys.executable, '-c', script, 'early', MOD.SOURCE, '123',
                    'c' * 40, str(full), str(pages)], cwd=tmp_path, check=True)
    data = MOD.load_manifest(tmp_path / 'manifests/early.json', 'early')
    assert data['sha256'] == 'a' * 64
    assert data['pages_sha256'] == 'b' * 64
