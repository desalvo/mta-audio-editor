"""Managed neural assets: explicit admin ZIP install, immutable hashes and rights.

No model downloads, user-selected executable paths or automatic license grants.
Installed packages are untrusted until an administrator authorizes their actual
components. Model files may contain executable pickle/code: only operator-owned
bundles may be admitted. All inference still runs in existing isolated workers.
"""
import hashlib
from functools import lru_cache
import io
import json
import os
from pathlib import Path,PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile
from urllib.parse import urlsplit

ID=re.compile(r'[a-z][a-z0-9-]{0,63}')
KINDS={'diffsinger','vocoder','seed-vc','rvc','transkun'}
MAX_FILES=10000
MAX_BUNDLE=4*1024**3
REQUIRED={'diffsinger':{'runtime_root','acoustic','config','vocoder','phonemes'},
          'vocoder':{'checkpoint'},'seed-vc':{'runtime_root','script','checkpoint','config','reference','hf_home'},
          'rvc':{'runtime_root','script','checkpoint'},'transkun':{'runtime_root','checkpoint','config'}}


def root():
    from .studio_catalog import root as studio_root
    path=studio_root()/'managed'
    if path.is_symlink():raise ValueError('Unsafe managed asset root')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path


def relative(value):
    if (not isinstance(value,str) or not 1<=len(value)<=300 or '\\' in value or '\x00' in value
            or PurePosixPath(value).is_absolute() or any(p in ('','..','.') for p in value.split('/'))
            or ':' in value):raise ValueError('Unsafe bundle-relative path')
    return value


