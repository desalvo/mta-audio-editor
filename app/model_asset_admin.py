"""Administrator-only, engine-grouped model files and fixed-source maintenance.

No path or URL is accepted from a request. Installed files are discovered only
inside operator-configured model roots/verified receipts. Downloaded bytes never
activate a model or grant permission to use it. Missing manifest members remain
visible, including sidecars and transitive HF dependencies.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from urllib.parse import quote

ENGINE_NAMES={'whisper':'Whisper / lyrics','chords':'Chord recognition','demucs':'Demucs / separation',
    'drumsep':'DrumSep','vocals':'UVR / vocal separation','ace':'ACE-Step','basic-pitch':'Basic Pitch',
    'mr-mt3':'MR-MT3','yourmt3':'YourMT3','diffsinger':'DiffSinger / Qixuan','rvc':'RVC','seed-vc':'Seed-VC',
    'transkun':'Transkun','vocoder':'Vocoders','oddvoices':'OddVoices','gm':'General MIDI',
    'shared':'Shared / other model caches'}
MAX_SCAN=200000
EXCLUDED={'.git','__pycache__','.locks','site-packages','node_modules'}
CREDENTIALS={'.env','token','stored_tokens','credentials','credentials.json','config.json.token'}


def _data():
    from .auth import data_root
    return data_root()


def staging():
    return _data()/'.model-assets'


def _safe_relative(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ValueError('Invalid model-relative name')
    parts=name.split('/')
    if PurePosixPath(name).is_absolute() or any(p in ('','..','.') for p in parts):
        raise ValueError('Invalid model-relative name')
    return name


def _safe_path(root,name,*,allow_hf_link=False):
    _safe_relative(name)
    root=Path(root)
    if root.is_symlink():raise ValueError('Unsafe model root link')
    target=root/name
    for parent in [target.parent,*target.parents]:
        if parent==root.parent:break
        if parent.is_symlink():raise ValueError('Unsafe model directory link')
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('Model path escapes its root')
    if target.is_symlink() and not allow_hf_link:raise ValueError('Unsafe model file link')
    if target.exists() and not target.is_file():raise ValueError('Model entry is not a regular file')
    return target


def _json(path,limit=4*1024**2):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>limit:raise ValueError('Unsafe model metadata')
    return json.loads(path.read_text())


def sources():
    path=Path(__file__).with_name('studio_assets')/'admin_external_sources.json'
    return _json(path).get('sources',[]) if path.exists() else []


def _hf_source(relative):
    parts=PurePosixPath(relative).parts
    for index,part in enumerate(parts):
        if not part.startswith('models--') or len(parts)<index+4 or parts[index+1]!='snapshots':continue
        repo=part[len('models--'):].replace('--','/')
        revision=parts[index+2];name='/'.join(parts[index+3:])
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) or not re.fullmatch('[a-f0-9]{40}',revision):continue
        return {'repo_id':repo,'revision':revision,'filename':name,
                'url':f'https://huggingface.co/{repo}/resolve/{revision}/{quote(name,safe="/")}',
                'source_url':f'https://huggingface.co/{repo}/tree/{revision}'}
    return None


def _engine_for_repo(relative,default):
    lowered=relative.lower()
    for engine,terms in [('rvc',['hubert','rmvpe','voiceconversionwebui']),('seed-vc',['seed-vc','bigvgan','campplus']),
                         ('demucs',['htdemucs','demucs']),('ace',['ace-step','acestep']),('whisper',['whisper']),
                         ('transkun',['transkun']),('yourmt3',['yourmt3']),('diffsinger',['qixuan','diffsinger'])]:
        if any(term in lowered for term in terms):return engine
    return default


def _roots():
    from .model_storage import roots
    from .studio_catalog import root as studio_root
    rename={'server':'demucs','coreml':'demucs','onnx':'demucs','managed':'demucs','lyrics':'whisper',
            'huggingface':'shared','torch':'shared','whisper':'whisper'}
    result=[(rename.get(engine,engine),path) for engine,path in roots()]
    from .chord_ml import model_root
    result.append(('chords',model_root()))
    result.extend([('ace',Path(os.getenv('MTA_ACE_STEP_DESKTOP_DIR',str(Path.home()/'.local/share/mta-audio-editor/ace-step')))/'models'),
                   ('shared',staging()),('basic-pitch',studio_root()/'basic-pitch-0.4.0-onnx-v1'),
                   ('oddvoices',studio_root()/'oddvoices'),('gm',_data()/'soundfonts'),
                   ('gm',Path(os.getenv('MTA_GM_SOUNDFONT_DIR',str(_data()/'soundfonts'))))])
    legacy=os.getenv('MTA_DIFFSINGER_ROOT')
    if legacy:
        folder=Path(legacy)
        if not folder.is_absolute():raise ValueError('Legacy DiffSinger root must be absolute')
        result.append(('diffsinger',folder))
    # Never recurse through the YourMT3 venv: its receipt identifies exact source/weight members.
    return result


def _record(root,relative,engine,*,expected=None,asset=None,source=None,origin='cache'):
    path=_safe_path(root,relative,allow_hf_link=_hf_source(relative) is not None)
    installed=path.is_file()
    identifier=hashlib.sha256((str(path.absolute())).encode()).hexdigest()
    value={'id':identifier,'engine':engine,'name':relative,'kind':'file','origin':origin,
           'installed':installed,'bytes':path.stat().st_size if installed else expected.get('bytes') if expected else None,
           'expected_sha256':expected.get('sha256') if expected else None,
           'source':source or _hf_source(relative),'asset_id':asset,
           '_root':Path(root),'_path':path,'_expected':expected,'_asset':asset}
    value['engines']=sorted({engine,*((value['source'] or {}).get('consumers',[]))})
    return value


def records():
    """Complete scan or explicit failure; no hidden first-N model inventory."""
    found={};warnings=[];pins=sources();by_hash={p['sha256']:p for p in pins if p.get('sha256')}
    def add(row):
        previous=found.get(row['id'])
        if previous is None:
            found[row['id']]=row
        else:
            # Preserve the managed/receipt owner when the same absolute file is
            # also reached through a broader HF cache root or source pin.
            keep=previous if previous['_asset'] or previous['_expected'] else row
            other=row if keep is previous else previous
            if not keep['_expected'] and other['_expected']:
                keep['_expected']=other['_expected'];keep['expected_sha256']=other['expected_sha256']
            if not keep['source'] and other['source']:keep['source']=other['source']
            keep['engines']=sorted(set(keep['engines'])|set(other['engines']))
            found[row['id']]=keep
        if len(found)>MAX_SCAN:raise ValueError('Model inventory exceeds 200000 files; no partial inventory returned')
    # Complete reviewed manifests retain missing members and independent component labels.
    from .studio_asset_registry import root as managed_root,manifest
    managed=managed_root()
    for folder in sorted(managed.iterdir()):
        if folder.name.startswith('.'):continue
        try:
            model=manifest(folder.name)
            for name,expected in model['files'].items():
                add(_record(folder,name,model['kind'],expected=expected,asset=folder.name,
                            source=by_hash.get(expected['sha256']),origin='managed'))
            # Supplemental HF files downloaded by runtimes below an approved bundle root.
            for base,dirs,files in os.walk(folder,followlinks=False):
                dirs[:]=[d for d in dirs if d not in EXCLUDED and not (Path(base)/d).is_symlink()]
                for name in files:
                    path=Path(base)/name;relative=path.relative_to(folder).as_posix()
                    if name in ('manifest.json','receipt.json') or name in CREDENTIALS:continue
                    if relative not in model['files']:add(_record(folder,relative,model['kind'],origin='managed-cache',asset=folder.name))
        except (OSError,ValueError,KeyError) as exc:warnings.append(f'Managed {folder.name}: {exc}')
    from .studio_catalog import root as studio_root, MODEL_SHA
    bp=studio_root()/'basic-pitch.json'
    if bp.is_file():
        try:
            value=_json(bp,32768)
            add(_record(studio_root()/'basic-pitch-0.4.0-onnx-v1',value['model'],'basic-pitch',
                        expected={'sha256':MODEL_SHA},origin='runtime-receipt'))
        except (ValueError,OSError,KeyError) as exc:warnings.append(f'Basic Pitch: {exc}')
    mr=os.getenv('MTA_STUDIO_MRMT3_RUNTIME')
    if mr:
        try:
            folder=Path(mr);value=_json(folder/'mta-runtime.json',131072)
            for relative,digest in value.get('files',{}).items():
                add(_record(folder,relative,'mr-mt3',expected={'sha256':digest},source=by_hash.get(digest),origin='runtime-receipt'))
            digest=value.get('python_sha256')
            if isinstance(digest,str) and re.fullmatch('[a-f0-9]{64}',digest):
                add(_record(folder,'Scripts/python.exe' if os.name=='nt' else 'bin/python','mr-mt3',
                            expected={'sha256':digest,'mode':0o755},origin='runtime-interpreter'))
        except (ValueError,OSError,KeyError) as exc:warnings.append(f'MR-MT3: {exc}')
    for variable,digest_variable in [('MTA_NEURAL_SINGER_CHECKPOINT','MTA_NEURAL_SINGER_SHA256'),
                                    ('MTA_DIFFSINGER_VOCODER','MTA_DIFFSINGER_VOCODER_SHA256'),
                                    ('MTA_DIFFSINGER_PHONEMES','MTA_DIFFSINGER_PHONEMES_SHA256'),
                                    ('MTA_DIFFSINGER_LEXICON','MTA_DIFFSINGER_LEXICON_SHA256')]:
        raw=os.getenv(variable);digest=os.getenv(digest_variable,'').lower()
        if raw:
            try:
                path=Path(raw)
                if not path.is_absolute() or not re.fullmatch('[a-f0-9]{64}',digest):raise ValueError('Absolute pinned model path required')
                add(_record(path.parent,path.name,'diffsinger',expected={'sha256':digest},source=by_hash.get(digest),origin='operator-binding'))
            except (ValueError,OSError) as exc:warnings.append(f'{variable}: {exc}')
    runtime=os.getenv('MTA_STUDIO_YOURMT3_RUNTIME')
    if runtime:
        root=Path(runtime)
        for name in ('mta-runtime.json','mta-runtime-ps.json'):
            receipt=root/name
            if not receipt.exists():continue
            try:
                value=_json(receipt,131072)
                for relative,digest in value.get('files',{}).items():
                    add(_record(root,relative,'yourmt3',expected={'sha256':digest},source=by_hash.get(digest),origin='runtime-receipt'))
            except (ValueError,OSError,KeyError) as exc:warnings.append(f'YourMT3 {name}: {exc}')
    scanned=set();count=0
    for engine,root in _roots():
        if not root.exists():continue
        if root.is_symlink():warnings.append(f'{engine}: model root link is not traversed');continue
        identity=str(root.absolute())
        if identity in scanned:continue
        scanned.add(identity)
        def onerror(exc):warnings.append(f'{engine}: {type(exc).__name__}')
        for base,dirs,files in os.walk(root,followlinks=False,onerror=onerror):
            dirs[:]=[d for d in dirs if d not in EXCLUDED and not (Path(base)/d).is_symlink()]
            # Skip interpreter libraries, even for the Basic Pitch runtime.
            if root.name=='basic-pitch-0.4.0-onnx-v1' or (root/'pyvenv.cfg').is_file():dirs[:]=[d for d in dirs if d not in ('lib','lib64','bin','Scripts','include','share')]
            for name in files:
                if name in CREDENTIALS or name.endswith(('.lock','.pyc','.partial','.tmp')):continue
                count+=1
                if count>MAX_SCAN:raise ValueError('Model inventory exceeds 200000 files; split configured model roots. No partial inventory returned.')
                path=Path(base)/name;relative=path.relative_to(root).as_posix()
                try:add(_record(root,relative,_engine_for_repo(relative,engine)))
                except (OSError,ValueError) as exc:warnings.append(f'{engine}/{relative}: {exc}')
    # Published sources stay listed when missing. Model HF files land directly
    # in the immutable snapshot cache; archives/code remain staged until installed.
    cache=Path(os.getenv('XDG_CACHE_HOME',str(Path.home()/'.cache')))
    hub=Path(os.getenv('HF_HUB_CACHE',str(Path(os.getenv('HF_HOME',str(cache/'huggingface')))/'hub')))
    for pin in pins:
        repo=pin.get('repo_id','')
        if pin.get('source_kind','huggingface-model').startswith('huggingface') and '/spaces/' not in pin['url']:
            name='models--'+repo.replace('/','--')+'/snapshots/'+pin['revision']+'/'+pin['filename']
            target_root=hub
        else:
            name=pin['engine']+'/'+pin['id']+'/'+pin['filename'];target_root=staging()
        add(_record(target_root,name,pin['engine'],expected=pin,source=pin,origin='source-download'))
    return sorted(found.values(),key=lambda row:(row['engine'],row['name'])),sorted(set(warnings))


def public(row):
    value={k:v for k,v in row.items() if not k.startswith('_')}
    value['can_download']=bool(row['source'])
    value['can_restore']=bool(row['_expected'] and row['_expected'].get('sha256'))
    value['can_delete']=row['installed']
    return value


def inventory(engine='',search='',offset=0,limit=100):
    rows,warnings=records()
    engines=[{'id':name,'name':ENGINE_NAMES.get(name,name),'files':sum(name in r['engines'] for r in rows)}
             for name in sorted(ENGINE_NAMES.keys()|{r['engine'] for r in rows})]
    selected=[r for r in rows if (not engine or engine in r['engines']) and search.casefold() in r['name'].casefold()]
    return {'engines':engines,'files':[public(row) for row in selected[offset:offset+limit]],
            'total':len(selected),'offset':offset,'limit':limit,'next_offset':offset+limit if offset+limit<len(selected) else None,
            'complete':not warnings,'warnings':warnings,'activation_changed':False,
            'note':'Source downloads and exact-file restoration do not install a runtime or grant model rights. Managed model admission remains separate.'}


def find(identifier):
    if not re.fullmatch('[a-f0-9]{64}',identifier):raise ValueError('Unknown model file ID')
    row=next((r for r in records()[0] if r['id']==identifier),None)
    if row is None:raise ValueError('Unknown model file ID')
    return row


def _running(con,job_id):
    return con.execute("""SELECT 1 FROM jobs WHERE job_id!=? AND (state='running' OR
        (state IN ('queued','blocked') AND operation NOT IN ('worker:studio-install','worker:studio-test',
        'download-lyrics-model','download-chords-model'))) LIMIT 1""",(job_id or '',)).fetchone()


@contextmanager
def mutation(job_id=None):
    """Block active jobs, hold Studio readers' locks and serialize queue admission."""
    from . import ai_arranger_runtime as queue
    from .ai_project_lock import project_publication_lock
    with queue._db() as con:
        if _running(con,job_id):raise ValueError('Wait for running AI jobs and queued inference jobs before changing model files')
    with ExitStack() as stack:
        for key in ('studio-model:basic-pitch','studio-model:managed','studio-model:oddvoices','studio-model:gm','model-admin-files'):
            stack.enter_context(project_publication_lock(key))
        with queue._db() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                if _running(con,job_id):raise ValueError('Wait for running AI jobs and queued inference jobs before changing model files')
                yield
                con.execute('COMMIT')
            except BaseException:
                con.execute('ROLLBACK');raise


