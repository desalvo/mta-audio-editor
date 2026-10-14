#!/usr/bin/env python3
"""Run one deterministic, bounded portion of the complete Python test tree.

File-level partitioning keeps each test module and its fixtures within one worker.
The command is intentionally fail-closed: missing tests, timeouts, and missing
JUnit XML yield nonzero exit status and a diagnostic JSON report.
"""
import argparse
import hashlib
import json
import signal
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def partition(files, shard_count):
    if shard_count < 1:
        raise ValueError('shard_count must be positive')
    groups = [[] for _ in range(shard_count)]
    for path in sorted(files):
        digest = hashlib.sha256(path.as_posix().encode('utf-8')).digest()
        groups[int.from_bytes(digest[:8], 'big') % shard_count].append(path)
    return groups


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shards', type=int, default=8)
    parser.add_argument('--shard', type=int, required=True)
    parser.add_argument('--timeout', type=int, default=3600)
    parser.add_argument('--output-dir', type=Path, default=Path('regression-reports'))
    parser.add_argument('--list-only', action='store_true')
    args = parser.parse_args(argv)
    if args.shards < 1 or not 0 <= args.shard < args.shards or args.timeout < 1:
        parser.error('Invalid shard selection or timeout')
    files = sorted(Path('tests').glob('test_*.py'))
    if not files:
        parser.error('No test modules found; run from project root')
    selected = partition(files, args.shards)[args.shard]
    if not selected:
        parser.error('Selected shard is empty; decrease --shards')
    if args.list_only:
        print('\n'.join(str(p) for p in selected))
        return 0
    args.output_dir.mkdir(parents=True, exist_ok=True)
    label = f'shard-{args.shard:02d}-of-{args.shards:02d}'
    junit = args.output_dir / (label + '.xml')
    report = args.output_dir / (label + '.json')
    command = [sys.executable, '-m', 'pytest', '-o', 'faulthandler_timeout=240',
               '--durations=20', '-ra', f'--junitxml={junit}', *map(str, selected)]
    start = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(command, env={**os.environ, 'PYTHONPATH': '.'},
                            start_new_session=(os.name == 'posix'))
    try:
        code = proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'posix':
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        proc.wait()
        code = 124
    duration = round(time.monotonic() - start, 2)
    counts = None
    if junit.is_file():
        try:
            xml = ET.parse(junit).getroot()
            suites = [xml] if xml.tag == 'testsuite' else xml.findall('.//testsuite')
            counts = {key: sum(int(s.get(key, 0)) for s in suites)
                      for key in ('tests', 'failures', 'errors', 'skipped')}
        except (ET.ParseError, ValueError):
            counts = None
    if counts is None:
        code = code or 2
    payload = {'shard': args.shard, 'shards': args.shards,
               'modules': len(selected), 'seconds': duration, 'exit_code': code,
               'timed_out': timed_out, 'junit': str(junit) if counts else None,
               'counts': counts}
    report.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    print(json.dumps(payload, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
