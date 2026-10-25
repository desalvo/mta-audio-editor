"""Run all Bandit checks and require a complete source-bound reviewed ledger.

No baseline regeneration or automatic approval. An audit is valid only for the
exact app source inventory and the exact unsuppressed scan it reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import tempfile


class ReviewInvalid(ValueError):
    pass


def source_hashes(root):
    paths=sorted((root/'app').rglob('*.py'))
    if not paths:raise ReviewInvalid('Missing application source inventory')
    if any(p.is_symlink() for p in paths):raise ReviewInvalid('Symbolic application source is not reviewable')
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def finding_identity(row):
    fields={k:row[k] for k in ('filename','test_id','test_name','issue_severity','issue_confidence','issue_text','line_number','line_range','col_offset','end_col_offset')}
    fields['code_sha256']=hashlib.sha256(row['code'].encode()).hexdigest()
    return hashlib.sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def validate(root,scan,review):
    if not isinstance(scan,dict) or scan.get('errors')!=[] or not isinstance(scan.get('results'),list):
        raise ReviewInvalid('Incomplete or errored Bandit scan')
    hashes=source_hashes(root)
    if (not isinstance(review,dict) or review.get('schema')!='mta-security-review-1'
            or review.get('source_sha256')!=hashes or not isinstance(review.get('findings'),list)):
        raise ReviewInvalid('Security review is missing or stale for current source')
    metrics=scan.get('metrics',{});totals=metrics.get('_totals',{})
    if set(metrics)-{'_totals'}!=set(hashes) or any(totals.get(k)!=0 for k in ('nosec','skipped_tests','SEVERITY.HIGH')):
        raise ReviewInvalid('Incomplete, suppressed or high-severity scan')
    identities={};counts={'HIGH':0,'MEDIUM':0,'LOW':0}
    for row in scan['results']:
        if row['filename'] not in hashes or row['issue_severity'] not in counts:raise ReviewInvalid('Unknown scan path or severity')
        identity=finding_identity(row)
        if identity in identities:raise ReviewInvalid('Duplicate scan finding')
        identities[identity]=row;counts[row['issue_severity']]+=1
    if any(totals.get('SEVERITY.'+k)!=v for k,v in counts.items()):raise ReviewInvalid('Inconsistent finding totals')
    approved={}
    for item in review['findings']:
        if (not isinstance(item,dict) or set(item)!={'id','disposition','rationale','boundary','verification'}
                or item['id'] in approved or item['id'] not in identities
                or item['disposition'] not in ('false_positive','reviewed_trust_boundary')
                or any(not isinstance(item[k],str) or len(item[k].strip())<20 for k in ('rationale','boundary','verification'))):
            raise ReviewInvalid('Invalid, duplicate or unreviewed finding disposition')
        approved[item['id']]=item
    if set(identities)!=set(approved):raise ReviewInvalid('New or missing finding requires review')
    return {'reviewed_findings':len(approved),'source_files':len(hashes),'raw_severity':counts,
            'scan_review_passed':True,'release_candidate':False,'transition_enabled':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args(argv);root=args.root.resolve()
    try:
        review=json.loads((root/'docs/security/APP_SECURITY_REVIEW_R210.json').read_text())
        if review.get('bandit_version')!=version('bandit'):raise ReviewInvalid('Bandit version changed; review must be refreshed')
        with tempfile.TemporaryDirectory(prefix='mta-bandit-review-') as tmp:
            output=Path(tmp)/'scan.json'
            result=subprocess.run([sys.executable,'-m','bandit','-r','app','-f','json','-o',str(output)],cwd=root,
                                  stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=False)
            if result.returncode not in (0,1) or not output.is_file():raise ReviewInvalid('Bandit did not complete successfully')
            scan=json.loads(output.read_text())
        print(json.dumps(validate(root,scan,review),sort_keys=True))
        return 0
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError) as exc:
        print('Security review blocked: '+str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