def _disable(row):
    # A restored/partially removed bundle must be explicitly verified and re-enabled.
    from .storage import _atomic_json_write
    if row['_asset']:
        path=row['_root']/'receipt.json';value=_json(path,16384);value['enabled']=False;_atomic_json_write(path,value)
    if row['engine']=='mr-mt3' and row['origin'] in ('runtime-receipt','runtime-interpreter'):
        path=row['_root']/'mta-runtime.json'
        if path.is_file() and not path.is_symlink():
            value=_json(path,131072);value['tested']=False;_atomic_json_write(path,value)
    if row['engine']=='yourmt3':
        for name in ('mta-runtime.json','mta-runtime-ps.json'):
            path=row['_root']/name
            if path.is_file() and not path.is_symlink():
                value=_json(path,131072)
                if row['name'] in value.get('files',{}):value['tested']=False;_atomic_json_write(path,value)
    if row['engine']=='basic-pitch':
        from .studio_catalog import root
        path=root()/'basic-pitch.json'
        if path.is_file() and not path.is_symlink():
            value=_json(path,32768);value['enabled']=False;_atomic_json_write(path,value)


def remove(identifier):
    with mutation():
        row=find(identifier);path=_safe_path(row['_root'],row['name'],allow_hf_link=bool(_hf_source(row['name'])))
        if not path.exists():return {'removed':False}
        # Removing an alias never deletes shared blobs or another model's files.
        if 'blobs' in Path(row['name']).parts and not path.is_symlink():
            aliases=[r for r in records()[0] if r['_path'].is_symlink() and r['_path'].resolve()==path.resolve()]
            if aliases:raise ValueError(f'Shared blob is still referenced by {len(aliases)} model files; remove only the intended snapshot aliases first')
        _disable(row);size=path.lstat().st_size;path.unlink()
        return {'removed':True,'id':identifier,'unlinked_bytes':size,'shared_cache_blobs_retained':True,'model_requires_review':True}


