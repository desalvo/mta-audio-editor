#!/usr/bin/env python3
"""Read-only periodic license check. Does not auto-update reviewed source pins."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def review(fetch=None):
    data=json.loads((ROOT/'app/optional_plugins_catalog.json').read_text())
    due=dt.datetime.now(dt.timezone.utc).date()>dt.date.fromisoformat(data['reviewed_at'])+dt.timedelta(days=data['review_interval_days'])
    results=[]
    def download(url):
        with urllib.request.urlopen(url,timeout=30) as response:  # noqa: S310 -- fixed HTTPS GitHub upstream
            return response.read(1024*1024)
    fetch=fetch or download
    for p in data['plugins']:
        if not p['enabled']:continue
        url='https://raw.githubusercontent.com/'+p['repo']+'/'+p['revision']+'/LICENSE'
        actual=hashlib.sha256(fetch(url)).hexdigest()
        results.append({'id':p['id'],'revision':p['revision'],'license_matches':actual==p['license_sha256'],'manual_review_due':due})
    return results


if __name__=='__main__':
    results=review();print(json.dumps(results,indent=2))
    if any(not r['license_matches'] or r['manual_review_due'] for r in results):raise SystemExit(1)
