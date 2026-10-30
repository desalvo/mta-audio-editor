"""Opt-in end-to-end smoke test for an installed ACE-Step worker.

Unlike health/capability probes, this actually requests audio generation. It does
not assert artistic quality or guarantee that source structure is preserved.
"""
from __future__ import annotations

from .service_admission import admitted

import argparse
import json
import math
from pathlib import Path
import struct
import tempfile
import wave

from .ai_worker_protocol import WorkerUnavailable, configured_worker


@admitted('ace-diagnostic')
def test_live_inference(*, seconds: float = 5.0, timeout_seconds: int = 1200) -> dict:
    """Generate an original synthetic input WAV and demand a decodable WAV output."""
    if not 1 <= seconds <= 15:
        raise ValueError('smoke input must last 1-15 seconds')
    from .model_license_policy import evaluate_model
    evaluate_model('ace-step')
    if configured_worker() is None:
        return {'attempted': False, 'verified': False, 'reason': 'worker_not_configured'}
    rate = 44100
    with tempfile.TemporaryDirectory(prefix='mta-ace-live-') as tmp:
        source = Path(tmp) / 'input.wav'
        frames = int(seconds * rate)
        with wave.open(str(source), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            for start in range(0, frames, 4096):
                batch = bytearray()
                for i in range(start, min(start + 4096, frames)):
                    sample = int(8000 * math.sin(2 * math.pi * 220 * i / rate))
                    batch.extend(struct.pack('<h', sample))
                wav.writeframesraw(batch)
        import subprocess
        import sys
        worker = configured_worker()
        output = Path(tmp) / 'generated.wav'
        try:
            evaluate_model('ace-step')
            completed = subprocess.run(([sys.executable, str(worker)] if worker.suffix == '.py' else [str(worker)]) + ['--smoke-input', str(source), '--output', str(output)],
                cwd=tmp, capture_output=True, timeout=timeout_seconds, check=False)
        except subprocess.TimeoutExpired:
            return {'attempted': True, 'verified': False, 'reason': 'timeout'}
        if completed.returncode != 0:
            return {'attempted': True, 'verified': False, 'reason': 'worker_smoke_failed'}
        evaluate_model('ace-step')
        from .ai_worker_protocol import verify_preview_wav
        try:
            meta = verify_preview_wav(output)
        except (OSError, ValueError, wave.Error):
            return {'attempted': True, 'verified': False, 'reason': 'invalid_generated_audio'}
        return {'attempted': True, 'verified': True, 'reason': 'audio_generated', 'audio': meta,
                'warning': 'This only verifies a completed audio job, not musical fidelity.'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Opt-in live audio inference test (needs installed ACE-Step)')
    parser.add_argument('--seconds', type=float, default=5.0)
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    try:
        result = test_live_inference(seconds=args.seconds, timeout_seconds=args.timeout)
    except (ValueError, OSError, WorkerUnavailable) as exc:
        result = {'attempted': False, 'verified': False, 'reason': str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
