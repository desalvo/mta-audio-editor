#!/usr/bin/env python3
"""Offline MR-MT3 inference with durable, input-bound per-window checkpoints.

Requires separately installed, reviewed mt3-infer, transformers, torch and safetensors.
Output window files are numerical token IDs, never executable pickles. Each run
uses its own source-audio, model and source-revision fingerprints.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as inp:
        for block in iter(lambda: inp.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.mrmt3-', suffix='.json', delete=False) as out:
        temporary = Path(out.name)
        json.dump(payload, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def accept_window(path, identity, index, n_windows):
    """Reject stale, truncated, or incorrectly ordered results before reuse."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Corrupted saved window {index}: {exc}') from exc
    if (data.get('identity') != identity or data.get('index') != index
            or data.get('window_count') != n_windows):
        raise ValueError(f'Window {index} does not belong to this inference')
    tokens = data.get('tokens')
    if (not isinstance(tokens, list) or len(tokens) > 8192
            or any(type(t) is not int or t < 0 for t in tokens)):
        raise ValueError(f'Invalid tokens in saved window {index}')
    start = data.get('start_time')
    if type(start) not in (int, float) or not 0 <= start < 86400:
        raise ValueError(f'Invalid start_time in saved window {index}')
    return data


def serializable_tokens(tokens):
    """Convert MR-MT3 NumPy or Torch token vectors to validated token IDs."""
    import numpy as np

    if hasattr(tokens, 'detach'):
        tokens = tokens.detach().cpu().numpy()
    tokens = np.asarray(tokens)
    if tokens.ndim != 1 or tokens.dtype.kind not in ('i', 'u'):
        raise ValueError('Model returned non-integral or non-vector tokens')
    if tokens.size > 8192:
        raise ValueError('Model returned too many tokens')
    return [int(token) for token in tokens[tokens >= 0].tolist()]


def budget_exhausted(started, now, completed, seconds):
    """Never interrupt a forward pass; stop only between completed windows."""
    return bool(completed and seconds and now - started >= seconds)

def gpu_backend(torch):
    """ROCm shares the torch.cuda interface; distinguish the installed wheel."""
    if not torch.cuda.is_available():
        return None
    version = getattr(torch, 'version', None)
    if getattr(version, 'hip', None):
        return 'rocm'
    if getattr(version, 'cuda', None):
        return 'cuda'
    return None


def resolve_device(requested, torch):
    """Require the chosen vendor; PyTorch ROCm still uses device='cuda'."""
    if requested == 'cpu':
        return 'cpu'
    if requested not in ('cuda', 'rocm', 'gpu', 'auto'):
        raise ValueError('Unsupported inference device')
    backend = gpu_backend(torch)
    if requested == 'auto':
        return 'cuda' if backend else 'cpu'
    if backend is None:
        raise RuntimeError('GPU requested but unavailable or incompatible; no CPU fallback')
    if requested in ('rocm', 'cuda') and requested != backend:
        raise RuntimeError(f'{requested} requested but {backend} backend was detected')
    return 'cuda'


