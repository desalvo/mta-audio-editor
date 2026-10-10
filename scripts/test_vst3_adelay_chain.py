#!/usr/bin/env python3
"""End-to-end acceptance: native PCM passes through a real ADelay VST3 in isolation.
Requires MTA_VST3_PATHS to contain the ADelay plugin bundle's parent.
Usage: python scripts/test_vst3_adelay_chain.py <native-probe> <ADelay-bundle>
"""
import math
from pathlib import Path
import subprocess
import sys
import json


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: test_vst3_adelay_chain.py <probe> <adelay.vst3>')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from native.vst3_probe.native_chain import FRAMES, render_native_chain
    probe, bundle = sys.argv[1:]
    from native.vst3_probe.probe import resolve_module_binary
    scan = subprocess.run([probe, str(resolve_module_binary(Path(bundle)))], text=True,
                          capture_output=True, check=True, timeout=20)
    classes = json.loads(scan.stdout)['classes']
    cid, = [item['cid'] for item in classes if item['name'] == 'ADelay' and item['category'] == 'Audio Module Class']
    audio = [0.125*math.sin(2*math.pi*440*i/48000) for i in range(FRAMES)]
    rendered = render_native_chain(audio, [(bundle, cid)], probe, timeout=20)
    assert len(rendered) == FRAMES
    assert all(math.isfinite(v) for v in rendered)
    assert sum(v*v for v in rendered) > 1.0
    print('ADelay native PCM chain: real audio, 65536 samples, isolated process, finite nonzero output')

if __name__ == '__main__':
    main()
