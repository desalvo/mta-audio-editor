#!/usr/bin/env python3
"""Build an admin-reviewed model bundle from explicit local files/directories.

Template.files is a list of relative paths to include. No download, model
training, automatic permissions or unsafe ZIP links. Cache symlinks are copied
as regular bytes only when their resolved targets remain inside the source root.
"""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.studio_asset_registry import validate_manifest,relative,MAX_BUNDLE


def build(template,source,destination):
    source=Path(source).resolve(strict=True);destination=Path(destination).resolve()
    if destination.is_relative_to(source):raise ValueError('Write the bundle outside the model source directory')
    if destination.exists():raise ValueError('Refusing to overwrite an existing bundle')
    value=json.loads(Path(template).read_text());includes=value['files']
    if not isinstance(includes,list) or not includes:raise ValueError('Template.files must list explicit model files/directories')
    files={}
    for name in includes:
        relative(name);path=source/name
        selected=sorted(path.rglob('*')) if path.is_dir() else [path]
        for item in selected:
            if item.is_dir():continue
            if not item.resolve(strict=True).is_relative_to(source):raise ValueError('Model source link escapes the reviewed directory')
            rel=item.relative_to(source).as_posix();relative(rel)
            if not item.is_file():raise ValueError('Model source must contain regular files')
            with item.open('rb') as stream:files[rel]={'bytes':item.stat().st_size,'sha256':hashlib.file_digest(stream,'sha256').hexdigest()}
    value['files']=files;validate_manifest(value)
    if sum(x['bytes'] for x in files.values())>MAX_BUNDLE:raise ValueError('Bundle exceeds expanded size limit')
    try:
        with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json',json.dumps(value,indent=2))
            for name in sorted(files):
                # Stream multi-gigabyte weights and recheck the exact packed bytes.
                expected=files[name];digest=hashlib.sha256();size=0
                item=source/name
                if not item.resolve(strict=True).is_relative_to(source):
                    raise ValueError('Model source changed outside the reviewed directory')
                entry=zipfile.ZipInfo(name);entry.compress_type=zipfile.ZIP_DEFLATED
                entry.external_attr=0o100600<<16
                with item.open('rb') as inp,archive.open(entry,'w',force_zip64=True) as out:
                    while block:=inp.read(1024*1024):
                        size+=len(block)
                        if size>expected['bytes']:raise ValueError('Model source changed while packaging')
                        digest.update(block);out.write(block)
                if size!=expected['bytes'] or digest.hexdigest()!=expected['sha256']:
                    raise ValueError('Model source changed while packaging')
    except BaseException:destination.unlink(missing_ok=True);raise
    return {'path':str(destination),'files':len(files),'licenses_granted':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('template',type=Path);parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();print(json.dumps(build(args.template,args.source,args.output),indent=2))

if __name__=='__main__':main()
