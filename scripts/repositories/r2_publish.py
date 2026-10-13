#!/usr/bin/env python3
"""Opt-in Cloudflare R2 staging publisher; refuses to run until explicitly enabled.

Uses S3-compatible endpoint and credentials provided at execution time. The signed
repo tree is produced by the same GPG pipeline as Pages. No destructive prune here:
activation requires a separately reviewed cleanup strategy.
"""
import argparse
import hashlib
import os
from pathlib import Path


def publish(root, bucket, endpoint, channel, *, dry_run=True):
    if channel not in ('early', 'stable'):
        raise ValueError('Invalid repository channel')
    if not (root / 'apt' / channel / 'InRelease').is_file():
        raise ValueError('Missing signed APT metadata')
    for target in ('el9', 'el10'):
        if not (root / 'rpm' / channel / target / 'repodata' / 'repomd.xml.asc').is_file():
            raise ValueError(f'Missing signed {target} RPM metadata')
    files = sorted(p for p in root.rglob('*') if p.is_file() and p.relative_to(root).parts[0] in ('apt', 'rpm'))
    files = [p for p in files if p.relative_to(root).parts[1] == channel]
    if dry_run:
        return [{'key': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size} for p in files]
    if os.environ.get('MTA_R2_PUBLISH_ENABLED') != 'true':
        raise RuntimeError('R2 publishing is disabled; explicitly enable after review')
    import boto3
    client = boto3.client('s3', endpoint_url=endpoint)
    # Packages first, indexes last: clients never discover an index before its payload.
    def priority(p):
        name = p.name
        if name in ('InRelease', 'Release', 'Release.gpg', 'repomd.xml', 'repomd.xml.asc'):
            return 2
        if '/repodata/' in p.as_posix() or name in ('Packages', 'Packages.gz'):
            return 1
        return 0
    for path in sorted(files, key=priority):
        key = path.relative_to(root).as_posix()
        content_type = 'application/octet-stream'
        if path.suffix == '.gz':
            content_type = 'application/gzip'
        elif path.suffix in ('.xml', '.html'):
            content_type = 'text/xml' if path.suffix == '.xml' else 'text/html'
        client.upload_file(str(path), bucket, key, ExtraArgs={'ContentType': content_type})
        remote = client.head_object(Bucket=bucket, Key=key)
        if remote['ContentLength'] != path.stat().st_size:
            raise RuntimeError(f'R2 upload verification failed: {key}')
    return len(files)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--channel', required=True, choices=['early', 'stable'])
    parser.add_argument('--bucket', default=os.environ.get('MTA_R2_BUCKET', ''))
    parser.add_argument('--endpoint', default=os.environ.get('MTA_R2_ENDPOINT', ''))
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute and (not args.bucket or not args.endpoint.startswith('https://')):
        parser.error('R2 bucket and HTTPS endpoint required for execution')
    print(publish(args.root, args.bucket, args.endpoint, args.channel, dry_run=not args.execute))


if __name__ == '__main__':
    main()
