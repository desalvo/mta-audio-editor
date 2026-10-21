#!/usr/bin/env python3
"""Offline inventory of the separately supplied neural validation bundle.

Never imports model code, deserializes checkpoints, approves licenses or
downloads assets. Hash verification is not inference or model admission.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def inspect(root):
    root=Path(root).resolve(strict=True)
    manifest=json.loads((root/'ASSET_MANIFEST.json').read_text(encoding='utf-8'))
    checked=[]
    for item in manifest['files']:
        relative=Path(item['path'])
        path=root/relative
        if relative.is_absolute() or '..' in relative.parts or path.is_symlink():
            raise ValueError('Unsafe asset path')
        if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
            raise ValueError('Asset must be a regular file inside the bundle')
        with path.open('rb') as stream:
            digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if path.stat().st_size!=item['bytes'] or digest!=item['sha256']:
            raise ValueError('Asset integrity mismatch: '+item['path'])
        if path.suffix in ('.zip','.whl'):
            with zipfile.ZipFile(path) as archive:
                bad=archive.testzip()
                if bad is not None:raise ValueError('Asset CRC mismatch: '+item['path'])
        checked.append({'path':item['path'],'bytes':item['bytes'],'sha256':digest})
    return {'schema':'mta-neural-assets-audit-1','verified':checked,
            'inference_executed':False,'licenses_approved':False,
            'note':'Source/weight inventory only. Verify runtime, matching configuration, all auxiliary assets and rights separately.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset_root',type=Path)
    args=parser.parse_args()
    print(json.dumps(inspect(args.asset_root),indent=2))


if __name__=='__main__':main()
