#!/usr/bin/env python3
"""Create an offline, hash-locked runtime staging for native server packages.

Run INSIDE a supported target OS/architecture with the same Python interpreter
used by the resulting package; do not cross-download binary wheels.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def run(cmd):
    subprocess.run(cmd, check=True, env={**os.environ, 'PIP_DISABLE_PIP_VERSION_CHECK': '1'})


def prepare(source: Path, stage: Path, requirements: Path):
    if sys.version_info < (3, 12):
        raise ValueError('Python 3.12+ is required by the MTA server')
    if stage.exists() and any(stage.iterdir()):
        raise ValueError('Refusing non-empty staging directory: use a fresh stage')
    if not (source / 'app/main.py').is_file() or not (source / 'app/ai_cgroup_launcher.py').is_file():
        raise ValueError('MTA application entrypoints not found')
    if not requirements.is_file():
        raise ValueError('Missing server requirements')
    app = stage / 'application'
    wheels = stage / 'wheelhouse'
    app.mkdir(parents=True, exist_ok=True)
    wheels.mkdir()
    # Only the application and locked runtime requirements belong to the server.
    shutil.copytree(source / 'app', app / 'app', ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'), symlinks=False)
    shutil.copy2(requirements, app / 'requirements.txt')
    shutil.copy2(source / 'requirements-vst3.txt', app / 'requirements-vst3.txt')
    # Optional Studio runtimes are installed explicitly after deployment; their
    # recipes must survive RPM/DEB staging without merging ML dependencies.
    for recipe in ('requirements-studio-basic-pitch.txt','requirements-studio-yourmt3.txt'):
        shutil.copy2(source / recipe, app / recipe)
    (app / 'scripts').mkdir(exist_ok=True)
    shutil.copy2(source / 'scripts/install_studio_yourmt3.py', app / 'scripts/install_studio_yourmt3.py')
    for helper in ('install_music_assets.py','verify_music_hardware.py'):
        shutil.copy2(source/'scripts'/helper,app/'scripts'/helper)
    shutil.copytree(source/'native/third_party/oddvoices',app/'native/third_party/oddvoices',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (app/'native/third_party/tinysoundfont').mkdir(parents=True)
    shutil.copy2(source/'native/third_party/tinysoundfont/LICENSE',app/'native/third_party/tinysoundfont/LICENSE')
    (app / 'docs').mkdir(exist_ok=True)
    for guide in ('YOURMT3_RUNTIME_R210.md','YOURMT3_RUNTIME_R210_EN.md','MUSIC_ASSETS_AND_LICENSES_R210.md','MUSIC_ASSETS_AND_LICENSES_R210_EN.md'):
        shutil.copy2(source / 'docs' / guide, app / 'docs' / guide)
    # The native RPM/DEB payload must carry the exact application identity.
    for filename in ('VERSION', 'REVISION', 'BUILD_INFO', 'RELEASE_CHANNEL'):
        metadata = source / filename
        if not metadata.is_file():
            raise ValueError(f'Missing release metadata: {filename}')
        shutil.copy2(metadata, app / filename)
    import importlib.util
    spec = importlib.util.spec_from_file_location('mta_build_audio_core', source / 'scripts/build_audio_core.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build = module.build
    import tempfile
    with tempfile.TemporaryDirectory(prefix='mta-server-dsp-') as work:
        binary = build(source, Path(work))
        (app / 'bin').mkdir()
        shutil.copy2(binary, app / 'bin' / binary.name)
    # A private, target-built display also supports EL10 without Xorg/Xvfb RPMs.
    run([sys.executable,str(source/'scripts/build_server_display.py'),'--output',str(app/'bin')])
    # Compile the pinned host ABI before resolving the offline dependency set.
    with tempfile.TemporaryDirectory(prefix='mta-vst3-host-') as work:
        run([sys.executable,str(source/'scripts/build_vst3_runtime.py'),'--wheel-dir',str(Path(work)/'wheels')])
        for wheel in (Path(work)/'wheels').glob('*.whl'):shutil.copy2(wheel,wheels/wheel.name)
    # Download the full transitive closure. No sdists, no editable/VCS builds.
    run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--no-cache-dir',
         '--dest', str(wheels), '--find-links',str(wheels), '-r', str(app / 'requirements.txt')])
    scripts = Path(__file__).resolve().parent
    run([sys.executable, str(scripts / 'wheelhouse_lock.py'), 'create', str(stage)])
    run([sys.executable, str(scripts / 'verify_offline_runtime.py'), str(stage), '--write-proof'])
    run([sys.executable, str(scripts / 'validate_stage.py'), str(stage)])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path('.'))
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--requirements', type=Path, default=Path('requirements.txt'))
    args = parser.parse_args()
    prepare(args.source.resolve(), args.stage.resolve(), args.requirements.resolve())
    print(f'Release-ready offline runtime: {args.stage}')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
