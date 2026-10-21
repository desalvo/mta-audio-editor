"""Operator-installed, hash-pinned extra GM banks. No URL download or API paths."""
import hashlib
import json
import re
import os
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlsplit

ID = re.compile(r'sf2-[a-z0-9][a-z0-9-]{0,47}')
# Only clearly permissive declarations accepted by this bounded installer.
LICENSES = {'MIT', 'CC0-1.0', 'BSD-2-Clause', 'BSD-3-Clause', 'CC-BY-4.0'}


def root():
    from .gm_installer import root as soundfont_root
    folder=soundfont_root()/'reviewed'
    if folder.is_symlink():raise ValueError('Unsafe extra SoundFont directory')
    folder.mkdir(exist_ok=True,mode=0o700)
    return folder


def descriptor(bank_id):
    if not isinstance(bank_id,str) or not ID.fullmatch(bank_id):raise ValueError('Invalid reviewed SoundFont identifier')
    folder=root()/bank_id
    receipt=folder/'receipt.json'
    if folder.is_symlink() or receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size>16384:
        raise ValueError('Reviewed SoundFont receipt missing or unsafe')
    value=json.loads(receipt.read_text())
    if (not isinstance(value,dict) or value.get('id')!=bank_id or value.get('license') not in LICENSES
            or value.get('rights_reviewed') is not True or not isinstance(value.get('sha256'),str)
            or not re.fullmatch('[a-f0-9]{64}',value['sha256'])):
        raise ValueError('Invalid reviewed SoundFont receipt')
    return value


def bank_path(bank_id):
    value=descriptor(bank_id)
    path=root()/bank_id/'bank.sf2'
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1 or not 12<path.stat().st_size<=1024**3:
        raise ValueError('Reviewed SoundFont file missing or unsafe')
    with path.open('rb') as stream:
        header=stream.read(12)
        if header[:4]!=b'RIFF' or header[8:]!=b'sfbk':raise ValueError('Not an SF2 SoundFont')
        stream.seek(0)
        if hashlib.file_digest(stream,'sha256').hexdigest()!=value['sha256']:
            raise ValueError('Reviewed SoundFont checksum mismatch')
    license_path=path.with_name('LICENSE.txt')
    if license_path.is_symlink() or not license_path.is_file() or license_path.stat().st_size>1024**2:
        raise ValueError('SoundFont license notice missing')
    with license_path.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=value.get('license_sha256'):
            raise ValueError('SoundFont license notice checksum mismatch')
    return path


def install(source,bank_id,*,name,sha256,license_id,license_file,evidence_url,rights_reviewed=False):
    """Explicit administrator CLI operation, refusing overwrite of any bank."""
    if not ID.fullmatch(bank_id) or license_id not in LICENSES or rights_reviewed is not True:
        raise ValueError('Review bank rights and choose a supported permissive license')
    if not isinstance(name,str) or not 1<=len(name)<=160 or not re.fullmatch('[a-f0-9]{64}',sha256):
        raise ValueError('Invalid SoundFont name or digest')
    url=urlsplit(evidence_url)
    if url.scheme!='https' or not url.hostname or url.username or url.password or len(evidence_url)>2000:
        raise ValueError('Provide a public HTTPS license reference without credentials')
    source,notice=Path(source),Path(license_file)
    for path,limit in ((source,1024**3),(notice,1024**2)):
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=limit:
            raise ValueError('Missing or unsafe SoundFont/license source')
    from .ai_project_lock import project_publication_lock
    from .storage import _atomic_json_write
    from .fs_durability import sync_directory
    with project_publication_lock('studio-model:gm'):
        folder=root();destination=folder/bank_id
        if destination.exists() or destination.is_symlink():raise ValueError('SoundFont already installed; choose another identifier')
        with tempfile.TemporaryDirectory(prefix='.bank-',dir=folder) as temporary:
            stage=Path(temporary)/'bank';stage.mkdir()
            shutil.copyfile(source,stage/'bank.sf2');shutil.copyfile(notice,stage/'LICENSE.txt')
            with (stage/'bank.sf2').open('rb') as stream:
                if hashlib.file_digest(stream,'sha256').hexdigest()!=sha256:raise ValueError('SoundFont SHA-256 mismatch')
            with (stage/'bank.sf2').open('rb') as stream:
                header=stream.read(12)
                if header[:4]!=b'RIFF' or header[8:]!=b'sfbk':raise ValueError('Not an SF2 SoundFont')
            with (stage/'LICENSE.txt').open('rb') as stream:license_sha=hashlib.file_digest(stream,'sha256').hexdigest()
            record={'id':bank_id,'name':name,'sha256':sha256,'license':license_id,'license_sha256':license_sha,
                    'evidence_url':evidence_url,'rights_reviewed':True,'musical_coverage_verified':False}
            _atomic_json_write(stage/'receipt.json',record)
            for item in stage.iterdir():
                with item.open('rb') as stream:os.fsync(stream.fileno())
            sync_directory(stage);os.rename(stage,destination);sync_directory(folder)
    return record


def catalog():
    result=[]
    for folder in sorted(root().iterdir()):
        if not ID.fullmatch(folder.name):continue
        try:
            value=descriptor(folder.name);bank_path(folder.name)
            result.append({**value,'available':True})
        except (ValueError,OSError,json.JSONDecodeError):
            result.append({'id':folder.name,'name':folder.name,'available':False})
    return result
