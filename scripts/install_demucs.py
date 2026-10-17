#!/usr/bin/env python3
"""Install server Demucs into an existing torch runtime without replacing torch.

Run as administrator while AI jobs are idle. No service is restarted here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def install(python,env_file,device='auto'):
    python=Path(python)
    if not python.is_absolute() or not python.is_file() or not os.access(python,os.X_OK):
        raise ValueError('Choose an existing absolute Python executable with torch and torchaudio installed')
    if device not in ('auto','cpu','cuda'):raise ValueError('Invalid device')
    env_file=Path(env_file)
    if env_file.is_symlink() or (env_file.exists() and not env_file.is_file()):raise ValueError('Unsafe environment file')
    original=env_file.read_text() if env_file.exists() else ''
    adapter=Path(__file__).resolve().parents[1]/'app'/'ai_unified_adapter.py'
    if adapter.is_symlink() or not adapter.is_file() or not os.access(adapter,os.X_OK):
        raise ValueError('Trusted Demucs adapter missing; use the helper bundled with the signed MTA server package')
    # Reuse the existing accelerator wheels. Let pip fail rather than downgrade
    # or silently exchange ROCm for CPU/CUDA wheels in an ACE environment.
    # Pin all other installed dependencies too: this optional component must
    # not upgrade an existing ACE dependency to satisfy its own requirements.
    result=subprocess.run([str(python),'-c',
        'import torch,torchaudio;print("torch=="+torch.__version__);print("torchaudio=="+torchaudio.__version__)'],
        capture_output=True,text=True,check=True)
    versions=result.stdout.strip().splitlines()
    if len(versions)!=2 or any(not re.fullmatch(r'(torch|torchaudio)==[A-Za-z0-9.+_-]+',v) for v in versions):
        raise ValueError('Cannot determine installed accelerator package versions')
    installed=subprocess.run([str(python),'-m','pip','list','--format=json'],capture_output=True,text=True,check=True)
    frozen=[]
    for package in json.loads(installed.stdout):
        name,version=package.get('name'),package.get('version')
        if (not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',name)
                or not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9.+_!-]+',version)):
            raise ValueError('Invalid installed package metadata')
        if name.lower().replace('_','-') not in {'torch','torchaudio','demucs'}:
            frozen.append(name+'=='+version)
    versions+=sorted(frozen)
    with tempfile.TemporaryDirectory(prefix='mta-demucs-install-') as tmp:
        constraints=Path(tmp)/'constraints.txt';constraints.write_text('\n'.join(versions)+'\n')
        subprocess.run([str(python),'-m','pip','install','--constraint',str(constraints),'demucs==4.1.0'],check=True)
    subprocess.run([str(python),'-c','import demucs.separate,torch,torchaudio;print("Demucs runtime ready; accelerator available:",torch.cuda.is_available(),"HIP:",torch.version.hip)'],check=True)
    if env_file.is_symlink() or (env_file.read_text() if env_file.exists() else '')!=original:
        raise ValueError('Server configuration changed during installation; rerun to preserve the new settings')
    values={'MTA_DEMUCS_PYTHON':str(python),'MTA_DEMUCS_DEVICE':device,
      'MTA_AI_WORKER_DEMUCS_EXECUTABLE':str(adapter),'MTA_AI_WORKER_ENABLED':'true'}
    lines=[line for line in original.splitlines() if line.split('=',1)[0] not in values]
    # systemd EnvironmentFile quoted values, no interpolation or shell evaluation.
    for key,value in values.items():
        if any(c in value for c in '\r\n\x00'):raise ValueError('Invalid configuration value')
        lines.append(key+'="'+value.replace('\\','\\\\').replace('"','\\"')+'"')
    env_file.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=env_file.parent,prefix='.demucs-env-')
    try:
        os.fchmod(fd,0o600)
        if env_file.exists():
            st=env_file.stat();os.fchown(fd,st.st_uid,st.st_gid)
        with os.fdopen(fd,'w') as stream:
            stream.write('\n'.join(lines)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,env_file)
    finally:
        if os.path.exists(name):os.unlink(name)
    print('Demucs configured. Restart mta-server when the AI queue is idle; test as the service user.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',required=True)
    parser.add_argument('--env-file',default='/etc/mta/mta.env')
    parser.add_argument('--device',choices=('auto','cpu','cuda'),default='auto')
    args=parser.parse_args()
    install(args.python,args.env_file,args.device)


if __name__=='__main__':main()
