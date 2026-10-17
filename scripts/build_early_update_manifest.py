#!/usr/bin/env python3
"""Publish build identities taken from the actual desktop installer filenames."""
from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native.update_manager import asset_build, asset_release_version


def build_manifest(folder, version, revision, *, commit_sha='', repository='desalvo/mta-audio-editor'):
    release = f'{version}-r{revision}'
    builds = {}
    for path in sorted(Path(folder).iterdir()):
        if path.suffix.lower() not in ('.exe', '.dmg'):
            continue
        build = asset_build(path.name)
        if not build or asset_release_version(path.name) != release:
            raise ValueError('Early desktop installer lacks a matching release/build identity: ' + path.name)
        builds[path.name] = build
    if not builds:
        raise ValueError('No early desktop installers available for publication')
    return {'channel': 'early', 'version': version, 'revision': str(revision), 'release': release,
            'commit_sha': commit_sha, 'ref': 'main', 'repository': repository, 'package_builds': builds}


def main():
    folder = Path(sys.argv[1])
    manifest = build_manifest(folder, (ROOT / 'VERSION').read_text().strip(),
        (ROOT / 'REVISION').read_text().strip(), commit_sha=os.environ.get('GITHUB_SHA', ''),
        repository=os.environ.get('GITHUB_REPOSITORY', 'desalvo/mta-audio-editor'))
    (folder / 'early-update.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
