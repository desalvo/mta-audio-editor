"""Validate signed-bundle iOS model review inputs;never invent a checkpoint grant.

An empty bundled registry is valid and authorizes no local model. A release
download is selected only by a complete review matching the actual file bytes.
This build check is not independent legal review or native runtime acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import stat
import time
from urllib.parse import urlsplit

SCHEMA='mta-ios-model-rights-1'
MODEL_KEYS=frozenset({'id','stemCount','sourceFormat','sourceSHA256','licenseFile','licenseSHA256',
                     'noticeFile','noticeSHA256','authorizationBasis','reviewReference','reviewer',
                     'reviewedAt','expiresAt','localNoncommercialOnly'})


def unique_pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('Duplicate model rights field')
        result[key]=value
    return result


def digest(path):
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>2_147_483_648:
        raise ValueError('Unsafe or oversized review asset')
    checksum=hashlib.sha256();count=0
    with path.open('rb') as stream:
        while chunk:=stream.read(1_048_576):
            count+=len(chunk)
            if count>2_147_483_648:raise ValueError('Review asset grew during hashing')
            checksum.update(chunk)
    if count!=info.st_size:raise ValueError('Review asset size changed')
    return checksum.hexdigest(),count


def valid_hash(value):
    return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None


def load_reviews(directory:Path,*,now=None):
    now=int(time.time()) if now is None else now
    path=directory/'model-rights.json'
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>262_144:
        raise ValueError('Unsafe model rights registry')
    document=json.loads(path.read_text(),object_pairs_hook=unique_pairs)
    if (not isinstance(document,dict) or set(document)!={'schema','models'} or document['schema']!=SCHEMA
            or not isinstance(document['models'],list) or len(document['models'])>256):
        raise ValueError('Invalid model rights registry')
    result={}
    for item in document['models']:
        if not isinstance(item,dict) or set(item)!=MODEL_KEYS:
            raise ValueError('Incomplete or unknown model review fields')
        if (not isinstance(item['id'],str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,95}',item['id']) is None
                or type(item['stemCount']) is not int or not 2<=item['stemCount']<=64
                or not isinstance(item['sourceFormat'],str) or item['sourceFormat'] not in {'mlmodel','mlmodelc'}
                or not valid_hash(item['sourceSHA256']) or item['localNoncommercialOnly'] is not True
                or type(item['reviewedAt']) is not int or type(item['expiresAt']) is not int
                or not 0<item['reviewedAt']<=now<item['expiresAt']<=2**63-1
                or not isinstance(item['reviewer'],str) or not 3<=len(item['reviewer'])<=200
                or not isinstance(item['authorizationBasis'],str) or item['authorizationBasis'] not in {'written_permission','verified_license'}
                or not isinstance(item['reviewReference'],str) or len(item['reviewReference'])>2000):
            raise ValueError('Invalid,expired or incompatible model review')
        parsed=urlsplit(item['reviewReference'])
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('HTTPS rights evidence reference required')
        for label in ('license','notice'):
            filename=item[label+'File'];expected=item[label+'SHA256']
            if (not isinstance(filename,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',filename) is None
                    or not valid_hash(expected) or not 0<(directory/filename).lstat().st_size<=1_048_576
                    or digest(directory/filename)[0]!=expected):
                raise ValueError('Bundled license or notice evidence mismatch')
        key=(item['id'],item['stemCount'])
        if key in result:raise ValueError('Duplicate model review selection')
        result[key]=item
    return result


def compiled_digest(directory):
    if not stat.S_ISDIR(directory.lstat().st_mode):raise ValueError('Unsafe compiled model directory')
    entries=[]
    for path in directory.rglob('*'):
        mode=path.lstat().st_mode
        if stat.S_ISDIR(mode):continue
        if not stat.S_ISREG(mode):raise ValueError('Unsafe compiled model member')
        name=path.relative_to(directory).as_posix()
        if '\n' in name or '\0' in name or len(entries)>=8192:raise ValueError('Invalid compiled inventory')
        entries.append((name,path))
    if not entries:raise ValueError('Empty compiled model inventory')
    checksum=hashlib.sha256();total=0
    for name,path in sorted(entries,key=lambda item:item[0].encode()):
        hashed,size=digest(path);total+=size
        if total>8_589_934_592:raise ValueError('Compiled verification budget exceeded')
        checksum.update(f'{name}\0{size}\0{hashed}\n'.encode())
    return checksum.hexdigest()


def verify_source(review,path):
    actual=compiled_digest(path) if review['sourceFormat']=='mlmodelc' else digest(path)[0]
    if actual!=review['sourceSHA256']:raise ValueError('Source does not match the reviewed checkpoint bytes')
    if review['sourceFormat']=='mlmodel' and path.stat().st_size==0:raise ValueError('Empty model source')
    return actual


def check_bundled(directory,reviews):
    checked=0
    for path in directory.iterdir():
        if path.suffix.lower() not in {'.mlmodel','.mlmodelc'}:continue
        model_id='demucs-4' if path.stem=='demucs-default-4' else path.stem
        candidates=[item for (mid,_),item in reviews.items() if mid==model_id and '.'+item['sourceFormat']==path.suffix]
        if len(candidates)!=1:raise ValueError('Bundled model lacks an exact rights selection: '+path.name)
        verify_source(candidates[0],path);checked+=1
    return checked


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models-directory',type=Path,default=Path(__file__).resolve().parents[1]/'mobile/ios/MTAEditorMobile/Models')
    parser.add_argument('--model-id')
    parser.add_argument('--stem-count',type=int,default=4)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--source-format',choices=('mlmodel','mlmodelc'))
    parser.add_argument('--check-bundled',action='store_true')
    parser.add_argument('--optional-model',action='store_true',help='Print no fingerprint for an unregistered selection;never authorizes it')
    args=parser.parse_args(argv)
    try:
        reviews=load_reviews(args.models_directory)
        if args.check_bundled:
            checked=check_bundled(args.models_directory,reviews)
            print(json.dumps({'bundled_models_checked':checked,'reviewed_models':len(reviews),'release_candidate':False}))
        elif args.model_id:
            review=reviews.get((args.model_id,args.stem_count))
            if review is None or (args.source_format and review['sourceFormat']!=args.source_format):
                if args.optional_model and args.source is None:return 0
                raise ValueError('No bundled rights review for selected model and format')
            if args.source:verify_source(review,args.source)
            print(review['sourceSHA256'])
        else:print(json.dumps({'schema':SCHEMA,'reviewed_models':len(reviews),'independent_rights_review_completed':False,'release_candidate':False}))
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print('iOS model rights refused: '+str(exc),file=__import__('sys').stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
