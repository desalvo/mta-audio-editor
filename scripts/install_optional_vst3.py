#!/usr/bin/env python3
"""Optional source build: --list, --plugins all or comma-separated catalog IDs."""
import argparse
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
if (root/'app').is_dir():sys.path.insert(0,str(root))
from app import optional_plugins as plugins


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--plugins',default='')
    parser.add_argument('--accept-licenses',action='store_true')
    args=parser.parse_args()
    if args.list:print(json.dumps(plugins.catalog(),indent=2));return
    if not args.plugins or not args.accept_licenses:parser.error('--plugins and --accept-licenses are required; inspect --list first')
    ids=[p['id'] for p in plugins.catalog()['plugins'] if p['available']] if args.plugins=='all' else args.plugins.split(',')
    results=plugins.install(ids,lambda stage,message:print(stage+': '+message,flush=True))
    print(json.dumps(results,indent=2))
    if any('error' in r for r in results):raise SystemExit(1)


if __name__=='__main__':main()
