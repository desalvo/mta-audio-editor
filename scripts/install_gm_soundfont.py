#!/usr/bin/env python3
"""Install an administrator-reviewed local SF2; no downloads, no overwrites."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.gm_banks import install, LICENSES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sf2',type=Path)
    parser.add_argument('--id',required=True,help='sf2-<unique-bank-name>')
    parser.add_argument('--name',required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--license',required=True,choices=sorted(LICENSES))
    parser.add_argument('--license-file',type=Path,required=True)
    parser.add_argument('--evidence-url',required=True)
    parser.add_argument('--rights-reviewed',action='store_true',required=True)
    args=parser.parse_args()
    print(json.dumps(install(args.sf2,args.id,name=args.name,sha256=args.sha256,license_id=args.license,
        license_file=args.license_file,evidence_url=args.evidence_url,rights_reviewed=args.rights_reviewed),indent=2))

if __name__=='__main__':main()