def _source_spec(row):
    source=row['source']
    if not source:raise ValueError('No reviewed direct source: restore the exact manifest file or install a complete authorized bundle')
    if source.get('sha256') and source.get('bytes') is not None:return source
    # A local HF snapshot already fixes the repository and immutable revision.
    repo=source['repo_id'];revision=source['revision']
    from .secure_https import https_urlopen
    url=f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true'
    with https_urlopen(url,timeout=45) as response:
        raw=response.read(16*1024**2+1)
    if len(raw)>16*1024**2:raise ValueError('Oversized upstream model metadata')
    metadata=json.loads(raw)
    if metadata.get('sha')!=revision:raise ValueError('Upstream snapshot revision mismatch')
    match=next((entry for entry in metadata.get('siblings',[]) if entry.get('rfilename')==source['filename']),None)
    if not match:raise ValueError('File missing from original pinned snapshot')
    lfs=match.get('lfs') or {}
    sha=lfs.get('sha256');git=match.get('blobId');size=match.get('size',lfs.get('size'))
    if not isinstance(size,int) or not 0<=size<=32*1024**3 or not (sha or re.fullmatch('[a-f0-9]{40}',git or '')):
        raise ValueError('Original snapshot lacks a usable immutable file digest')
    return {**source,'bytes':size,'sha256':sha,'git_sha1':git if not sha else None}


