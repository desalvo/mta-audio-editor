#!/usr/bin/env python3
"""Offline YourMT3+ inference on authorized recording with a verified runtime receipt.

Produces strict fixed-protocol prediction JSON for compare_multitrack_models.py.
No ground truth enters inference and no network or server changes are performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def prediction(result):
    """Convert MusicResult to the existing MR-MT3 comparison schema."""
    notes = []
    for part in result.parts:
        for n in part.notes:
            if not part.percussion and part.program is None:
                raise ValueError('Melodic prediction without a GM program')
            notes.append({'program': 0 if part.percussion else part.program,
                          'is_drum': bool(part.percussion), 'pitch': n.pitch,
                          'start_time': n.start_ms / 1000,
                          'end_time': (n.start_ms + n.duration_ms) / 1000})
    return {'notes': notes}


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--backend', choices=('rocm', 'cuda', 'gpu', 'cpu'), default='rocm')
    parser.add_argument('--variant', choices=('nops', 'ps'), default='nops')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.audio.is_file() or args.audio.is_symlink():
        parser.error('Audio must be a real local file')
    if args.output.exists() or args.output.is_symlink():
        parser.error('Output already exists (refusing to overwrite verified evidence)')
    os.environ['MTA_STUDIO_YOURMT3_RUNTIME'] = str(args.runtime.resolve(strict=True))
    os.environ['MTA_STUDIO_YOURMT3_VARIANT'] = args.variant
    os.environ['MTA_STUDIO_YOURMT3_DEVICE'] = args.backend
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    import torch
    from app.yourmt3_adapter import selected_variant, select_inference_device, transcribe, verified_runtime
    select_inference_device(torch, args.backend)
    verified_runtime()
    result = transcribe(args.audio.resolve(), {})
    data = prediction(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_name(args.output.name + '.partial')
    if tmp.exists():
        parser.error('Partial output exists; inspect and remove only after validation')
    try:
        with tmp.open('x', encoding='utf-8') as f:
            json.dump(data, f, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(args.output)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({'model': selected_variant()[0], 'backend': args.backend,
                      'audio_sha256': file_hash(args.audio), 'prediction_sha256': file_hash(args.output),
                      'predicted_notes': len(data['notes']), 'accuracy_certified': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
