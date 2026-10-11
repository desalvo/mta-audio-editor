#!/usr/bin/env python3
"""User-managed ACE-Step local service launcher; model downloads happen upstream on first use.

Never runs arbitrary shell scripts from the network. An operator installs upstream
ACE-Step in a dedicated environment first; only an absolute executable is accepted.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys


def launch(executable: str, *, model_dir: str, confirm_download: bool = False) -> int:
    path = Path(executable)
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError("Use an absolute, installed ACE-Step executable (no symlinks)")
    root = Path(model_dir).expanduser().resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not confirm_download and not any(root.iterdir()):
        raise RuntimeError("Models may download on first use; accept explicitly with --allow-model-download")
    env = dict(os.environ)
    env['HF_HOME'] = str(root / 'huggingface')
    env['ACESTEP_MODE'] = 'api'
    # Official CLI reads its model paths and downloads missing checkpoints itself.
    return subprocess.call([str(path)], env=env)


def main() -> int:
    parser = argparse.ArgumentParser(description='Start an operator-installed ACE-Step API with persistent model cache')
    parser.add_argument('--executable', required=True)
    parser.add_argument('--model-dir', default=str(Path.home() / '.cache' / 'mta-audio-editor' / 'ace-step'))
    parser.add_argument('--allow-model-download', action='store_true')
    args = parser.parse_args()
    try:
        return launch(args.executable, model_dir=args.model_dir, confirm_download=args.allow_model_download)
    except (ValueError, RuntimeError, OSError) as error:
        print(f'ACE-Step: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
