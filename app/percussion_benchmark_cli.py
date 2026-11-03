"""Local developer inspection/export tools; inference uses authenticated API jobs.

Usage: python -m app.percussion_benchmark_cli --data-root /path/to/data catalog
There is deliberately no local run/approve command that could impersonate an
authenticated scheduler owner or a human evaluator.
"""
import argparse
import json
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, help='Explicit local MTA data directory')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('prepare', help='Prepare only the original synthetic diagnostic corpus')
    commands.add_parser('catalog', help='Inspect candidates, rights/installation states and datasets')
    commands.add_parser('list', help='List local persistent campaigns')
    for action in ('show', 'reports', 'export'):
        command = commands.add_parser(action)
        command.add_argument('campaign_id')
        if action == 'export':
            command.add_argument('--output', type=Path, required=True, help='New ZIP path; existing files are never overwritten')
    args = parser.parse_args(argv)
    from . import auth, percussion_benchmark as benchmark, service_admission
    from .regime_operation_fence import FenceBlocked
    if args.data_root is not None:
        if not args.data_root.is_absolute() or args.data_root.is_symlink():
            parser.error('--data-root must be an absolute, nonsymbolic directory')
        auth.DATA_ROOT = args.data_root
    try:
        with service_admission.operation('percussion-benchmark-cli'):
            if args.action == 'prepare':
                result = benchmark.prepare_synthetic()
            elif args.action == 'catalog':
                result = benchmark.catalog()
            elif args.action == 'list':
                result = benchmark.campaigns()
            elif args.action == 'show':
                result = benchmark.get(args.campaign_id)
            elif args.action == 'reports':
                result = benchmark.reports(args.campaign_id)
            else:
                output = args.output
                if output.is_symlink() or not output.parent.is_dir():
                    raise ValueError('Export needs an existing nonsymbolic parent directory')
                data = benchmark.export(args.campaign_id)
                with output.open('xb') as stream:
                    stream.write(data)
                result = {'output': str(output.resolve()), 'bytes': len(data)}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, FenceBlocked) as exc:
        print('Benchmark command failed: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
