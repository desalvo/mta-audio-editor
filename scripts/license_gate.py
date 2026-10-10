#!/usr/bin/env python3
"""Fail-closed guard for accidentally bundled proprietary VST SDKs/plugins.

This static check is not a legal opinion or a substitute for reviewing the
licenses of binaries resolved by package managers at distribution time.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {'.vst3', '.component', '.aaxplugin'}
BINARY_SUFFIXES = {'.dll', '.so', '.dylib'}
REQUIRED_NOTICES = ('EUPL', 'FFmpeg', 'Chordino', 'VST3')


def audit(root: Path) -> dict:
    errors: list[str] = []
    notices = root / 'THIRD_PARTY_NOTICES.md'
    if not notices.is_file():
        errors.append('Missing THIRD_PARTY_NOTICES.md')
    else:
        contents = notices.read_text(encoding='utf-8')
        for name in REQUIRED_NOTICES:
            if name.casefold() not in contents.casefold():
                errors.append(f'Notice missing: {name}')
    bundles: list[str] = []
    for file in root.rglob('*'):
        if not file.is_file() or any(p in {'.git', '.venv', '__pycache__', '.pytest_cache'} for p in file.parts):
            continue
        relative = file.relative_to(root).as_posix()
        # A shipped third-party plugin is not implicitly redistributable.
        if any(p.lower().endswith(tuple(FORBIDDEN_SUFFIXES)) for p in file.parts):
            errors.append(f'VST/AU/AAX bundle must not be shipped without an explicit reviewed exception: {relative}')
        if file.suffix.lower() in BINARY_SUFFIXES and ('vst3' in relative.lower() or 'steinberg' in relative.lower()):
            errors.append(f'Unreviewed VST binary: {relative}')
        if file.name.lower() in {'pluginterfaces', 'vst3sdk'}:
            errors.append(f'Unexpected SDK directory artifact: {relative}')
        if file.suffix.lower() in {'.whl', '.deb', '.rpm'}:
            bundles.append(relative)
    android = root / 'mobile/android/app/build.gradle.kts'
    if android.is_file() and re.search(r'META-INF/(?:LICENSE|NOTICE)\*?', android.read_text()):
        errors.append('Android blanket exclusion of license/notice resources')
    return {'ok': not errors, 'errors': errors, 'prebuilt_artifacts': bundles,
            'message': 'Static source guard only: review compiled bundles, transitive dependencies and media codecs before distribution.'}



def audit_archive(archive: Path) -> dict:
    """Scan members without extracting/untrusted filesystem writes.

    Binary distributables like .deb/.rpm require a separate package audit;
    never claim this archive scanner handles those formats.
    """
    errors: list[str] = []
    members: list[str] = []
    try:
        if zipfile.is_zipfile(archive):
            with zipfile.ZipFile(archive) as zf:
                members = [x.filename for x in zf.infolist() if not x.is_dir()]
        elif tarfile.is_tarfile(archive):
            with tarfile.open(archive, 'r:*') as tf:
                members = [x.name for x in tf.getmembers() if x.isfile()]
        else:
            return {'ok': False, 'errors': [f'Unsupported archive format: {archive.name}'], 'members_checked': 0}
    except (OSError, ValueError, EOFError, tarfile.TarError, zipfile.BadZipFile) as exc:
        return {'ok': False, 'errors': [f'Unreadable archive: {exc}'], 'members_checked': 0}
    for name in members:
        normalized = name.replace('\\', '/')
        parts = Path(normalized).parts
        if normalized.startswith('/') or '..' in parts:
            errors.append(f'Unsafe archive member path: {name}')
        if any(part.lower().endswith(tuple(FORBIDDEN_SUFFIXES)) for part in parts):
            errors.append(f'Unreviewed bundled plugin: {name}')
        if Path(normalized).suffix.lower() in BINARY_SUFFIXES and any(
            term in normalized.lower() for term in ('vst3', 'steinberg')
        ):
            errors.append(f'Unreviewed VST binary: {name}')
    return {'ok': not errors, 'errors': errors, 'members_checked': len(members),
            'message': 'Archive contents static scan; external runtime and binary license audit still required.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--archive', type=Path, action='append', default=[],
                        help='Also inspect ZIP/TAR source or release archives without extracting')
    args = parser.parse_args()
    result = audit(args.root.resolve())
    result['archives'] = {str(path): audit_archive(path) for path in args.archive}
    if any(not item['ok'] for item in result['archives'].values()):
        result['ok'] = False
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
