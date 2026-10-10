#!/usr/bin/env python3
"""Real VST3 variable-length mono/stereo acceptance test using ADelay."""
import json
import math
from pathlib import Path
import subprocess
import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: test_vst3_adelay_variable.py <native-probe> <adelay.vst3>')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from native.vst3_probe.native_chain import render_native_chain
    from native.vst3_probe.probe import resolve_module_binary
    executable, plugin = sys.argv[1:]
    binary = resolve_module_binary(Path(plugin))
    payload = json.loads(subprocess.check_output([executable, str(binary)], text=True, timeout=20))
    cid = next(item['cid'] for item in payload['classes'] if item['name'] == 'ADelay' and item['category'] == 'Audio Module Class')
    frames = 70001
    source = [(0.125 * math.sin(2 * math.pi * 440 * i / 48000),
               0.125 * math.sin(2 * math.pi * 440 * (i + 11) / 48000)) for i in range(frames)]
    rendered = render_native_chain(source, [(plugin, cid)], executable, timeout=30)
    assert len(rendered) == frames
    assert all(len(pair) == 2 and all(math.isfinite(x) for x in pair) for pair in rendered)
    assert sum(a*a+b*b for a, b in rendered) > 1.0
    print('ADelay variable stereo PCM: 70001 frames, finite nonzero output')

if __name__ == '__main__':
    main()
