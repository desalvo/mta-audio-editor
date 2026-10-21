#!/usr/bin/env python3
"""Conservative periodic cache cleanup. Defaults to dry-run."""
import argparse
import json
from app.ai_result_cache import purge_expired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Remove expired entries (default dry-run)')
    args = parser.parse_args()
    print(json.dumps(purge_expired(dry_run=not args.apply), sort_keys=True))


if __name__ == '__main__':
    main()
