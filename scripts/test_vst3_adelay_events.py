#!/usr/bin/env python3
"""Real SDK reference acceptance for opt-in sample-accurate VST3 automation IPC."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit('usage: test_vst3_adelay_events.py <probe> <adelay.vst3>')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from native.vst3_probe.probe import resolve_module_binary
    from native.vst3_probe.native_chain import NativeChainError
    from native.vst3_probe.stream_worker import NativeVST3Worker, ParameterPoint
    executable, bundle = sys.argv[1:]
    os.environ['MTA_VST3_PATHS'] = str(Path(bundle).resolve().parent)
    meta = json.loads(subprocess.check_output([executable, str(resolve_module_binary(Path(bundle)))],
                                               text=True, timeout=25))
    cid = next(info['cid'] for info in meta['classes']
               if info['name'] == 'ADelay' and info['category'] == 'Audio Module Class')
    for channels in (1, 2):
        for rate in (44100, 48000, 96000):
            with NativeVST3Worker((bundle, cid), executable, channels=channels, sample_rate=rate,
                                  timeout=20, events_enabled=True) as worker:
                for length in (1, 17, 128, 512, 31):
                    signal = [0.125] * (length * channels)
                    params = [ParameterPoint(100, min(4, length - 1), 0.25)]
                    out = worker.process_with_events(signal, parameters=params)
                    assert len(out) == len(signal)
                try:
                    worker.process_with_events([0.0] * channels * 8,
                                               parameters=[ParameterPoint(0xffffffff, 0, 0.5)])
                except NativeChainError:
                    pass
                else:
                    raise AssertionError('Worker must reject unsupported parameter IDs')
            print(f'ADelay event IPC {rate} Hz {channels}ch: OK')


if __name__ == '__main__':
    main()
