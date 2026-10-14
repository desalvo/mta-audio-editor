#!/usr/bin/env python3
"""Offline destructive-process crash injection in a *temporary sandbox only*.

Never writes the production MTA queue or audio store.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run():
    with tempfile.TemporaryDirectory(prefix='mta-outbox-injection-') as root:
        env = dict(os.environ, MTA_AI_JOB_STATE_DIR=root, PYTHONPATH=str(ROOT))
        child = '''import os
from app import ai_publish_outbox as o
o.stage('crash01','sandbox-project',b'RIFFtest',{'mode':'arranger'})
def simulate_commit(jid,*_):
    open(os.path.join(os.environ['MTA_AI_JOB_STATE_DIR'],'published.marker'),'w').write(jid)
    os._exit(77)
o.recover(simulate_commit)
'''
        proc = subprocess.run([sys.executable, '-c', child], env=env, check=False, timeout=15)
        if proc.returncode != 77:
            raise RuntimeError(f'Expected injected crash exit 77, got {proc.returncode}')
        followup = '''import os
from app import ai_publish_outbox as o
path=os.path.join(os.environ['MTA_AI_JOB_STATE_DIR'],'published.marker')
def publish(jid,*_):
    if os.path.exists(path):
        assert open(path).read()==jid
    else:
        open(path,'w').write(jid)
assert o.recover(publish)==1
assert o.recover(publish)==0
assert o.status('crash01')['state']=='published'
'''
        subprocess.run([sys.executable, '-c', followup], env=env, check=True, timeout=15)
        print('PASS: process killed between publication and receipt; recovery without duplicate visible artifact')


if __name__ == '__main__':
    run()