def publish(row,temporary,expected,job_id=None):
    path=Path(temporary)
    if path.is_symlink() or not path.is_file():raise ValueError('Invalid model transfer')
    size=path.stat().st_size
    if expected.get('bytes') is not None and size!=expected['bytes']:raise ValueError('Model size mismatch')
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if expected.get('sha256') and digest!=expected['sha256']:raise ValueError('Model SHA-256 mismatch')
    if expected.get('git_sha1'):
        h=hashlib.sha1(f'blob {size}\0'.encode(),usedforsecurity=False)
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
        if h.hexdigest()!=expected['git_sha1']:raise ValueError('Original Git blob checksum mismatch')
    with mutation(job_id):
        current=find(row['id']);target=_safe_path(current['_root'],current['name'],allow_hf_link=bool(_hf_source(current['name'])))
        if current['_expected'] and current['_expected'].get('sha256') and digest!=current['_expected']['sha256']:
            raise ValueError('Installed manifest changed during transfer')
        target.parent.mkdir(parents=True,exist_ok=True)
        mode=current['_expected'].get('mode') if current['_expected'] else None
        if mode is None and target.exists() and not target.is_symlink():mode=target.stat().st_mode&0o777
        _disable(current)
        # Copy through a same-directory private file; no replacing through links.
        fd,name=tempfile.mkstemp(prefix='.model-transfer-',dir=target.parent)
        try:
            with os.fdopen(fd,'wb') as out,path.open('rb') as inp:
                for block in iter(lambda:inp.read(1024*1024),b''):out.write(block)
                out.flush();os.fsync(out.fileno())
            if mode is not None:os.chmod(name,mode)
            os.replace(name,target)
        finally:Path(name).unlink(missing_ok=True)
    return {'id':row['id'],'bytes':size,'sha256':digest,'downloaded':True,'enabled':False,'model_requires_review':True}


