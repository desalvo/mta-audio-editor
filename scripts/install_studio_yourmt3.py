#!/usr/bin/env python3
"""Explicit operator installation of one pinned CPU transcription runtime.

No activation before a real inference test. Run with Python 3.11/3.12. This
recipe does not modify the server/ACE/ROCm environment or download other models.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from app.yourmt3_adapter import MODEL,EXPERIMENT
from app.studio_checkpoint import SHA256,SIZE
COMMIT='5e66c1ea173a8186e0d20432b841d3180cc015b5'
BASE='https://huggingface.co/spaces/mimbres/YourMT3/resolve/'+COMMIT+'/'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def download(relative,target,size,sha,cache=None):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.stat().st_size==size and digest(target)==sha:return
    part=target.with_name(target.name+'.partial')
    try:
        if cache is not None:
            cached=cache/relative
            if cached.is_symlink() or not cached.resolve().is_relative_to(cache.resolve()) or cached.stat().st_size!=size:raise ValueError('Missing/unsafe pinned source cache: '+relative)
            source=cached.open('rb')
        else:
            source=urllib.request.urlopen(BASE+relative,timeout=90)  # noqa: S310 -- fixed official HTTPS origin, pinned commit and digest
        with source as response,part.open('wb') as stream:
            count=0
            while block:=response.read(1024*1024):
                count+=len(block)
                if count>size:raise ValueError('Download exceeds pinned size')
                stream.write(block)
        if count!=size or digest(part)!=sha:raise ValueError('Pinned source/model digest mismatch: '+relative)
        part.replace(target)
    finally:part.unlink(missing_ok=True)


def install(root,test_audio,cache=None):
    if sys.platform!='linux':raise ValueError('This pinned CPU installation recipe currently supports Linux only')
    if sys.version_info[:2] not in ((3,11),(3,12)):raise ValueError('Use Python 3.11 or 3.12 for this isolated runtime')
    root=root.absolute()
    if root.exists():raise ValueError('Choose a new runtime directory; an existing runtime is never overwritten')
    if not test_audio.is_file():raise ValueError('Supply a short authorized musical WAV fixture, not silence')
    root.mkdir(parents=True,mode=0o700)
    identity=root.stat().st_ino
    try:return install_created(root,test_audio,cache)
    except BaseException:
        # This invocation owns this new directory; never remove a replacement
        # directory, an existing runtime or a symlink supplied by another actor.
        if root.is_dir() and not root.is_symlink() and root.stat().st_ino==identity:shutil.rmtree(root)
        raise


def install_created(root,test_audio,cache):
    python=root/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    def run(args,**kw):subprocess.run(list(map(str,args)),check=True,**kw)
    run([sys.executable,'-m','venv',root])
    run([python,'-m','pip','install','--disable-pip-version-check','torch==2.11.0+cpu','torchaudio==2.11.0+cpu',
         '--index-url','https://download.pytorch.org/whl/cpu'])
    run([python,'-m','pip','install','--disable-pip-version-check','-r',PROJECT/'requirements-studio-yourmt3.txt'])
    manifest=json.loads((PROJECT/'app/studio_assets/yourmt3_sources.json').read_text())
    for i,item in enumerate(manifest['files']):
        print(f"Source {i+1}/{len(manifest['files'])}: {item['path']}",flush=True)
        download(item['path'],root/item['path'],item['size'],item['sha256'],cache)
    # Preserve mathematical T5 layer semantics without installing old model
    # deserialization/network code from Transformers 4.45.1.
    shutil.copyfile(PROJECT/'app/studio_assets/yourmt3_t5_compat.py',root/'amt/src/model/mta_t5_compat.py')
    t5=root/'amt/src/model/t5mod.py';text=t5.read_text()
    old='from transformers.models.t5.modeling_t5 import'
    if text.count(old)!=1:raise ValueError('Unexpected pinned T5 import')
    t5.write_text(text.replace(old,'from model.mta_t5_compat import'))
    helper=root/'model_helper.py';text=helper.read_text();lines=text.splitlines()
    positions=[i for i,line in enumerate(lines) if 'checkpoint = torch.load(' in line]
    if len(positions)!=1:raise ValueError('Unexpected pinned checkpoint loader')
    lines[positions[0]]='    checkpoint = {"state_dict": __import__("safetensors.torch",fromlist=["load_file"]).load_file(dir_info["last_ckpt_path"],device=device)}'
    helper.write_text('\n'.join(lines)+'\n')
    modeldir=root/'amt/logs/2024'/EXPERIMENT/'checkpoints';checkpoint=modeldir/'last.ckpt'
    download('amt/logs/2024/'+EXPERIMENT+'/checkpoints/last.ckpt',checkpoint,SIZE,SHA256,cache)
    run([python,'-c','from app.studio_checkpoint import convert;import sys;convert(sys.argv[1],sys.argv[2])',checkpoint,modeldir/'model.safetensors'],cwd=PROJECT)
    checkpoint.unlink()
    shutil.copyfile(PROJECT/'app/studio_assets/Apache-2.0.txt',root/'MTA-THIRD-PARTY-LICENSE.txt')
    (root/'MTA-NOTICE.txt').write_text('YourMT3 original-author pinned Space: Apache-2.0. T5 mathematical layers: Copyright 2018 Mesh TensorFlow authors, T5 Authors and HuggingFace Inc., Apache-2.0. MTA changes: tensor-only checkpoint loader and mathematical-layer compatibility imports. See project docs/YOURMT3_RUNTIME_R210.md.\n')
    files=[root/item['path'] for item in manifest['files']]+[root/'amt/src/model/mta_t5_compat.py',modeldir/'model.safetensors',root/'MTA-THIRD-PARTY-LICENSE.txt',root/'MTA-NOTICE.txt']
    receipt={'model':MODEL,'commit':COMMIT,'license':'Apache-2.0','tested':False,
             'files':{str(path.relative_to(root)):digest(path) for path in files}}
    (root/'mta-runtime.json').write_text(json.dumps(receipt,indent=2)+'\n')
    env={**os.environ,'MTA_STUDIO_YOURMT3_RUNTIME':str(root),'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'}
    run([python,'-c','from app.yourmt3_adapter import transcribe;import sys;print(transcribe(sys.argv[1],{}).model_dump_json())',test_audio.resolve()],cwd=PROJECT,env=env)
    receipt['tested']=True;(root/'mta-runtime.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Inference passed. Operator configuration (restart the application after applying):')
    print('MTA_STUDIO_TRANSCRIBER=yourmt3')
    print('MTA_STUDIO_YOURMT3_RUNTIME='+str(root))
    print('MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON='+str(python))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--test-audio',type=Path,required=True)
    parser.add_argument('--source-cache',type=Path,help='Offline source/model cache; every pinned file must be present and verified, no source download fallback')
    parser.add_argument('--accept-apache-2-license',action='store_true',help='Confirm review of the original-author Space/model and dependency licenses')
    args=parser.parse_args()
    if not args.accept_apache_2_license:parser.error('Review docs/YOURMT3_RUNTIME_R210.md and explicitly accept the linked licenses')
    install(args.runtime,args.test_audio,args.source_cache)
