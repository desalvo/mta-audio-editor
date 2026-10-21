#!/usr/bin/env python3
"""Restore an MTA application dump with the service stopped, into empty roots."""
import argparse
import json
from pathlib import Path
from .admin_dump import restore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--queue-dir', type=Path, required=True)
    parser.add_argument('--gpu-dir', type=Path, required=True)
    parser.add_argument('--service-stopped', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(restore(args.archive, data_dir=args.data_dir, queue_dir=args.queue_dir, gpu_dir=args.gpu_dir, service_stopped=args.service_stopped)))
    except Exception as exc:
        parser.exit(1, 'Restore failed: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
