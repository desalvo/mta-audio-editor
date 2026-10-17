#!/usr/bin/env python3
"""Bind installed AI runtimes to the global server queue; never install model weights."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

IMPORTS={'whisper':['whisper'],'chords-ml':['madmom_infer','librosa'],
 'markers':['numpy','scipy','librosa'],'demucs':['demucs.separate'],
 'sam-audio':['sam_audio'],'singer-separation':['sam_audio'],
 'backing-vocals':['audio_separator.separator'],'drumsep':['onnxruntime']}


def configure(python,env_file,kinds):
    python=Path(python);env_file=Path(env_file)
    if not python.is_absolute() or not python.is_file() or not os.access(python,os.X_OK):raise ValueError('Invalid AI Python')
    if not kinds or set(kinds)-IMPORTS.keys():raise ValueError('Unsupported engine selection')
    if env_file.is_symlink() or (env_file.exists() and not env_file.is_file()):raise ValueError('Unsafe environment file')
    original=env_file.read_text() if env_file.exists() else ''
    modules=sorted({name for kind in kinds for name in IMPORTS[kind]})
    # Fixed import statements, no shell or caller-supplied code/module paths.
    subprocess.run([str(python),'-c','import importlib,json;[importlib.import_module(n) for n in json.loads(__import__("sys").argv[1])]',json.dumps(modules)],check=True)
    values={'MTA_AI_WORKER_ENABLED':'true','MTA_AI_UNIFIED_WORKERS_ENABLED':'true'}
    values.update({'MTA_AI_WORKER_'+kind.upper().replace('-','_')+'_PYTHON':str(python) for kind in kinds})
    if 'demucs' in kinds:values['MTA_DEMUCS_PYTHON']=str(python)
    if env_file.is_symlink() or (env_file.read_text() if env_file.exists() else '')!=original:raise ValueError('Configuration changed during preflight')
    lines=[line for line in original.splitlines() if line.split('=',1)[0] not in values]
    for key,value in values.items():
        if any(c in value for c in '\r\n\x00'):raise ValueError('Unsafe configuration value')
        lines.append(key+'="'+value.replace('\\','\\\\').replace('"','\\"')+'"')
    env_file.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=env_file.parent,prefix='.ai-workers-')
    try:
        os.fchmod(fd,0o600)
        if env_file.exists():
            info=env_file.stat();os.fchown(fd,info.st_uid,info.st_gid)
        with os.fdopen(fd,'w') as stream:
            stream.write('\n'.join(lines)+'\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,env_file)
    finally:
        if os.path.exists(name):os.unlink(name)
    return {'configured':kinds,'restart_required':True,'model_weights_verified':False,'gpu_billing_activated':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',required=True)
    parser.add_argument('--env-file',default='/etc/mta/mta.env')
    parser.add_argument('--kinds',required=True,help=','.join(IMPORTS))
    args=parser.parse_args()
    try:print(json.dumps(configure(args.python,args.env_file,args.kinds.split(','))))
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        print(type(exc).__name__+': '+str(exc));return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