def validate_manifest(value):
    if not isinstance(value,dict) or value.get('schema')!='mta-studio-bundle-1':raise ValueError('Invalid studio bundle schema')
    if not isinstance(value.get('id'),str) or not ID.fullmatch(value['id']) or not isinstance(value.get('kind'),str) or value.get('kind') not in KINDS:
        raise ValueError('Invalid studio bundle identity')
    if not isinstance(value.get('name'),str) or not 1<=len(value['name'])<=160:raise ValueError('Invalid bundle name')
    model_format=value.get('format','native')
    if model_format not in ('native','openutau-onnx') or (model_format!='native' and value['kind']!='diffsinger'):
        raise ValueError('Unsupported model format')
    if not isinstance(value.get('languages'),list) or any(l not in ('it','en','fr','vocalise') for l in value['languages']):
        raise ValueError('Invalid bundle language inventory')
    modes=value.get('pronunciation_modes',{})
    if (not isinstance(modes,dict) or set(modes)-set(value['languages'])
            or any(mode not in ('native-inventory','cross-language') for mode in modes.values())):
        raise ValueError('Invalid pronunciation modes')
    if 'pronunciation_note' in value and (not isinstance(value['pronunciation_note'],str)
                                          or not 1<=len(value['pronunciation_note'])<=1000):
        raise ValueError('Invalid pronunciation note')
    files=value.get('files')
    if not isinstance(files,dict) or not 1<=len(files)<=MAX_FILES:raise ValueError('Invalid bundle file inventory')
    folded=set();total=0
    for name,entry in files.items():
        relative(name)
        if name.casefold() in folded or name in ('manifest.json','receipt.json'):raise ValueError('Duplicate/reserved bundle path')
        folded.add(name.casefold())
        if (not isinstance(entry,dict) or set(entry)!={'bytes','sha256'} or type(entry['bytes']) is not int
                or not 0<=entry['bytes']<=MAX_BUNDLE or not isinstance(entry['sha256'],str)
                or not re.fullmatch('[a-f0-9]{64}',entry['sha256'])):raise ValueError('Invalid bundle file hash/size')
        total+=entry['bytes']
    if total>MAX_BUNDLE:raise ValueError('Bundle exceeds 4 GiB expanded size')
    bindings=value.get('bindings')
    if not isinstance(bindings,dict) or set(bindings)-{'runtime_root','script','checkpoint','config','reference','hf_home','acoustic','vocoder','vocoder_config','phonemes','lexicon','index','experiment'}:
        raise ValueError('Unsupported model asset binding')
    if not REQUIRED[value['kind']]<=set(bindings):raise ValueError('Incomplete model asset bindings')
    for key,path in bindings.items():
        if key=='experiment':
            if not isinstance(path,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',path):raise ValueError('Invalid DiffSinger experiment')
        else:
            relative(path)
            if key not in ('runtime_root','hf_home') and path not in files:raise ValueError('Asset binding is absent from pinned inventory')
    if value['kind']=='diffsinger':
        if model_format=='native':
            if 'experiment' not in bindings:raise ValueError('DiffSinger experiment binding required')
            prefix=bindings['runtime_root']+'/checkpoints/'+bindings['experiment']+'/'
            if bindings['config']!=prefix+'config.yaml' or not bindings['acoustic'].startswith(prefix):
                raise ValueError('DiffSinger checkpoint/config must belong to the exact experiment')
            if bindings['runtime_root']+'/scripts/infer.py' not in files:
                raise ValueError('Pinned OpenVPI acoustic inference script missing')
        else:
            if 'vocoder_config' not in bindings:raise ValueError('ONNX vocoder metadata is required')
            if any(not bindings[k].startswith(bindings['runtime_root']+'/') for k in ('config','acoustic','vocoder_config')):
                raise ValueError('ONNX configuration and models must belong to the pinned runtime')
            if not all(bindings[k].endswith('.onnx') for k in ('acoustic','vocoder')):
                raise ValueError('ONNX models required')
            from .vocal_expression import Expression
            defaults=value.get('expression_defaults',{})
            if not isinstance(defaults,dict) or set(defaults)-{'energy_db','breathiness_db','voicing_db','tension_db','gender','speed'}:
                raise ValueError('Invalid ONNX expression defaults')
            Expression.model_validate(defaults)
        languages=value.get('language_bindings',{})
        if not isinstance(languages,dict) or set(languages)-set(value['languages']):raise ValueError('Invalid per-language profile bindings')
        for language,mapping in languages.items():
            if not isinstance(mapping,dict) or set(mapping)-{'phonemes','lexicon'} or 'phonemes' not in mapping:
                raise ValueError('Each declared language needs its reviewed phone profile')
            if any(not isinstance(path,str) or path not in files for path in mapping.values()):raise ValueError('Per-language profile absent from pinned files')
        if len(set(value['languages'])-{'vocalise'})>1 and not set(value['languages'])-{'vocalise'}<=set(languages):
            raise ValueError('Multilingual bank requires independently reviewed language profiles')
        roles=value.get('policies',{})
        if not isinstance(roles,dict) or set(roles)!={'singer','vocoder'} or any(not isinstance(p,str) for p in roles.values()) or roles['singer']==roles['vocoder']:
            raise ValueError('Declare separate singer and vocoder policy identities')
    notices=value.get('licenses')
    if not isinstance(notices,list) or not 1<=len(notices)<=32:raise ValueError('Each model component requires license evidence')
    for notice in notices:
        if not isinstance(notice,dict) or set(notice)!={'policy_model','notice','evidence_url'}:raise ValueError('Invalid model license reference')
        if not isinstance(notice['policy_model'],str) or not ID.fullmatch(notice['policy_model']):raise ValueError('Invalid policy model identity')
        if not isinstance(notice['notice'],str) or notice['notice'] not in files:raise ValueError('License text absent from pinned inventory')
        if not isinstance(notice['evidence_url'],str):raise ValueError('Invalid license evidence URL')
        url=urlsplit(notice['evidence_url'])
        if url.scheme!='https' or not url.hostname or url.username or url.password:raise ValueError('Public HTTPS license evidence required')
    required_policy={'seed-vc':'seed-vc-assets','rvc':'rvc-assets','transkun':'transkun-assets'}.get(value['kind'])
    if required_policy and required_policy not in {n['policy_model'] for n in notices}:
        raise ValueError('Managed backend requires its independent checkpoint license policy')
    if any(files[n['notice']]['bytes']==0 for n in notices):raise ValueError('License notices cannot be empty')
    required_components={
        'diffsinger':{'engine','acoustic','vocoder'},'vocoder':{'checkpoint'},
        'seed-vc':{'engine','acoustic','pitch_extractor','speaker_encoder','semantic_encoder','vocoder','reference_voice'},
        'rvc':{'engine','acoustic','pitch_extractor','semantic_encoder','voice_authorization'},
        'transkun':{'engine','checkpoint'}}[value['kind']]
    components=value.get('components');component_files=value.get('component_files')
    if (not isinstance(components,dict) or not required_components<=set(components)
            or not isinstance(component_files,dict) or set(component_files)!=set(components)):
        raise ValueError('Declare every backend component, its policy and pinned files')
    identities={n['policy_model'] for n in notices}
    for role,policy in components.items():
        members=component_files[role]
        if not isinstance(policy,str) or policy not in identities or not isinstance(members,list) or not members or any(not isinstance(path,str) or path not in files for path in members):
            raise ValueError('Component permission/file inventory is incomplete')
    assigned={name for members in component_files.values() for name in members}
    if set(files)-assigned-{n['notice'] for n in notices}:raise ValueError('Every model/runtime file requires an explicit component policy')
    for key,role in ({'checkpoint':'acoustic','reference':'reference_voice'} if value['kind']=='seed-vc' else
                     {'checkpoint':'acoustic'} if value['kind']=='rvc' else
                     {'acoustic':'acoustic','vocoder':'vocoder'} if value['kind']=='diffsinger' else {'checkpoint':'checkpoint'}).items():
        if bindings[key] not in component_files[role]:raise ValueError('Selected asset is outside its declared component permission')
    if value['kind']=='diffsinger' and (value['policies']['singer']!=components['acoustic'] or value['policies']['vocoder']!=components['vocoder']):
        raise ValueError('Selected singer/vocoder policy does not match its component identity')
    if value['kind']=='diffsinger' and not bindings['vocoder'].startswith(bindings['runtime_root']+'/'):
        raise ValueError('DiffSinger vocoder must be included in the pinned runtime experiment bundle')
    if value['kind']=='diffsinger' and not set(value['policies'].values())<={n['policy_model'] for n in notices}:
        raise ValueError('Singer/vocoder policy evidence missing')
    if value['kind']=='diffsinger' and len({n['policy_model'] for n in notices})<2:
        raise ValueError('DiffSinger singer and vocoder require distinct license identities')
    return value


def _file_identity(info):
    return (info.st_dev,info.st_ino,info.st_mode,info.st_nlink,info.st_size,
            info.st_mtime_ns,info.st_ctime_ns)


@lru_cache(maxsize=32768)
def _verified_digest(path,identity):
    # Avoid rehashing multi-GiB immutable checkpoints at every policy heartbeat.
    # ctime catches replacements/writes even if an operator restores mtime.
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or _file_identity(info)!=identity:
            raise ValueError('Managed asset changed during verification')
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if _file_identity(os.fstat(stream.fileno()))!=identity:
            raise ValueError('Managed asset changed during verification')
        return digest


def manifest(asset_id,verify=False):
    if not isinstance(asset_id,str) or not ID.fullmatch(asset_id):raise ValueError('Invalid managed asset ID')
    folder=root()/asset_id;receipt=folder/'receipt.json';path=folder/'manifest.json'
    if folder.is_symlink() or path.is_symlink() or receipt.is_symlink() or not path.is_file() or not receipt.is_file():
        raise ValueError('Managed model asset not installed')
    if path.stat().st_size>4*1024**2 or receipt.stat().st_size>16384:raise ValueError('Managed asset receipt exceeds limit')
    data=path.read_bytes();record=json.loads(receipt.read_text())
    if record.get('manifest_sha256')!=hashlib.sha256(data).hexdigest():raise ValueError('Managed asset manifest checksum mismatch')
    value=validate_manifest(json.loads(data))
    if value['id']!=asset_id:raise ValueError('Managed asset identity mismatch')
    if verify:
        # Runtime imports and checkpoint discovery must not see unpinned files
        # added after installation, including links inside otherwise empty dirs.
        allowed=set(value['files'])|{'manifest.json','receipt.json'}
        for target in folder.rglob('*'):
            if target.is_symlink() or (not target.is_dir() and target.relative_to(folder).as_posix() not in allowed):
                raise ValueError('Unpinned/unsafe managed asset file')
        for name,entry in value['files'].items():
            target=folder/name
            if target.is_symlink() or not target.resolve().is_relative_to(folder.resolve()) or not target.is_file() or target.stat().st_nlink!=1:
                raise ValueError('Unsafe/missing managed asset file')
            identity=_file_identity(target.stat())
            if (identity[4]!=entry['bytes'] or _verified_digest(target,identity)!=entry['sha256']
                    or _file_identity(target.stat())!=identity):
                raise ValueError('Managed asset file checksum mismatch: '+name)
    return {**value,'enabled':record.get('enabled') is True,'folder':folder}


def policies(asset_id,verify=False):
    from .model_license_policy import evaluate_model
    value=manifest(asset_id,verify)
    if not value['enabled']:raise ValueError('Managed model asset is disabled')
    return [evaluate_model(notice['policy_model']) for notice in value['licenses']]


def catalog():
    result=[]
    for path in sorted(root().iterdir()):
        if not ID.fullmatch(path.name):continue
        try:
            value=manifest(path.name)
            error=''
            try:policies(path.name)
            except ValueError as exc:error=str(exc)
            result.append({key:value[key] for key in ('id','name','kind','languages','enabled')}|{
                'installed':True,'asset_sha256':hashlib.sha256((value['folder']/'manifest.json').read_bytes()).hexdigest(),'admitted':not error,'error':error,'real_inference_validated':False,
                'pronunciation_modes':value.get('pronunciation_modes',{}),'pronunciation_note':value.get('pronunciation_note',''),
                'licenses':[{k:n[k] for k in ('policy_model','evidence_url')} for n in value['licenses']]})
        except (ValueError,OSError,KeyError) as exc:
            result.append({'id':path.name,'name':path.name,'kind':'invalid','installed':False,'admitted':False,'error':str(exc)})
    return result


def install(bundle,cancelled=lambda:False,progress=lambda *a:None):
    """Install verified bytes atomically and disabled; never overwrite a model."""
    from .ai_project_lock import project_publication_lock
    from .storage import _atomic_json_write
    from .fs_durability import sync_directory
    with project_publication_lock('studio-model:managed'):
        source=io.BytesIO(bundle) if isinstance(bundle,bytes) else bundle
        with zipfile.ZipFile(source) as archive:
            entries=archive.infolist();names=[e.filename for e in entries if not e.is_dir()]
            if len(entries)>MAX_FILES+1000 or len(names)!=len(set(n.casefold() for n in names)):raise ValueError('Duplicate/oversized bundle inventory')
            for entry in entries:
                relative(entry.filename.rstrip('/'))
                mode=entry.external_attr>>16
                if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR)):
                    raise ValueError('Links/devices in model bundle are forbidden')
            meta=archive.getinfo('manifest.json')
            if meta.file_size>4*1024**2:raise ValueError('Bundle manifest too large')
            raw=archive.read(meta);value=validate_manifest(json.loads(raw))
            if set(names)!=set(value['files'])|{'manifest.json'}:raise ValueError('Unpinned/missing files in model bundle')
            folder=root();destination=folder/value['id']
            if destination.exists() or destination.is_symlink():raise ValueError('Model ID already installed; use a new versioned ID')
            with tempfile.TemporaryDirectory(prefix='.install-',dir=folder) as temporary:
                work=Path(temporary)/'package';work.mkdir(mode=0o700)
                for index,(name,expected) in enumerate(value['files'].items()):
                    if cancelled():raise RuntimeError('Model installation cancelled')
                    entry=archive.getinfo(name)
                    if entry.file_size!=expected['bytes']:raise ValueError('Bundle declared file size mismatch')
                    target=work/name;target.parent.mkdir(parents=True,exist_ok=True)
                    h=hashlib.sha256();count=0
                    with archive.open(entry) as inp,target.open('xb') as out:
                        while block:=inp.read(1024*1024):
                            if cancelled():raise RuntimeError('Model installation cancelled')
                            count+=len(block)
                            if count>expected['bytes']:raise ValueError('Expanded model file exceeds pinned size')
                            h.update(block);out.write(block)
                        out.flush();os.fsync(out.fileno())
                    if count!=expected['bytes'] or h.hexdigest()!=expected['sha256']:raise ValueError('Model asset SHA-256 mismatch')
                    progress('verifying',index+1,len(value['files']))
                for binding in ('runtime_root','hf_home'):
                    if binding in value['bindings']:(work/value['bindings'][binding]).mkdir(parents=True,exist_ok=True)
                (work/'manifest.json').write_bytes(raw)
                _atomic_json_write(work/'receipt.json',{'manifest_sha256':hashlib.sha256(raw).hexdigest(),'enabled':False})
                with (work/'manifest.json').open('rb') as stream:os.fsync(stream.fileno())
                sync_directory(work)
                if cancelled():raise RuntimeError('Model installation cancelled before activation')
                os.rename(work,destination);sync_directory(folder)
    return {'id':value['id'],'installed':True,'enabled':False,'real_inference_validated':False}


