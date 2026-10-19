#!/usr/bin/env python3
"""Transactional offline MTA virtualenv replacement, with rollback on failed validation.

Only modifies the managed virtualenv; application state and secrets are untouched.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def install_runtime(python: str, app: Path, wheels: Path, venv: Path) -> None:
    if not app.is_dir() or not (app / 'requirements.txt').is_file():
        raise RuntimeError('Application/requirements.txt missing')
    if not list(wheels.glob('*.whl')):
        raise RuntimeError('Offline wheelhouse missing')
    venv.parent.mkdir(parents=True, exist_ok=True)
    stage = venv.with_name(venv.name + '.staging-' + uuid.uuid4().hex)
    backup = venv.with_name(venv.name + '.rollback')
    if backup.exists():
        raise RuntimeError(f'Existing rollback directory requires operator review: {backup}')
    moved_old = False
    installed_new = False
    try:
        subprocess.run([python, '-m', 'venv', str(stage)], check=True)
        interpreter = str(stage / 'bin' / 'python')
        subprocess.run([interpreter, '-m', 'pip', '--version'], check=True, stdout=subprocess.DEVNULL)
        subprocess.run([interpreter, '-m', 'pip', 'install', '--no-index', f'--find-links={wheels}', '-r', str(app / 'requirements.txt')], check=True)
        subprocess.run([interpreter, '-m', 'pip', 'check'], check=True)
        subprocess.run([interpreter, '-c', 'import app.ai_cgroup_launcher, app.main; import pedalboard,av,mido; assert all(hasattr(pedalboard.VST3Plugin,n) for n in ("_mta_set_transport","_mta_set_musical_position","_mta_process_sidechain"))'], cwd=app, check=True)
        if venv.exists():
            venv.rename(backup)
            moved_old = True
        stage.rename(venv)
        installed_new = True
        # A venv contains absolute paths, so scripts generated under staging need
        # rewriting after the directory is promoted.
        for script in (venv / 'bin').iterdir():
            if script.is_file() and not script.is_symlink():
                try:
                    raw = script.read_bytes()
                except OSError:
                    continue
                old = os.fsencode(str(stage))
                if raw.startswith(b'#!') and old in raw.split(b'\n', 1)[0]:
                    script.write_bytes(raw.replace(old, os.fsencode(str(venv))))
        # Validate after promotion as well: venvs contain absolute paths.
        promoted_python = str(venv / 'bin' / 'python')
        subprocess.run([promoted_python, '-m', 'pip', 'check'], check=True)
        subprocess.run([promoted_python, '-c', 'import app.ai_cgroup_launcher, app.main'], cwd=app, check=True)
        if moved_old:
            shutil.rmtree(backup)
    except BaseException:
        if installed_new and venv.exists():
            shutil.rmtree(venv)
        if moved_old and backup.exists():
            backup.rename(venv)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--python', default=sys.executable)
    p.add_argument('--app', type=Path, default=Path('/usr/lib/mta-audio-editor-server'))
    p.add_argument('--wheels', type=Path, default=Path('/usr/share/mta-audio-editor-server/wheelhouse'))
    p.add_argument('--venv', type=Path, default=Path('/opt/mta/server-venv'))
    a = p.parse_args()
    install_runtime(a.python, a.app, a.wheels, a.venv)


if __name__ == '__main__':
    main()
