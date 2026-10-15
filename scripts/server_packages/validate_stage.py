#!/usr/bin/env python3
"""Fail closed before packaging an incomplete or wrongly identified server artifact."""
import argparse

from pathlib import Path
import importlib.util



def validate(stage: Path) -> list[str]:
    errors = []
    app = stage / 'application'
    for name in ('app/main.py', 'app/ai_cgroup_launcher.py', 'requirements.txt'):
        if not (app / name).is_file():
            errors.append(f'missing {name}')
    # Non-release fixtures can omit identity files, but a real release must
    # always carry the exact version and revision into the native package.
    if __import__('os').environ.get('MTA_SERVER_RELEASE_READY') == '1':
        for filename in ('VERSION', 'REVISION', 'BUILD_INFO', 'RELEASE_CHANNEL'):
            if not (app / filename).is_file():
                errors.append(f'missing native release metadata {filename}')
    if (app / 'VERSION').is_file() and (app / 'REVISION').is_file():
        if not __import__('re').fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', (app / 'VERSION').read_text().strip()):
            errors.append('invalid VERSION in native package')
        if not __import__('re').fullmatch(r'[0-9]+', (app / 'REVISION').read_text().strip()):
            errors.append('invalid REVISION in native package')
    if (app / '.git').exists():
        errors.append('git metadata in server payload')
    wheels = list((stage / 'wheelhouse').glob('*.whl'))
    if not wheels:
        errors.append('wheelhouse empty: network-free install impossible')
    else:
        try:
            spec = importlib.util.spec_from_file_location("wheelhouse_lock", Path(__file__).with_name("wheelhouse_lock.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.verify(stage)
        except (ValueError, OSError, KeyError, TypeError, __import__("json").JSONDecodeError, __import__("zipfile").BadZipFile) as exc:
            errors.append(f'invalid wheelhouse lock: {exc}')
    for path in stage.rglob('*'):
        if path.is_symlink() and (path.is_absolute() or '..' in path.parts):
            errors.append(f'unsafe symlink {path}')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    problems = validate(args.stage)
    for issue in problems:
        print('ERROR:', issue)
    if problems:
        raise SystemExit(1)
    print('Server staging valid')