def download(identifier,cancelled=lambda:False,progress=lambda *a:None,job_id=None):
    row=find(identifier);source=_source_spec(row)
    from .secure_https import https_urlopen
    with tempfile.TemporaryDirectory(prefix='mta-model-download-') as folder:
        path=Path(folder)/'model';count=0
        with https_urlopen(source['url'],timeout=90) as response,path.open('xb') as out:
            while block:=response.read(1024*1024):
                if cancelled():raise RuntimeError('Model download cancelled')
                count+=len(block)
                if count>source['bytes']:raise ValueError('Model download exceeds pinned size')
                out.write(block);progress(count,source['bytes'])
        if cancelled():raise RuntimeError('Model download cancelled')
        return publish(row,path,source,job_id)


def recipes():
    """Existing fixed installers, surfaced together instead of hidden per editor."""
    from .ai_models import LYRICS_MODELS,CHORD_MODELS,lyrics_model_dir,_whisper_filename
    from .studio_catalog import root as studio_root
    from .vocal_banks import VOICES,status as voices
    rows=[]
    def add(identifier,engine,name,install,remove='',body=None,installed=None,note=''):
        rows.append({'id':identifier,'engine':engine,'name':name,'install_url':install,'delete_url':remove,
                     'body':body,'installed':installed,'note':note})
    for item in LYRICS_MODELS:
        identifier=item['id'];filename=_whisper_filename(identifier) or ('large-v3-turbo' if identifier=='turbo' else identifier)+'.pt'
        add('whisper-'+identifier,'whisper',item['display_name'],f'/api/ai-models/lyrics/{identifier}/download-jobs',
            f'/api/ai-models/lyrics/{identifier}',installed=bool(filename and (lyrics_model_dir()/filename).is_file()))
    for item in CHORD_MODELS:
        identifier=item['id']
        add('chords-'+identifier,'chords',item['display_name'],f'/api/ai-models/chords/{identifier}/download-jobs',f'/api/ai-models/chords/{identifier}')
    from .ai_backend_models import LEAD_BACKING_MODELS
    for item in LEAD_BACKING_MODELS:
        identifier=item['id']
        add('vocals-'+identifier,'vocals',item['display_name'],
            f'/api/vocal-separation/models/{identifier}/download' if identifier!='mvsep-mega53' else '',
            f'/api/vocal-separation/models/{identifier}',note='Operator-authorized external MSST checkpoint; use its configured files below.' if identifier=='mvsep-mega53' else '')
    add('drumsep','drumsep','DrumSep ONNX','/api/drumsep/models/download','/api/drumsep/models')
    add('basic-pitch','basic-pitch','Basic Pitch 0.4.0 ONNX runtime','/api/admin/ai/studio/models/basic-pitch/install',
        '/api/admin/ai/studio/models/basic-pitch',body={'accept_licenses':True},installed=(studio_root()/'basic-pitch.json').exists())
    add('gm-pack','gm','FluidR3 GM + notices','/api/admin/ai/studio/models/gm-pack/install',
        '/api/admin/ai/studio/models/gm-pack',body={'accept_licenses':True})
    installed={v['id']:v['installed'] for v in voices()}
    for voice,name in VOICES.items():
        add('voice-'+voice,'oddvoices',name,f'/api/admin/ai/studio/voicebanks/{voice}/install',
            f'/api/admin/ai/studio/voicebanks/{voice}',body={'accept_licenses':True},installed=installed.get(voice,False))
    from .studio_asset_registry import catalog
    for asset in catalog():
        add('bundle-'+asset['id'],asset['kind'],asset['name'],'',f"/api/admin/ai/model-assets/bundles/{asset['id']}",
            installed=asset['installed'],note='Complete managed bundle; files and missing members are listed below. Import a reviewed ZIP for a new model.')
    for row in rows:
        if row['engine'] in ('whisper','chords','vocals','drumsep'):
            row['delete_url']='/api/admin/ai/model-assets/recipes/'+row['id']
    return rows


