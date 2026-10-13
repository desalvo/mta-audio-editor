"""Ensure fresh EL installations initialize metadata GPG trust before bounded probes."""
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/repositories/install_repository.sh"


def test_first_boot_makecache_precedes_short_probe_and_package_install():
    s = SCRIPT.read_text()
    prewarm = s.index('echo "Initializing signed MTA DNF repository metadata')
    probe = s.index('   prepare_el_dependencies "$major"', prewarm)
    install = s.index('   dnf install -y mta-audio-editor-server', probe)
    assert prewarm < probe < install
    assert "--disablerepo='*' --enablerepo=mta-audio-editor makecache" in s
    assert "dnf -y --refresh" in s
    assert "timeout --signal=TERM --kill-after=5s 180s" in s


def test_first_boot_trust_is_pinned_and_not_bypassed():
    s = SCRIPT.read_text()
    assert '[[ $actual == "${MTA_REPO_KEY_FINGERPRINT^^}" ]]' in s
    assert 'rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-MTA' in s
    assert 'repo_gpgcheck=1' in s and 'gpgcheck=1' in s
    assert '--nogpgcheck' not in s
    assert '--setopt=repo_gpgcheck=0' not in s
