#!/usr/bin/env python3
"""Publish only signed RPM metadata and HTML download links to a small Pages site.

RPM binaries live in a GitHub Release because they can exceed GitHub's 100 MiB
Git-blob limit. createrepo_c --baseurl must run before this script; RPM signing
and repomd.xml.asc must be refreshed after that command.
"""
import argparse
import gzip
import html
from pathlib import Path
import shutil
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET

GIT_BLOB_LIMIT = 45 * 1024 * 1024  # Leave headroom below GitHub's 50 MB warning
PAGES_SOFT_LIMIT = 900 * 1024 * 1024  # Below the 1 GiB Pages site limit
XMLNS = '{http://linux.duke.edu/metadata/repo}'


def populate(staging: Path, pages: Path, channel: str, release_url: str) -> list[str]:
    if channel not in ('early', 'stable'):
        raise ValueError('Invalid channel')
    url = urlsplit(release_url)
    if url.scheme != 'https' or url.netloc != 'github.com' or '/releases/download/' not in url.path:
        raise ValueError('A GitHub Release HTTPS asset root is required')
    if not release_url.endswith('/'):
        raise ValueError('Release asset root must end with /')
    key = staging / 'mta-archive-key.asc'
    if not key.is_file() or not key.stat().st_size:
        raise ValueError('Missing GPG public key')
    page_key = pages / 'mta-archive-key.asc'
    page_key.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(key, page_key)
    published = []
    for distro in ('el9', 'el10'):
        root = staging / 'rpm' / channel / distro
        rpms = sorted((root / 'packages').glob('*.rpm'))
        if not rpms:
            raise ValueError(f'Missing {distro} RPMs')
        names = [p.name for p in rpms]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate RPM filenames')
        metadata = root / 'repodata'
        repomd = metadata / 'repomd.xml'
        sig = metadata / 'repomd.xml.asc'
        if not repomd.is_file() or not sig.is_file():
            raise ValueError(f'Missing signed {distro} repository metadata')
        tree = ET.parse(repomd)
        locations = [node.attrib.get('href', '') for node in tree.iter(XMLNS + 'location')]
        if not locations:
            raise ValueError(f'Missing metadata references for {distro}')
        for href in locations:
            if not href.startswith('repodata/') or '..' in Path(href).parts:
                raise ValueError(f'Unsafe repository metadata reference: {href}')
            if not (root / href).is_file():
                raise ValueError(f'Missing metadata payload: {href}')
        # Validate the primary metadata's actual download URLs (DNF consumes
        # primary.xml, not the human HTML listing). No broken package links.
        main_data = [n for n in tree.iter(XMLNS + 'data') if n.attrib.get('type') == 'primary']
        if len(main_data) != 1:
            raise ValueError(f'Expected one primary metadata entry for {distro}')
        main_location = main_data[0].find(XMLNS + 'location')
        if main_location is None:
            raise ValueError('No primary metadata location')
        primary_path = root / main_location.attrib['href']
        if primary_path.suffix == '.gz':
            with gzip.open(primary_path, 'rb') as stream:
                primary = ET.parse(stream)
        else:
            primary = ET.parse(primary_path)
        pkg_ns = '{http://linux.duke.edu/metadata/common}'
        xml_base = '{http://www.w3.org/XML/1998/namespace}base'
        actual = {}
        for package in primary.getroot().findall(pkg_ns + 'package'):
            loc = package.find(pkg_ns + 'location')
            if loc is None:
                raise ValueError('Package missing location in primary metadata')
            actual[loc.attrib.get('href', '')] = loc.attrib.get(xml_base)
        if set(actual) != set(names) or any(v != release_url for v in actual.values()):
            raise ValueError(f'{distro} primary.xml does not reference the verified Release asset URL')
        target = pages / 'rpm' / channel / distro
        dest = target / 'repodata'
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(metadata, dest)
        package_dir = target / 'packages'
        if package_dir.exists():
            shutil.rmtree(package_dir)
        package_dir.mkdir(parents=True)
        links = '\n'.join(f'<li><a href="{html.escape(release_url + quote(name), quote=True)}">{html.escape(name)}</a></li>' for name in names)
        (package_dir / 'index.html').write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            f'<title>MTA server {html.escape(channel)} {html.escape(distro)} RPM downloads</title>'
            f'<h1>MTA server {html.escape(channel)} / {html.escape(distro)}</h1>'
            '<p>Signed RPM binaries are hosted on GitHub Releases to keep GitHub Pages below its size limit.</p>'
            f'<ul>{links}</ul></html>\n', encoding='utf-8')
        published.extend(names)
    (pages / '.nojekyll').touch()
    # Strictly enforce the GitHub git blob warning threshold and Pages site limit.
    files = [p for p in pages.rglob('*') if p.is_file() and '.git' not in p.relative_to(pages).parts]
    oversized = [(p, p.stat().st_size) for p in files if p.stat().st_size > GIT_BLOB_LIMIT]
    if oversized:
        raise ValueError(f'Pages file exceeds conservative Git blob limit: {oversized}')
    total = sum(p.stat().st_size for p in files)
    if total > PAGES_SOFT_LIMIT:
        raise ValueError(f'Pages content {total} bytes exceeds {PAGES_SOFT_LIMIT} byte budget')
    if any(p.suffix == '.rpm' for p in files):
        raise ValueError('RPM payload must never enter Pages Git repository')
    return published


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--staging', type=Path, required=True)
    p.add_argument('--pages', type=Path, required=True)
    p.add_argument('--channel', choices=('early', 'stable'), required=True)
    p.add_argument('--release-url', required=True)
    a = p.parse_args()
    print('\n'.join(populate(a.staging, a.pages, a.channel, a.release_url)))


if __name__ == '__main__':
    main()