def configure(asset_id,enabled):
    from .ai_project_lock import project_publication_lock
    from .storage import _atomic_json_write
    if type(enabled) is not bool:raise ValueError('Expected enabled boolean')
    with project_publication_lock('studio-model:managed'):
        value=manifest(asset_id,verify=enabled)
        if enabled:
            from .model_license_policy import evaluate_model
            for notice in value['licenses']:evaluate_model(notice['policy_model'])
        path=value['folder']/'receipt.json';record=json.loads(path.read_text());record['enabled']=enabled
        _atomic_json_write(path,record)
    return {'id':asset_id,'enabled':enabled}


def remove(asset_id):
    from .ai_project_lock import project_publication_lock
    from . import ai_arranger_runtime as queue
    with project_publication_lock('studio-model:managed'):
        with queue._db() as con:
            if con.execute("SELECT 1 FROM jobs WHERE operation LIKE 'worker:studio-%' AND state IN ('running','queued','blocked') LIMIT 1").fetchone():
                raise ValueError('Wait for active Studio jobs before removing model assets')
        folder=manifest(asset_id)['folder'];shutil.rmtree(folder)
    return {'id':asset_id,'removed':True}


def runtime(asset_id,kind=None):
    value=manifest(asset_id,verify=True)
    if kind and value['kind']!=kind:raise ValueError('Wrong managed model kind')
    policies(asset_id)
    envkey='MTA_STUDIO_'+value['kind'].upper().replace('-','_')+'_PYTHON'
    if value['kind']=='diffsinger':envkey='MTA_DIFFSINGER_PYTHON'
    from .diffsinger_bridge import safe_file
    python=safe_file(str(Path(os.environ.get(envkey,'')).resolve()),os.environ.get(envkey+'_SHA256',''))
    return value,python


