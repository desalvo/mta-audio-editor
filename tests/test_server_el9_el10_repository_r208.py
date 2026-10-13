"""Regression gates: EL9 and EL10 artifacts never share DNF metadata."""
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


def test_el10_build_artifact_is_published_from_validated_rocky_job():
    matrix = (ROOT / '.github/workflows/server-native-runtime-validation.yml').read_text()
    assert "if: matrix.name == 'rocky10'" in matrix
    assert 'mta-server-rpm-el10-unreleased-test' in matrix
    publisher = (ROOT / '.github/workflows/server-pages-publish.yml').read_text()
    assert 'mta-server-rpm-el10-unreleased-test' in publisher
    assert 'incoming/rpm/el9' in publisher
    assert 'incoming/rpm/el10' in publisher


def test_indexes_are_isolated_and_signed_per_target():
    build = (ROOT / 'scripts/repositories/build_indexes.sh').read_text()
    assert 'for target in el9 el10' in build
    assert '"$out/rpm/$MTA_REPO_CHANNEL/$target/packages"' in build
    assert '"$rpmroot/repodata/repomd.xml.asc"' in build
    sign = (ROOT / 'scripts/repositories/prepare_signed_pages_release.sh').read_text()
    assert '"$MTA_REPO_INPUT"/rpm/el10/*.rpm' in sign
    assert 'for target in el9 el10' in sign


def test_pages_assembler_requires_both_signed_repositories():
    path = ROOT / 'packaging/pages-repository/scripts/assemble_pages.py'
    spec = importlib.util.spec_from_file_location('pages_mta', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import inspect
    source = inspect.getsource(mod.safe_extract)
    assert 'for el in ("el9", "el10")' in source


def test_native_installer_resolves_major_el_version():
    script = (ROOT / 'scripts/repositories/install_repository.sh').read_text()
    assert 'major=${VERSION_ID%%.*}' in script
    assert '9|10) target="el$major"' in script
    assert 'baseurl=$base/rpm/$CHANNEL/$target' in script
    assert 'repo_gpgcheck=1' in script
