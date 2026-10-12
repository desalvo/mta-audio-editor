from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_publisher_shell_parses():
    script = ROOT / 'scripts/repositories/prepare_signed_pages_release.sh'
    subprocess.run(['bash', '-n', str(script)], check=True)


def test_publisher_requires_fingerprint_and_key():
    script = (ROOT / 'scripts/repositories/prepare_signed_pages_release.sh').read_text()
    assert 'MTA_GPG_KEY_ID' in script
    assert 'MTA_GPG_PASSPHRASE_FILE' in script
    assert 'rpmsign --addsign' in script
    assert 'gpg --verify' in script
    assert 'Prerelease DEB cannot enter stable' in script


def test_workflow_is_manual_and_approval_gated():
    wf = (ROOT / '.github/workflows/server-pages-publish.yml').read_text()
    assert 'workflow_dispatch:' in wf
    assert 'environment: server-${{ inputs.channel }}' in wf
    assert '.conclusion' in wf and 'success' in wf
    assert 'GITHUB_SHA' in wf
    assert 'mta-server-rpm-unreleased-test' in wf
    assert 'mta-server-deb-debian13-unreleased-test' in wf
    assert 'MTA_PAGES_DEPLOY_KEY' in wf
    assert 'MTA_GPG_PRIVATE_KEY' in wf
    assert 'MTA_GPG_PASSPHRASE' in wf
    assert 'actions/upload-artifact@v4' in wf
    assert 'signed-mta-pages-${{ inputs.channel }}' in wf
    assert 'manifests' in wf
    assert '100-MiB' not in wf
