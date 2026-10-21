#!/usr/bin/env python3
"""Authenticated concurrent AI jobs and per-user storage smoke test.

Operates against an installed MTA server. Requires a PRIVATE JSON file:
{"users": [{"label":"test-a", "token":"..."}, {"label":"test-b", "token":"..."}]}
Only send tokens from temporary testing accounts. No credentials are written to output.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import wave
import io
import sqlite3


def sample_wav():
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
        out.writeframes(b'\0\0'*16000)
    return buffer.getvalue()


def task(base, kind, label, token, audio, timeout):
    parsed = urlsplit(base)
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'):
        raise ValueError('HTTPS required (loopback exception for testing only)')
    req=urllib.request.Request(base.rstrip('/')+'/api/ai-jobs/execute-audio/'+kind,  # noqa: S310 - validated scheme
        data=audio, headers={'Authorization': 'Bearer '+token, 'Content-Type': 'audio/wav'}, method='POST')  # noqa: S310 - HTTPS/loopback  # noqa: S310 - HTTPS or explicit local test loopback
    started=time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - validated HTTPS/loopback
            payload=response.read(65*1024*1024)
            return {'user':label,'status':response.status,'job_id':response.headers.get('X-MTA-AI-Job-ID'),
                    'result_bytes':len(payload),'result_type':response.headers.get('Content-Type'),
                    'wall_seconds':round(time.monotonic()-started,3)}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        return {'user':label,'error':str(exc)[:180], 'wall_seconds':round(time.monotonic()-started,3)}



def verify_server_ledger(report, db_path):
    """Run on the MTA server against its actual auth.sqlite3 (read-only)."""
    jobs = report.get('jobs', [])
    if not isinstance(jobs, list) or not jobs:
        raise ValueError('Benchmark has no jobs')
    uri = 'file:' + str(Path(db_path).resolve()) + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = []
        for result in jobs:
            jid = result.get('job_id')
            if not jid:
                rows.append({'label': result.get('user'), 'ok': False, 'issue': 'missing_job_id'})
                continue
            found = conn.execute('SELECT id,user_id,status,resource_source,usage_json FROM ai_compute_jobs WHERE id=?', (jid,)).fetchone()
            if found is None:
                rows.append({'label': result.get('user'), 'job_id': jid, 'ok': False, 'issue': 'job_not_in_ledger'})
                continue
            try:
                usage = json.loads(found['usage_json'])
                ok_usage = isinstance(usage, dict) and 'cpu_seconds' in usage and found['resource_source'] != 'unmetered'
            except (TypeError, ValueError):
                usage, ok_usage = {}, False
            rows.append({'label': result.get('user'), 'job_id': jid,
                         'user_id': found['user_id'], 'status': found['status'],
                         'source': found['resource_source'],
                         'cpu_seconds': usage.get('cpu_seconds'),
                         'gpu_seconds': usage.get('gpu_seconds'),
                         'ok': found['status'] == 'done' and ok_usage,
                         'issue': None if found['status'] == 'done' and ok_usage else 'unmetered_or_incomplete'})
        labels = {}
        for entry in rows:
            if entry.get('user_id') is not None:
                labels.setdefault(entry['label'], set()).add(entry['user_id'])
        user_ids = [next(iter(v)) for v in labels.values() if len(v)==1]
        separation = all(len(v)==1 for v in labels.values()) and len(user_ids)==len(set(user_ids)) and len(labels)>=2
        return {'ready': bool(rows) and all(r['ok'] for r in rows) and separation,
                'user_isolation_valid': separation, 'jobs': rows,
                'note': 'GPU billing still requires independently verified per-job GPU telemetry; no GPU time is inferred.'}
    finally:
        conn.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',required=True,help='MTA HTTPS base address')
    p.add_argument('--tokens-file',type=Path,required=True)
    p.add_argument('--kind',default='whisper')
    p.add_argument('--jobs-per-user',type=int,default=2)
    p.add_argument('--output',type=Path,default=Path('ai-concurrency-report.json'))
    p.add_argument('--timeout',type=int,default=1200)
    p.add_argument('--verify-ledger',type=Path,help='Read-only path to server auth.sqlite3; checks actual job ownership and usage')
    args=p.parse_args()
    if not args.url.startswith('https://') and not args.url.startswith('http://127.0.0.1:'):
        p.error('Require HTTPS (or local loopback for testing); TLS verification is always enabled')
    if not 1 <= args.jobs_per_user <= 8: p.error('jobs-per-user must be 1..8')
    if args.tokens_file.stat().st_mode & 0o077: p.error('tokens file must have mode 0600')
    users=json.loads(args.tokens_file.read_text()).get('users',[])
    if len(users)<2 or len(users)>8 or any(not u.get('token') or not u.get('label') for u in users):
        p.error('Provide 2..8 labelled test users with tokens')
    audio=sample_wav(); output=[]
    with ThreadPoolExecutor(max_workers=len(users)*args.jobs_per_user) as pool:
        futures=[pool.submit(task,args.url,args.kind,u['label'],u['token'],audio,args.timeout)
                 for u in users for _ in range(args.jobs_per_user)]
        for future in as_completed(futures): output.append(future.result())
    ids=[v['job_id'] for v in output if v.get('job_id')]
    report={'schema':1,'kind':args.kind,'jobs':output,
            'unique_job_ids':len(ids)==len(set(ids)) and len(ids)==len(output),
            'complete':len(ids)==len(output),
            'verification_required':'Compare per-user ledger, cgroup CPU/GPU, and persistent storage samples in MTA admin reporting; a client cannot attest server-side counters.'}
    if args.verify_ledger:
        report['server_verification'] = verify_server_ledger(report, args.verify_ledger)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(output)} jobs; {len(ids)} successful, IDs unique={report["unique_job_ids"]}; report={args.output}')
    return 0 if (report['complete'] and report['unique_job_ids'] and (not args.verify_ledger or report['server_verification']['ready'])) else 1


if __name__=='__main__':
    raise SystemExit(main())