def gpu_memory_ok(torch, required_free_gib):
    if not torch.cuda.is_available():
        return False
    free, _total = torch.cuda.mem_get_info()
    return free >= required_free_gib * 1024 ** 3


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True, help='Safetensors checkpoint')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-windows', type=int, default=4,
                        help='Compute at most N new windows per invocation (0 means all)')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--device', choices=('cpu','cuda','rocm','gpu','auto'), default='cpu',
                        help='cuda=NVIDIA, rocm=AMD HIP, gpu=either; ROCm uses torch device cuda internally')
    parser.add_argument('--min-free-gpu-gib', type=float, default=3.0,
                        help='Refuse CUDA run if less free GPU memory; do not starve production')
    parser.add_argument('--time-budget-seconds', type=float, default=0,
                        help='Stop after the current completed window once the elapsed budget is reached (0 disables)')
    args = parser.parse_args(argv)
    if (args.max_windows < 0 or not 1 <= args.threads <= 64
            or not 0 <= args.time_budget_seconds <= 86400
            or not 0 <= args.min_free_gpu_gib <= 1024):
        parser.error('Invalid window/thread limits')
    for path in (args.audio, args.model):
        if not path.is_file():
            parser.error(f'File not found: {path}')
    if args.model.suffix != '.safetensors':
        parser.error('Only Safetensors model weights are supported')
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
    # The decoded audio is canonically resampled by ffmpeg before hashing.
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        wav = Path(temp) / 'input.wav'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(args.audio),
                        '-ac', '1', '-ar', '16000', '-c:a', 'pcm_f32le', str(wav)],
                       check=True, timeout=180)
        import numpy as np
        import soundfile as sf
        import torch
        from transformers import T5Config
        from safetensors.torch import load_file
        from mt3_infer.adapters.mr_mt3 import MRMT3Adapter, _import_t5_model
        from app.mrmt3_decode import decode
        wave, rate = sf.read(wav, dtype='float32')
        if rate != 16000 or wave.ndim != 1 or not len(wave) or not np.isfinite(wave).all():
            raise ValueError('Invalid decoded audio')
        duration = len(wave) / rate
        wave = np.pad(wave, (0, (-len(wave)) % 128))
        torch.set_num_threads(args.threads)
        device = resolve_device(args.device, torch)
        if device == 'cuda' and not gpu_memory_ok(torch, args.min_free_gpu_gib):
            raise RuntimeError('Insufficient free GPU memory; refusing to compete with production')
        model = MRMT3Adapter()
        model.model = _import_t5_model()(T5Config.from_dict(model.model_config))
        model.model.load_state_dict(load_file(str(args.model), device='cpu'), strict=True)
        model.model.to(device)
        # MRMT3Adapter.forward() moves its inputs to self.device_str.
        # Without this, CUDA/ROCm weights receive CPU tensors.
        model.device_str = device
        model.model.eval()
        model._initialize_vocab()
        model._model_loaded = True
        features = model.preprocess(wave, rate)
        count = len(features['inputs'])
        identity = {'audio_pcm_sha256': sha256(wav), 'model_sha256': sha256(args.model),
                    'source': 'MRMT3Adapter', 'sample_rate': rate,
                    'duration_samples': int(len(wave)), 'windows': count, 'device': device, 'gpu_backend': gpu_backend(torch) if device == 'cuda' else None}
        manifest = args.output / 'manifest.json'
        if manifest.exists() and json.loads(manifest.read_text()) != identity:
            raise ValueError('Output directory belongs to a different input/model')
        atomic_json(manifest, identity)
        computed = 0
        started = time.monotonic()
        for i in range(count):
            dest = args.output / f'window-{i:05d}.json'
            if accept_window(dest, identity, i, count) is not None:
                continue
            if args.max_windows and computed >= args.max_windows:
                break
            if budget_exhausted(started, time.monotonic(), computed, args.time_budget_seconds):
                break
            with torch.inference_mode():
                result = model.forward({k: v[i:i+1].to(device) if hasattr(v, 'to') else v[i:i+1]
                                        for k, v in features.items()})
            tokens = result['tokens'][0]
            payload = {'identity': identity, 'index': i, 'window_count': count,
                       'tokens': serializable_tokens(tokens),
                       'start_time': float(result['frame_times'][0][0])}
            atomic_json(dest, payload)
            computed += 1
            print(f'computed window {i + 1}/{count}', flush=True)
        saved = [accept_window(args.output / f'window-{i:05d}.json', identity, i, count)
                 for i in range(count)]
        complete = all(x is not None for x in saved)
        if complete:
            predictions = [{'est_tokens': np.asarray(x['tokens'], dtype=np.int64),
                            'start_time': x['start_time']} for x in saved]
            notes, audit = decode(predictions, model.codec, duration)
            atomic_json(args.output / 'prediction.json', {'identity': identity,
                        'real_inference': True, 'duration_seconds': duration,
                        'notes': notes, 'decode_audit': audit})
        print(json.dumps({'complete': complete, 'saved_windows': sum(x is not None for x in saved),
                          'total_windows': count, 'new_windows': computed, 'device': device, 'gpu_backend': gpu_backend(torch) if device == 'cuda' else None}), flush=True)
        return 0 if complete else 2


if __name__ == '__main__':
    sys.exit(main())
