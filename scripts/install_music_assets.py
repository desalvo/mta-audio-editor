#!/usr/bin/env python3
"""Explicit optional GM/CC0 singing installation, using the same GUI recipes."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset',choices=['gm','air','cicada','quake'])
    parser.add_argument('--accept-licenses',action='store_true',required=True,
        help='Confirm review of docs/MUSIC_ASSETS_AND_LICENSES_R210.md and upstream notices')
    parser.add_argument('--offline-gm-archive',type=Path)
    args=parser.parse_args()
    def progress(phase,done,total):
        print(f'{phase}: {done}/{total}' if total else phase,flush=True)
    if args.asset=='gm':
        from app.gm_installer import install
        result=install(lambda:False,progress,archive=args.offline_gm_archive)
    else:
        if args.offline_gm_archive:parser.error('--offline-gm-archive is valid only for gm')
        from app.vocal_banks import install
        result=install(args.asset,lambda:False,progress)
    print(result)


if __name__=='__main__':main()
