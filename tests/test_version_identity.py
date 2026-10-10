from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_product_version_revision_and_build_are_distinct():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    revision = (ROOT / "REVISION").read_text(encoding="utf-8").strip()
    build = (ROOT / "BUILD_INFO").read_text(encoding="utf-8").strip()
    assert version == "0.3.0"
    assert revision.isdigit() and int(revision) >= 1
    assert build.isdigit() and len(build) == 14
    assert revision not in version


def test_release_identity_is_exposed_separately():
    source = (ROOT / "app/version.py").read_text(encoding="utf-8")
    assert 'APP_REVISION = os.getenv("MTA_APP_REVISION"' in source
    assert 'APP_RELEASE = f"{APP_VERSION}-r{APP_REVISION}"' in source
