#!/usr/bin/env python3
"""Admin CLI for reviewed local neural bundles; no implicit downloads or rights."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import studio_asset_registry as assets


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('install');p.add_argument('zip',type=Path);p.add_argument('--licenses-reviewed',action='store_true',required=True)
    commands.add_parser('list')
    for name in ('verify','enable','disable','remove'):
        p=commands.add_parser(name);p.add_argument('id')
    args=parser.parse_args()
    if args.command=='install':value=assets.install(args.zip)
    elif args.command=='list':value=assets.catalog()
    elif args.command=='verify':
        m=assets.manifest(args.id,verify=True);value={'id':m['id'],'integrity_verified':True,'real_inference_validated':False}
    elif args.command in ('enable','disable'):value=assets.configure(args.id,args.command=='enable')
    else:value=assets.remove(args.id)
    print(json.dumps(value,indent=2))

if __name__=='__main__':main()
