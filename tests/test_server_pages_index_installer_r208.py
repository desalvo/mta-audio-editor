"""Regression tests for the GitHub Pages browser and pinned native installer."""
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'packaging/pages-repository/scripts/assemble_pages.py'


def test_browsable_indexes(tmp_path):
    spec = importlib.util.spec_from_file_location('mta_pages_index', INDEX)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    pkg = tmp_path / 'apt/early/pool/mta-audio-editor-server_0.3.0~early.208_amd64.deb'
    pkg.parent.mkdir(parents=True)
    pkg.write_bytes(b'fake-test-data')
    rpm = tmp_path / 'rpm/early/el10/repodata/repomd.xml'
    rpm.parent.mkdir(parents=True)
    rpm.write_text('<repomd/>')
    module.render_file_indexes(tmp_path)
    for d in ('', 'apt', 'apt/early', 'apt/early/pool', 'rpm', 'rpm/early', 'rpm/early/el10', 'rpm/early/el10/repodata'):
        assert (tmp_path / d / 'index.html').is_file()
    assert 'mta-audio-editor-server_0.3.0~early.208_amd64.deb' in (pkg.parent / 'index.html').read_text()
    assert '14 bytes' in (pkg.parent / 'index.html').read_text()
    assert 'apt/' in (tmp_path / 'index.html').read_text()
    assert pkg.read_bytes() == b'fake-test-data'
    assert rpm.read_text() == '<repomd/>'


def test_native_installer_uses_pinned_defaults():
    cmd = ['bash', str(ROOT / 'scripts/install_mta.sh'), '--native-server', 'early', '--dry-run']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, env={'PATH': '/usr/bin:/bin'})
    assert 'channel=early' in result.stdout
    assert 'url=https://desalvo.github.io/mta-audio-editor-packages' in result.stdout
    assert 'configure-verified-repository-and-install' in result.stdout
    script = (ROOT / 'scripts/repositories/install_repository.sh').read_text()
    assert '0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7' in script
    assert 'Signing key fingerprint mismatch: refusing repository' in script
    assert 'repo_gpgcheck=1' in script
