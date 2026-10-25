#!/usr/bin/env python3
"""Build a deterministic r210 cumulative ZIP and verify it against its baseline.

Does not commit/publish. Existing output is refused. The checksum is written
alongside the archive; generated caches and Git internals are excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--baseline-archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve();output=args.output.resolve()
    if (root/'RELEASE').read_text().strip()!='0.3.0-r210':raise ValueError('Unexpected release')
    if output.exists() or output.with_suffix(output.suffix+'.sha256').exists():raise FileExistsError('Delivery already exists')
    with zipfile.ZipFile(args.baseline_archive) as baseline:
        if baseline.testzip() is not None:raise ValueError('Baseline CRC failed')
        required={item.filename for item in baseline.infolist() if not item.is_dir()}
    excluded={'.git','__pycache__','.pytest_cache','.ruff_cache','htmlcov'}
    files=[]
    for path in sorted(root.rglob('*')):
        if any(part in excluded for part in path.relative_to(root).parts):continue
        if path.is_symlink():raise ValueError('Symlinks require explicit archive review')
        if not path.is_file() or path.resolve()==output:continue
        if path.name.startswith('.coverage'):continue
        files.append(path)
    names={path.relative_to(root).as_posix() for path in files}
    missing=sorted(required-names)
    if missing:raise ValueError('Baseline files missing: '+', '.join(missing))
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in files:
            name=path.relative_to(root).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2026,10,23,0,0,0))
            info.create_system=3
            info.external_attr=(stat.S_IFREG|stat.S_IMODE(path.stat().st_mode))<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:raise ValueError('Final CRC failed')
        if set(archive.namelist())!=names:raise ValueError('Final inventory mismatch')
    digest=hashlib.file_digest(output.open('rb'),'sha256').hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n')
    print(json.dumps({'archive':str(output),'bytes':output.stat().st_size,'sha256':digest,
                      'files':len(files),'baseline_files':len(required),'missing_baseline_files':missing,'full_crc':'passed'},indent=2))


if __name__=='__main__':main()
