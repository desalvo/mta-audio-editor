#!/usr/bin/env python3
"""Add the original author's pinned PS checkpoint to a verified noPS runtime.

Keeps the existing noPS receipt, source, interpreter and weights unchanged.
Publishes PS as tested only after actual inference on authorized musical audio.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from app.studio_checkpoint import PS_SHA256,PS_SIZE
from scripts.install_studio_yourmt3 import digest

REVISION='e45ebd70398682d54b7bb1901a5216e18f3b1824'
EXPERIMENT='mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b80_ps2'
URL='https://huggingface.co/mimbres/YourMT3/resolve/'+REVISION+'/logs/2024/'+EXPERIMENT+'/checkpoints/model.ckpt'


def publish(path,value,exclusive=False):
    fd,temp=tempfile.mkstemp(prefix='.ps-receipt-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out:json.dump(value,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())
        if exclusive:os.link(temp,path)
        else:os.replace(temp,path)
    finally:Path(temp).unlink(missing_ok=True)


def install(root,audio,local_checkpoint=None):
    root=Path(root);audio=Path(audio).resolve(strict=True)
    if not root.is_absolute() or root.is_symlink():raise ValueError('Use an installed absolute runtime directory')
    python=root/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    env={**os.environ,'MTA_STUDIO_YOURMT3_RUNTIME':str(root),'MTA_STUDIO_YOURMT3_VARIANT':'nops',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'4','OPENBLAS_NUM_THREADS':'4'}
    subprocess.run([python,'-c','from app.yourmt3_adapter import verified_runtime;verified_runtime()'],cwd=PROJECT,env=env,check=True)
    baseline=root/'mta-runtime.json';original=baseline.read_bytes();base=json.loads(original)
    receipt_path=root/'mta-runtime-ps.json'
    if receipt_path.exists() or receipt_path.is_symlink():raise ValueError('PS runtime receipt already exists')
    parent=root/'amt/logs/2024'
    if any(p.is_symlink() for p in [root/'amt',root/'amt/logs',parent]):raise ValueError('Unsafe runtime model directory')
    experiment=parent/EXPERIMENT;experiment.mkdir()
    identity=experiment.stat().st_ino;receipt_identity=None
    try:
        folder=experiment/'checkpoints';folder.mkdir()
        source=Path(local_checkpoint) if local_checkpoint is not None else folder/'original.ckpt'
        if local_checkpoint is None:
            count=0
            with urllib.request.urlopen(URL,timeout=90) as response,source.open('xb') as stream:
                while block:=response.read(1024*1024):
                    count+=len(block)
                    if count>PS_SIZE:raise ValueError('PS checkpoint exceeds pinned size')
                    stream.write(block)
        if source.is_symlink() or source.stat().st_size!=PS_SIZE or digest(source)!=PS_SHA256:
            raise ValueError('Pinned PS checkpoint size/SHA-256 mismatch')
        target=folder/'model.safetensors'
        subprocess.run([python,'-c','from app.studio_checkpoint import convert;import sys;print(convert(sys.argv[1],sys.argv[2],"ps"))',source.resolve(),target],cwd=PROJECT,env=env,check=True)
        if local_checkpoint is None:source.unlink()
        value={**base,'model':'yourmt3-ps-e45ebd70','tested':False,'checkpoint_sha256':PS_SHA256,
               'checkpoint_revision':REVISION,'files':{n:h for n,h in base['files'].items() if not n.endswith('.safetensors')}}
        value['files'][str(target.relative_to(root)).replace(os.sep,'/')]=digest(target)
        publish(receipt_path,value,exclusive=True);receipt_identity=receipt_path.stat().st_ino
        env['MTA_STUDIO_YOURMT3_VARIANT']='ps';test=experiment/'mta-inference-test.json'
        subprocess.run([python,'-c',
            'from app.yourmt3_adapter import transcribe;from pathlib import Path;import sys;r=transcribe(sys.argv[1],{});assert any(p.notes for p in r.parts),"No notes detected";Path(sys.argv[2]).write_text(r.model_dump_json(indent=2))',audio,test],cwd=PROJECT,env=env,check=True)
        if baseline.read_bytes()!=original:raise ValueError('Original noPS receipt changed during installation')
        value['tested']=True;publish(receipt_path,value);receipt_identity=receipt_path.stat().st_ino
        return {'variant':'ps','tested':True,'receipt':str(receipt_path),'checkpoint_sha256':PS_SHA256,'tensor_sha256':digest(target),'nops_receipt_unchanged':True}
    except BaseException:
        if receipt_identity is not None and receipt_path.is_file() and not receipt_path.is_symlink() and receipt_path.stat().st_ino==receipt_identity:
            receipt_path.unlink()
        if experiment.is_dir() and not experiment.is_symlink() and experiment.stat().st_ino==identity:shutil.rmtree(experiment)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--test-audio',type=Path,required=True)
    parser.add_argument('--checkpoint-local',type=Path);parser.add_argument('--accept-apache-2-license',action='store_true')
    args=parser.parse_args()
    if not args.accept_apache_2_license:parser.error('Review the original-author Apache-2.0 checkpoint and dependency licenses first')
    print(json.dumps(install(args.runtime,args.test_audio,args.checkpoint_local),indent=2))
