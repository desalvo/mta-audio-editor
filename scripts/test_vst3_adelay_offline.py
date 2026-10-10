#!/usr/bin/env python3
"""Run the optional SDK ADelay offline acceptance smoke test.

Build ADelay from a separately obtained Steinberg SDK checkout, then call:
  python scripts/test_vst3_adelay_offline.py <probe-executable> <adelay.so>
No SDK sources or plugin binaries are distributed with MTA Audio Editor.
"""
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: test_vst3_adelay_offline.py <probe> <adelay.so>', file=sys.stderr)
        return 2
    probe, plugin = (Path(value).resolve() for value in sys.argv[1:])
    scan = subprocess.run([str(probe), str(plugin)], capture_output=True, text=True,
                          timeout=20, check=True)
    classes = json.loads(scan.stdout)['classes']
    matches = [item['cid'] for item in classes if item['name'] == 'ADelay'
               and item['category'] == 'Audio Module Class']
    if len(matches) != 1:
        raise AssertionError('Exactly one ADelay audio component is required')
    run = subprocess.run([str(probe), str(plugin), '--offline', matches[0]],
                         capture_output=True, text=True, timeout=20, check=True)
    data = json.loads(run.stdout)
    for field in ('instance_created', 'instance_initialized', 'processing_setup_succeeded',
                  'offline_activated', 'offline_processing_started',
                  'offline_process_succeeded', 'offline_deactivated', 'instance_terminated'):
        if data.get(field) is not True:
            raise AssertionError(f'{field} failed: {data}')
    assert data['offline_blocks_processed'] == 16, data
    assert data['offline_input_energy'] > 0, data
    assert data['offline_nonfinite_samples'] == 0, data
    assert data['native_host_ready'] is False, data
    print('ADelay VST3 SDK acceptance: 16 offline blocks, finite samples, clean teardown')
    return 0


if __name__ == '__main__':
    sys.exit(main())
