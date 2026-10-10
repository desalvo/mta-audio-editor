#!/usr/bin/env python3
"""Real-SDK acceptance for bounded state-continuous, multi-request offline VST3 sessions.

This is intentionally NOT a realtime readiness claim or an interactive IPC test.
"""
from __future__ import annotations
import json
import math
from pathlib import Path
import subprocess
import sys


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit('usage: test_vst3_adelay_session.py <native-probe> <adelay.vst3>')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from native.vst3_probe.offline_session import render_native_session, render_native_session_chain
    from native.vst3_probe.probe import resolve_module_binary
    executable, plugin = sys.argv[1:]
    binary = resolve_module_binary(Path(plugin))
    metadata = json.loads(subprocess.check_output([executable, str(binary)], text=True, timeout=20))
    cid = next(info['cid'] for info in metadata['classes']
               if info['name'] == 'ADelay' and info['category'] == 'Audio Module Class')
    # Uneven request boundaries, including fewer than one 512-frame process block.
    boundaries = (17, 513, 4097, 115536)
    for rate in (44100, 48000, 96000):
        for channels in (1, 2):
            total = sum(boundaries)
            signal = [0.125 * math.sin(2 * math.pi * 440 * (i + 3 * ch) / rate)
                      for i in range(total) for ch in range(channels)]
            offset = 0
            requests = []
            for frames in boundaries:
                count = frames * channels
                requests.append(signal[offset:offset + count])
                offset += count
            rendered = render_native_session(requests, (plugin, cid), executable,
                                             channels=channels, sample_rate=rate, timeout=60)
            assert [len(block) for block in rendered] == [x * channels for x in boundaries]
            flat = [sample for block in rendered for sample in block]
            assert len(flat) == len(signal)
            assert all(math.isfinite(sample) for sample in flat)
            assert sum(sample * sample for sample in flat) > 0.001
            # Request segmentation must not reset plugin state: compare with one request.
            whole = render_native_session([signal], (plugin, cid), executable,
                                          channels=channels, sample_rate=rate, timeout=60)[0]
            assert len(whole) == len(flat)
            error = max(abs(a - b) for a, b in zip(whole, flat))
            assert error < 1e-5, f'session boundary changed output: {error}'
            print(f'ADelay session rate={rate} channels={channels}: {total} frames; diff={error:.3g}')
    # Two actual VST3 processors, kept alive for their own entire session.
    chain = render_native_session_chain(requests, [(plugin, cid), (plugin, cid)], executable,
                                        channels=2, sample_rate=96000, timeout=60)
    assert [len(x) for x in chain] == [n * 2 for n in boundaries]
    assert all(math.isfinite(x) for block in chain for x in block)
    print('ADelay two-insert bounded session chain: OK')


if __name__ == '__main__':
    main()
