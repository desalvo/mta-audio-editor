#!/usr/bin/env python3
"""Compatibility CLI for unsupported opaque ACE-Step launchers.

Use MTA's managed desktop integration instead; a supplied executable has no
verifiable checkpoint loader contract, even with model download consent.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

if not __package__:sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def launch(executable: str, *, model_dir: str, confirm_download: bool = False) -> int:
    from app.model_license_policy import evaluate_model
    evaluate_model('ace-step')
    path = Path(executable)
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError("Use an absolute, installed ACE-Step executable (no symlinks)")
    # A launcher's pathname or consent to download cannot identify its loader
    # or model. The managed desktop service is a separate fixed integration.
    from app.ai_adapter_identity import deny_opaque_executor
    deny_opaque_executor()


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
