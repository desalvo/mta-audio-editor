from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repository_probe_has_two_minute_timeout():
    source = (ROOT / 'scripts/repositories/install_repository.sh').read_text()
    assert 'timeout --signal=TERM --kill-after=5s 120s' in source
    assert 'timeout --signal=TERM --kill-after=5s 180s' in source
    assert '(120s)' in source


def test_ace_installer_ensures_argcomplete_in_distro_and_venv():
    source = (ROOT / 'scripts/install_ace_step.sh').read_text()
    assert 'python3-argcomplete' in source
    assert 'pip install -U pip setuptools wheel argcomplete' in source
    assert "-c 'import argcomplete'" in source
    assert 'argcomplete>=3,<4' in source


def test_bootstrap_downloads_are_bounded():
    source = (ROOT / 'scripts/install_mta.sh').read_text()
    assert source.count('--connect-timeout 20 --max-time 120') >= 2
