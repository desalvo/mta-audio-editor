#!/usr/bin/env python3
"""Fail-closed certification of all deterministic global regression shards."""
import argparse
import json
from pathlib import Path
import sys


def verify(directory: Path, shards: int):
    if shards < 1:
        raise ValueError('shards must be positive')
    issues = []
    results = []
    for index in range(shards):
        name = f'shard-{index:02d}-of-{shards:02d}.json'
        candidates = list(directory.rglob(name))
        if len(candidates) != 1:
            issues.append(f'{name}: expected exactly one report, got {len(candidates)}')
            continue
        try:
            entry = json.loads(candidates[0].read_text())
            counts = entry['counts']
            if entry['shard'] != index or entry['shards'] != shards:
                raise ValueError('shard identity mismatch')
            if entry['exit_code'] != 0 or entry['timed_out']:
                raise ValueError('shard execution failed or timed out')
            if not isinstance(counts, dict) or counts['tests'] < 1 or counts['failures'] or counts['errors']:
                raise ValueError('missing tests or failing tests')
            if not entry['junit']:
                raise ValueError('missing JUnit report')
            results.append(entry)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            issues.append(f'{name}: {exc}')
    summary = {'shards_expected': shards, 'shards_valid': len(results),
               'tests': sum(e['counts']['tests'] for e in results),
               'failures': sum(e['counts']['failures'] for e in results),
               'errors': sum(e['counts']['errors'] for e in results),
               'issues': issues, 'passed': not issues and len(results) == shards}
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reports', type=Path, default=Path('regression-reports'))
    p.add_argument('--shards', type=int, default=8)
    args = p.parse_args(argv)
    summary = verify(args.reports, args.shards)
    print(json.dumps(summary, indent=2))
    return 0 if summary['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