def remove_recipe(identifier):
    recipe=next((row for row in recipes() if row['id']==identifier),None)
    if recipe is None or recipe['engine'] not in ('whisper','chords','vocals','drumsep'):
        raise ValueError('Unknown managed model removal recipe')
    with mutation():
        if recipe['engine']=='whisper':
            from .ai_models import delete_lyrics_model
            return delete_lyrics_model(identifier.removeprefix('whisper-'))
        if recipe['engine']=='chords':
            from .ai_models import delete_chord_model
            return delete_chord_model(identifier.removeprefix('chords-'))
        from . import main
        if recipe['engine']=='drumsep':
            path=_safe_path(main._DRUMSEP_PATH.parent,main._DRUMSEP_PATH.name)
        else:
            info=main._lead_backing_model_info(identifier.removeprefix('vocals-'))
            path=_safe_path(main.LEAD_BACKING_MODEL_DIR,info['filename'])
        existed=path.exists();path.unlink(missing_ok=True)
        return {'removed':existed,'model':identifier}


def remove_bundle(asset_id):
    from .studio_asset_registry import ID,root
    if not isinstance(asset_id,str) or not ID.fullmatch(asset_id):raise ValueError('Unknown managed bundle ID')
    with mutation():
        folder=root()/asset_id
        if folder.is_symlink() or not folder.is_dir() or not folder.resolve().is_relative_to(root().resolve()):
            raise ValueError('Managed bundle directory unavailable or unsafe')
        import shutil
        shutil.rmtree(folder)
    return {'id':asset_id,'removed':True}
