#!/usr/bin/env python3
"""Install selected reviewed source and tensors into an operator-created venv.

No dependency installation, automatic policy activation or model pickle classes.
Use `python -m venv --copies` plus requirements-studio-mrmt3.txt first.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from app.mrmt3_adapter import MODEL,SOURCE_COMMIT
from app.mrmt3_checkpoint import RAW_SHA,RAW_SIZE
from app.secure_https import https_urlopen
SOURCE_SHA='cfd8ae28ef0affcb6f52c9eaa91503031720e63b6ff51dd3fd4622fe7a8180f6'
PREFIX='mt3-infer-'+SOURCE_COMMIT+'/'
SELECTED=['base.py','exceptions.py','adapters/mr_mt3.py','adapters/vocab_utils.py','models/mr_mt3/t5.py']


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def fetch(url,path,limit,expected):
    with https_urlopen(url,timeout=60) as response,Path(path).open('wb') as output:
        total=0
        while block:=response.read(1024*1024):
            total+=len(block)
            if total>limit:raise ValueError('Official MR-MT3 artifact exceeds size budget')
            output.write(block)
    if sha(path)!=expected:raise ValueError('Official MR-MT3 artifact hash mismatch')


def install(runtime,archive,checkpoint,test_audio,accepted=False):
    if not accepted:raise ValueError('Explicit individual model/source license acknowledgement required')
    runtime=Path(runtime)
    if not runtime.is_absolute() or runtime.is_symlink() or not runtime.is_dir():raise ValueError('Choose an existing absolute venv directory')
    python=runtime/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if python.is_symlink() or not python.is_file():raise ValueError('Create the runtime venv with --copies')
    if any((runtime/name).exists() for name in ('source','weights','mta-runtime.json')):
        raise ValueError('Runtime already contains a model; choose a separate venv')
    with tempfile.TemporaryDirectory(prefix='.mrmt3-install-',dir=runtime) as temporary:
        for supplied in (archive,checkpoint):
            if supplied and (Path(supplied).is_symlink() or not Path(supplied).is_file()):
                raise ValueError('Supplied original artifact must be an existing regular file')
        stage=Path(temporary);archive=Path(archive) if archive else stage/'source.zip';checkpoint=Path(checkpoint) if checkpoint else stage/'mt3.pth'
        if not archive.exists():fetch('https://codeload.github.com/openmirlab/mt3-infer/zip/'+SOURCE_COMMIT,archive,16*1024**2,SOURCE_SHA)
        if not checkpoint.exists():fetch('https://huggingface.co/gudgud1014/MR-MT3/resolve/7bd24c3e1dc26468a6a9354c0a4f174405c9bad8/mt3.pth',checkpoint,RAW_SIZE,RAW_SHA)
        if archive.is_symlink() or sha(archive)!=SOURCE_SHA:raise ValueError('Reviewed source archive SHA mismatch')
        source=stage/'source';package=source/'mt3_infer';weights=stage/'weights';weights.mkdir()
        with zipfile.ZipFile(archive) as z:
            for name in SELECTED:
                data=z.read(PREFIX+'mt3_infer/'+name)
                if len(data)>1024**2:raise ValueError('Oversized reviewed source member')
                target=package/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            for folder in ('','adapters','models','models/mr_mt3'):
                path=package/folder;path.mkdir(parents=True,exist_ok=True)
                (path/'__init__.py').write_text('# MTA isolated MR-MT3 selection; other backends are excluded.\n')
            (source/'LICENSE-MT3-INFER').write_bytes(z.read(PREFIX+'LICENSE'))
            (source/'LICENSE-APACHE-2.0').write_bytes(z.read(PREFIX+'mt3_infer/models/yourmt3/LICENSE'))
        result=subprocess.run([str(python),str(PROJECT/'app/mrmt3_checkpoint.py'),str(checkpoint),str(weights/'model.safetensors')],
            check=True,capture_output=True,text=True,timeout=180)
        conversion=json.loads(result.stdout)
        # Publish only new model directories; never replace an existing engine.
        os.rename(source,runtime/'source');os.rename(weights,runtime/'weights')
        files={p.relative_to(runtime).as_posix():sha(p) for folder in ('source','weights') for p in (runtime/folder).rglob('*') if p.is_file()}
        receipt={'schema':'mta-mrmt3-runtime-1','model':MODEL,'source_commit':SOURCE_COMMIT,'files':files,
                 'python_sha256':sha(python),'tested':False,'conversion':conversion,
                 'licenses':['MIT (MR-MT3 and selected wrapper)','Apache-2.0 (T5 architecture and codec)'],
                 'source_archive_sha256':SOURCE_SHA,'model_license_url':'https://huggingface.co/gudgud1014/MR-MT3',
                 'excluded':'Other mt3-infer backends are not installed or imported.'}
        target=runtime/'mta-runtime.json'
        fd,tmp=tempfile.mkstemp(prefix='.receipt-',dir=runtime)
        try:
            with os.fdopen(fd,'w') as f:json.dump(receipt,f,indent=2)
            os.link(tmp,target)
        finally:Path(tmp).unlink(missing_ok=True)
        # Actual nonempty inference is required before the catalog can admit it.
        environment={**os.environ,'MTA_STUDIO_MRMT3_RUNTIME':str(runtime),'PYTHONPATH':str(PROJECT),
                     'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'}
        probe=stage/'probe.json'
        code="import json,sys;sys.path.insert(0,sys.argv[1]);from app.mrmt3_adapter import _transcribe;from pathlib import Path;r=_transcribe(Path(sys.argv[2]),{},_require_tested=False);assert r.parts,'No notes in installer test';Path(sys.argv[3]).write_text(r.model_dump_json(indent=2))"
        subprocess.run([str(python),'-I','-c',code,str(PROJECT),str(Path(test_audio).resolve()),str(probe)],
            env=environment,check=True,timeout=600)
        receipt.update(tested=True,selftest_result_sha256=sha(probe))
        fd,tmp=tempfile.mkstemp(prefix='.receipt-',dir=runtime)
        try:
            with os.fdopen(fd,'w') as f:json.dump(receipt,f,indent=2)
            os.replace(tmp,target)
        finally:Path(tmp).unlink(missing_ok=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--source-archive',type=Path);p.add_argument('--checkpoint-local',type=Path)
    p.add_argument('--test-audio',type=Path,required=True);p.add_argument('--accept-model-licenses',action='store_true')
    a=p.parse_args();print(json.dumps(install(a.runtime,a.source_archive,a.checkpoint_local,a.test_audio,a.accept_model_licenses),indent=2))
