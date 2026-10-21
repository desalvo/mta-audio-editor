#!/usr/bin/env python3
"""Build a disabled managed bundle from two complete, pinned author releases.

No downloads, weight conversions, model execution or automatic rights grants.
Preserves every original bank/vocoder member, including images and notices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import os
import zipfile

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from app.studio_asset_registry import validate_manifest,relative

BANK_SHA='fe8ee7c95883d327a2b7facbbe832a7a53e1344918dc791ca83fc23b08034110'
VOCODER_SHA='ba7d43142d41f6900c8264b5662ca7125a50feb8760bb8b9615c61a8f5e6902e'
BANK='Qixuan_v2.7.0_DiffSinger_OpenUtau'
BASE='runtime/'+BANK
MODEL='0101_qixuan_muon1_acoustic.qixuan.onnx'
VOCODER='pc_nsf_hifigan_44.1k_hop512_128bin_2025.02.onnx'
BASE_BUNDLE_SHA='011a35bd4c6667ed8f978f1a1a55e259de85c9b5e2a40858506fa33333020035'
SOURCE_BUNDLE_SHAS={BASE_BUNDLE_SHA,'f02ee089e85d58ca7ca7caff4d1e3d5ab508375d315ddcc0f0f5db8d19f1c4ac'}


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def build(bank,vocoder,destination,asset_id='qixuan-2-7-onnx-it-en-fr-context-r210'):
    for path,expected in ((bank,BANK_SHA),(vocoder,VOCODER_SHA)):
        if Path(path).is_symlink() or digest(path)!=expected:raise ValueError('Original release SHA-256 mismatch')
    destination=Path(destination)
    if destination.exists():raise ValueError('Choose a new output filename')
    files={};components={'engine':[],'acoustic':[],'vocoder':[]}
    originals={}
    fd,temp=tempfile.mkstemp(prefix='.qixuan-bundle-',dir=destination.parent);os.close(fd)
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
            def add(name,data,role):
                relative(name)
                if name.casefold() in {x.casefold() for x in files}:raise ValueError('Duplicate original member')
                files[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
                components[role].append(name);out.writestr(name,data)
            for path,prefix,role in ((bank,'runtime/','acoustic'),(vocoder,'runtime/vocoder/','vocoder')):
                with zipfile.ZipFile(path) as archive:
                    for item in archive.infolist():
                        relative(item.filename.rstrip('/'))
                        if item.is_dir():continue
                        if item.file_size>1024**3 or len(archive.infolist())>1000:raise ValueError('Oversized author package')
                        if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('Original link is not permitted')
                        data=archive.read(item);name=prefix+item.filename
                        if role=='acoustic' and not name.startswith(BASE+'/'):raise ValueError('Unexpected original bank layout')
                        add(name,data,role)
                        if name==BASE+'/0101_qixuan_muon1_acoustic.phonemes.json':originals['phones']=json.loads(data)
            acoustic_sha=files[BASE+'/'+MODEL]['sha256']
            from app.qixuan_profiles import build_profiles
            profiles=build_profiles(originals['phones'],acoustic_sha)
            for language,profile in profiles.items():
                add('profiles/qixuan-'+language+'.json',(json.dumps(profile,ensure_ascii=False,indent=2)+'\n').encode(),'acoustic')
            add('engine/LICENSE',(PROJECT/'LICENSE').read_bytes(),'engine')
            add('engine/diffsinger_onnx.py',(PROJECT/'app/diffsinger_onnx.py').read_bytes(),'engine')
            for module in ('qixuan_profiles.py','vocal_phonemizer.py','vocal_g2p_bridge.py'):
                add('engine/'+module,(PROJECT/'app'/module).read_bytes(),'engine')
            value={'schema':'mta-studio-bundle-1','id':asset_id,'name':'Qixuan 2.7.0 / ONNX / EN + contextual IT/FR projection',
                   'kind':'diffsinger','format':'openutau-onnx','languages':['en','it','fr','vocalise'],
                   'language_bindings':{language:{'phonemes':'profiles/qixuan-'+language+'.json'} for language in profiles},
                   'pronunciation_modes':{language:profile['pronunciation_mode'] for language,profile in profiles.items()},
                   'pronunciation_note':profiles['it']['notes'],
                   'bindings':{'runtime_root':'runtime','acoustic':BASE+'/'+MODEL,'config':BASE+'/dsconfig.yaml',
                               'vocoder':'runtime/vocoder/'+VOCODER,'vocoder_config':'runtime/vocoder/vocoder.yaml',
                               'phonemes':'profiles/qixuan-en.json'},
                   'policies':{'singer':'diffsinger-qixuan','vocoder':'diffsinger-vocoder'},
                   'expression_defaults':{'breathiness_db':-48.,'voicing_db':-12.},
                   'components':{'engine':'mta-analysis','acoustic':'diffsinger-qixuan','vocoder':'diffsinger-vocoder'},
                   'component_files':components,'files':files,
                   'licenses':[{'policy_model':'mta-analysis','notice':'engine/LICENSE','evidence_url':'https://github.com/desalvo/mta-audio-editor'},
                               {'policy_model':'diffsinger-qixuan','notice':BASE+'/Terms_of_Use.zh-CN.pdf',
                                'evidence_url':'https://github.com/yqzhishen/qixuan-diffsinger/blob/main/terms_of_use/Terms_of_Use.zh-CN.md'},
                               {'policy_model':'diffsinger-vocoder','notice':'runtime/vocoder/NOTICE.txt','evidence_url':'https://openvpi.github.io/vocoders/'}],
                   'original_releases':{'bank_sha256':BANK_SHA,'vocoder_sha256':VOCODER_SHA},
                   'changes':'Original bank/vocoder bytes unmodified and complete; added MTA runner evidence, English profile and explicitly disclosed Italian/French cross-language projections. Score F0/durations; explicit variance defaults, no predicted variance.'}
            validate_manifest(value)
            out.writestr('manifest.json',json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        os.link(temp,destination)
    finally:Path(temp).unlink(missing_ok=True)
    return {'file':str(destination),'bytes':destination.stat().st_size,'sha256':digest(destination),
            'enabled':False,'rights_granted':False,'original_members_preserved':sum(len(v) for k,v in components.items() if k!='engine')-3}


def upgrade(source,destination,asset_id='qixuan-2-7-onnx-it-en-fr-context-r210'):
    """Preserve complete original bank/vocoder bytes; update only MTA additions."""
    source=Path(source);destination=Path(destination)
    if source.is_symlink() or digest(source) not in SOURCE_BUNDLE_SHAS:
        raise ValueError('Pinned complete Qixuan source bundle SHA-256 mismatch')
    if destination.exists():raise ValueError('Choose a new output filename')
    from app.qixuan_profiles import build_profiles
    with zipfile.ZipFile(source) as old:
        if old.testzip() is not None:raise ValueError('Invalid source ZIP CRC')
        value=validate_manifest(json.loads(old.read('manifest.json')))
        for name,entry in value['files'].items():
            raw=old.read(name)
            if len(raw)!=entry['bytes'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']:
                raise ValueError('Incomplete or changed source bundle member')
        files=value['files'];components=value['component_files']
        phones=json.loads(old.read(BASE+'/0101_qixuan_muon1_acoustic.phonemes.json'))
        profiles=build_profiles(phones,files[BASE+'/'+MODEL]['sha256'])
        replacements={}
        for language,profile in profiles.items():
            name='profiles/qixuan-'+language+'.json'
            replacements[name]=(json.dumps(profile,ensure_ascii=False,indent=2)+'\n').encode()
            if name not in components['acoustic']:components['acoustic'].append(name)
        for module in ('diffsinger_onnx.py','qixuan_profiles.py','vocal_phonemizer.py','vocal_g2p_bridge.py'):
            name='engine/'+module;replacements[name]=(PROJECT/'app'/module).read_bytes()
            if name not in components['engine']:components['engine'].append(name)
        for name,raw in replacements.items():
            files[name]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        value.update(id=asset_id,name='Qixuan 2.7.0 / ONNX / EN + contextual IT/FR projection',
            languages=['en','it','fr','vocalise'],
            language_bindings={language:{'phonemes':'profiles/qixuan-'+language+'.json'} for language in profiles},
            pronunciation_modes={language:profile['pronunciation_mode'] for language,profile in profiles.items()},
            pronunciation_note=profiles['it']['notes'],
            changes='Complete original bank/vocoder bytes unchanged. MTA additions: EN profile and explicit IT/FR cross-language projections; no native IT/FR acoustic language or quality claim.')
        validate_manifest(value)
        fd,temporary=tempfile.mkstemp(prefix='.qixuan-itfr-',dir=destination.parent);os.close(fd)
        try:
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as out:
                for item in old.infolist():
                    if item.filename!='manifest.json' and item.filename not in replacements:
                        out.writestr(item,old.read(item))
                for name,raw in replacements.items():out.writestr(name,raw)
                out.writestr('manifest.json',json.dumps(value,ensure_ascii=False,indent=2)+'\n')
            os.link(temporary,destination)
        finally:Path(temporary).unlink(missing_ok=True)
    return {'file':str(destination),'bytes':destination.stat().st_size,'sha256':digest(destination),
            'enabled':False,'rights_granted':False,'original_members_preserved':37,
            'languages':value['languages'],'pronunciation_modes':value['pronunciation_modes']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank',type=Path);parser.add_argument('--vocoder',type=Path)
    parser.add_argument('--source-bundle',type=Path,help='Upgrade the exact pinned previous complete MTA bundle')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--id',default=None)
    args=parser.parse_args()
    if args.source_bundle:
        if args.bank or args.vocoder:parser.error('Choose source-bundle or bank+vocoder')
        result=upgrade(args.source_bundle,args.output,**({'asset_id':args.id} if args.id else {}))
    else:
        if not args.bank or not args.vocoder:parser.error('Supply bank+vocoder or source-bundle')
        result=build(args.bank,args.vocoder,args.output,**({'asset_id':args.id} if args.id else {}))
    print(json.dumps(result,indent=2))
