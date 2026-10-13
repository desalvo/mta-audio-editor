"""Regression checks for disposable APT-only repository fixture (r208)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_apt_fixture_requests_ci_only_mode():
    script = (ROOT / 'scripts/repositories/test_signed_apt_repository_ci.sh').read_text()
    assert 'MTA_REPO_APT_ONLY_CI=1 MTA_REPO_INPUT=' in script
    assert 'MTA_CI_DISPOSABLE_CONTAINER' in script


def test_repository_publisher_rejects_apt_only_outside_disposable_ci():
    script = (ROOT / 'scripts/repositories/build_indexes.sh').read_text()
    assert 'MTA_REPO_APT_ONLY_CI' in script
    assert '[[ ${MTA_CI_DISPOSABLE_CONTAINER:-0} == 1 ]]' in script
    assert script.count('[[ $apt_only_ci == 1 ]] && break') == 2
    assert 'No $target RPM packages' in script
