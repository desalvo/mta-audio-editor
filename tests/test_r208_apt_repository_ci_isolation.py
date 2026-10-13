from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/repositories/build_indexes.sh"
APT_TEST = ROOT / "scripts/repositories/test_signed_apt_repository_ci.sh"


def test_apt_fixture_is_explicitly_scoped_to_ci():
    script = APT_TEST.read_text()
    assert "MTA_CI_APT_ONLY=1" in script
    assert "MTA_CI_DISPOSABLE_CONTAINER=1" in script
    assert "CI=true" in script


def test_production_keeps_rpm_index_and_signature_checks():
    script = BUILD.read_text()
    assert "if [[ $apt_only != 1 ]]" in script
    assert "for target in el9 el10" in script
    assert "rpm --checksig" in script
    assert "createrepo_c --update" in script


def test_apt_only_rejected_outside_disposable_ci(tmp_path):
    env = dict(os.environ, MTA_CI_APT_ONLY="1", CI="false", MTA_CI_DISPOSABLE_CONTAINER="0",
               MTA_REPO_INPUT=str(tmp_path), MTA_REPO_OUTPUT=str(tmp_path / "out"),
               MTA_REPO_CHANNEL="early", MTA_GPG_KEY_ID="0" * 40)
    result = subprocess.run(["bash", str(BUILD)], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert "restricted to disposable CI" in result.stderr
