"""Guardrail tests for size-limited Pages RPM publishing."""
import gzip
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'pages_rpm', ROOT / 'scripts/repositories/publish_pages_rpm_indexes.py'
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _staging(tmp_path, *, valid=True):
    root = tmp_path / 'staging'
    root.mkdir()
    (root / 'mta-archive-key.asc').write_text('test-key')
    for distro in ('el9', 'el10'):
        rp = root / 'rpm/early' / distro
        (rp / 'packages').mkdir(parents=True)
        (rp / 'packages' / f'mta-server-0.3.0-209.{distro}.rpm').write_bytes(b'fake-rpm')
        (rp / 'repodata').mkdir()
        name = f'mta-server-0.3.0-209.{distro}.rpm'
        meta = ('<metadata xmlns="http://linux.duke.edu/metadata/common">'
                f'<package><location href="{name}" xml:base="https://github.com/desalvo/mta-audio-editor/releases/download/server-packages-early/"/></package>'
                '</metadata>').encode()
        with gzip.open(rp / 'repodata' / 'primary.xml.gz', 'wb') as f:
            f.write(meta)
        reponame = '{http://linux.duke.edu/metadata/repo}'
        re = ET.Element(reponame + 'repomd')
        dat = ET.SubElement(re, reponame + 'data', type='primary')
        ET.SubElement(dat, reponame + 'location', href='repodata/primary.xml.gz')
        ET.ElementTree(re).write(rp / 'repodata/repomd.xml')
        (rp / 'repodata/repomd.xml.asc').write_text('fake-signature')
    return root


def test_indexes_publish_without_rpm_payload(tmp_path):
    st = _staging(tmp_path)
    pages = tmp_path / 'pages'
    result = MODULE.populate(st, pages, 'early', 'https://github.com/desalvo/mta-audio-editor/releases/download/server-packages-early/')
    assert len(result) == 2
    assert not list(pages.rglob('*.rpm'))
    for distro in ('el9', 'el10'):
        listing = (pages / 'rpm/early' / distro / 'packages/index.html').read_text()
        assert 'https://github.com/desalvo/mta-audio-editor/releases/download/server-packages-early/' in listing
        assert (pages / 'rpm/early' / distro / 'repodata/repomd.xml.asc').is_file()


def test_missing_signed_metadata_rejected(tmp_path):
    st = _staging(tmp_path)
    (st / 'rpm/early/el10/repodata/repomd.xml.asc').unlink()
    import pytest
    with pytest.raises(ValueError, match='Missing signed'):
        MODULE.populate(st, tmp_path / 'pages', 'early', 'https://github.com/desalvo/mta-audio-editor/releases/download/server-packages-early/')


def test_pages_payload_size_limit_enforced(tmp_path):
    st = _staging(tmp_path)
    pages = tmp_path / 'pages'
    pages.mkdir()
    # test with small threshold rather than allocating tens of megabytes
    original = MODULE.GIT_BLOB_LIMIT
    MODULE.GIT_BLOB_LIMIT = 4
    import pytest
    try:
        with pytest.raises(ValueError, match='blob limit'):
            MODULE.populate(st, pages, 'early', 'https://github.com/desalvo/mta-audio-editor/releases/download/server-packages-early/')
    finally:
        MODULE.GIT_BLOB_LIMIT = original


def test_malformed_release_url_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError, match='GitHub Release'):
        MODULE.populate(_staging(tmp_path), tmp_path / 'pages', 'early', 'http://example.org/releases/')


def test_createrepo_indexes_flat_packages_into_pages_repo_root():
    # Indexing the parent directory would produce href=packages/<file>,
    # which makes DNF request a non-existent Release asset URL.
    workflow = (ROOT / '.github/workflows/server-pages-publish.yml').read_text()
    assert 'createrepo_c --baseurl "$url" --outputdir "$root" "$root/packages"' in workflow
    assert 'createrepo_c --baseurl "$url" "$root"' not in workflow


def test_primary_package_subdirectory_reference_rejected(tmp_path):
    import pytest
    st = _staging(tmp_path)
    root = st / 'rpm/early/el9/repodata/primary.xml.gz'
    with gzip.open(root, 'rb') as stream:
        xml = stream.read().replace(b'location href="mta-', b'location href="packages/mta-')
    with gzip.open(root, 'wb') as stream:
        stream.write(xml)
    with pytest.raises(ValueError, match='verified Release asset URL'):
        MODULE.populate(st, tmp_path / 'pages', 'early',
                        'https://github.com/desalvo/mta-audio-editor/releases/download/server-packages-early/')


def test_release_asset_collision_is_replaced_and_verified_by_digest():
    workflow = (ROOT / '.github/workflows/server-pages-publish.yml').read_text()
    assert 'gh release upload "$tag" "$f" -R "$GITHUB_REPOSITORY" --clobber' in workflow
    assert 'local_sha=$(sha256sum "$f"' in workflow
    assert workflow.count('"sha256:$local_sha"') >= 2
    assert 'Asset collision with different size' not in workflow