def binding(value,name):return value['folder']/value['bindings'][name]



def singer_environment(asset_id,language):
    value,python=runtime(asset_id,'diffsinger')
    if language not in value['languages']:raise ValueError('Selected voicebank does not declare this language')
    b={**value['bindings'],**value.get('language_bindings',{}).get(language,{})};files=value['files']
    def digest(name):return files[b[name]]['sha256']
    def path(name):return value['folder']/b[name]
    env={'MTA_DIFFSINGER_ROOT':str(binding(value,'runtime_root')),'MTA_DIFFSINGER_EXPERIMENT':b.get('experiment',value['id']),
         'MTA_DIFFSINGER_PYTHON':str(python),'MTA_DIFFSINGER_PYTHON_SHA256':os.environ['MTA_DIFFSINGER_PYTHON_SHA256'],
         'MTA_NEURAL_SINGER_CHECKPOINT':str(binding(value,'acoustic')),'MTA_NEURAL_SINGER_SHA256':digest('acoustic'),
         'MTA_DIFFSINGER_CONFIG_SHA256':digest('config'),'MTA_DIFFSINGER_VOCODER':str(binding(value,'vocoder')),
         'MTA_DIFFSINGER_VOCODER_SHA256':digest('vocoder'),'MTA_NEURAL_SINGER_POLICY_MODEL':value['policies']['singer'],
         'MTA_DIFFSINGER_VOCODER_POLICY_MODEL':value['policies']['vocoder'],
         'MTA_DIFFSINGER_PHONEMES':str(path('phonemes')),'MTA_DIFFSINGER_PHONEMES_SHA256':digest('phonemes')}
    env['MTA_DIFFSINGER_FORMAT']=value.get('format','native')
    if value.get('format')=='openutau-onnx':
        manifest_path=value['folder']/'manifest.json'
        env.update(MTA_DIFFSINGER_ONNX_INVENTORY=str(manifest_path),
                   MTA_DIFFSINGER_ONNX_INVENTORY_SHA256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
    if 'lexicon' in b:env.update(MTA_DIFFSINGER_LEXICON=str(path('lexicon')),MTA_DIFFSINGER_LEXICON_SHA256=digest('lexicon'))
    return env,value
