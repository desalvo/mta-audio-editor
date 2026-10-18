#!/usr/bin/env python3
"""Wait until GitHub Pages serves the exact signed DNF repository indexes.

Do not permit old GitHub Release RPM assets to be deleted until both target
repomd.xml files are publicly available byte-for-byte. Cache-bust every request
and show useful hashes if Pages has not deployed by the timeout.
"""
import argparse
import hashlib
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, token: str, timeout: float) -> bytes:
    # A changing query string prevents intermediate caches from returning a
    # previous generation of repomd.xml when the Pages deployment is delayed.
    sep = '&' if '?' in url else '?'
    request = Request(
        url + sep + urlencode({'mta_verify': token}),
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'User-Agent': 'mta-pages-publish-verify'},
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def verify(staging: Path, base: str, channel: str, run_id: str, max_wait: float = 900,
           interval: float = 15, timeout: float = 20) -> bool:
    expected = {}
    for target in ('el9', 'el10'):
        path = staging / 'rpm' / channel / target / 'repodata' / 'repomd.xml'
        expected[target] = sha256(path.read_bytes())
        print(f'{target} signed local repomd SHA-256: {expected[target]}', flush=True)
    deadline = time.monotonic() + max_wait
    attempt = 0
    while True:
        attempt += 1
        good = True
        for target in ('el9', 'el10'):
            root = f'{base.rstrip("/")}/rpm/{channel}/{target}'
            for path in ('repodata/repomd.xml', 'repodata/repomd.xml.asc', 'packages/'):
                try:
                    data = fetch(f'{root}/{path}', f'{run_id}-{attempt}', timeout)
                    if path == 'repodata/repomd.xml':
                        actual = sha256(data)
                        if actual != expected[target]:
                            print(f'Pages {target} not current: public={actual}, expected={expected[target]} (attempt {attempt})', flush=True)
                            good = False
                    elif not data:
                        print(f'Pages {target}/{path} is empty (attempt {attempt})', flush=True)
                        good = False
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    print(f'Pages {target}/{path} unavailable: {exc} (attempt {attempt})', flush=True)
                    good = False
        if good:
            print(f'Public Pages signed metadata and download listings current for el9 and el10 (attempt {attempt})', flush=True)
            return True
        if time.monotonic() >= deadline:
            print('Public Pages still stale or unavailable; refusing RPM asset cleanup. '
                  'Inspect Pages deployment workflow/status and Pages branch settings.', flush=True)
            return False
        time.sleep(min(interval, max(0, deadline - time.monotonic())))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--staging', type=Path, required=True)
    parser.add_argument('--base', required=True, help='Pages base URL, e.g. https://owner.github.io/repo')
    parser.add_argument('--channel', choices=('early', 'stable'), required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--max-wait', type=float, default=900)
    args = parser.parse_args()
    if not verify(args.staging, args.base, args.channel, args.run_id, max_wait=args.max_wait):
        raise SystemExit(4)


if __name__ == '__main__':
    main()
