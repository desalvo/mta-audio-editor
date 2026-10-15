"""Server matrix and release publisher must consume current revision, not stale r208."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_matrix_native_packages_use_current_version_metadata():
    workflow = (ROOT / ".github/workflows/server-native-runtime-validation.yml").read_text()
    assert workflow.count('MTA_RPM_RELEASE="0.$(cat REVISION).1.early.b$(cat BUILD_INFO).r${GITHUB_RUN_ID}.a${GITHUB_RUN_ATTEMPT}"') == 2
    assert workflow.count('MTA_SERVER_VERSION="$(cat VERSION)~early.$(cat REVISION)+pkg1"') == 2
    assert "MTA_RPM_RELEASE=0.208.1.early" not in workflow


def test_repository_tooling_deb_tracks_revision():
    workflow = (ROOT / ".github/workflows/server-package-repository-validation.yml").read_text()
    assert 'Version | grep -Fxq "$(cat VERSION)~early.$(cat REVISION)+pkg1"' in workflow
    assert "0.3.0~early.208+pkg1" not in workflow


def test_publish_rejects_stale_artifact_versions_before_restore():
    workflow = (ROOT / ".github/workflows/server-pages-publish.yml").read_text()
    assert "Stale RPM from matrix:" in workflow
    assert "Stale DEB from matrix:" in workflow
    assert workflow.index("Stale RPM from matrix:") < workflow.index("Restore previous channel and retain twenty versions")
    assert 'expected_rpm_release="0.$expected_revision.1.early.b${expected_build}.r${RUN_ID}.a${source_attempt}"' in workflow
