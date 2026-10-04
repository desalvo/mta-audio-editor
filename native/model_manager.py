from __future__ import annotations
import hashlib,json,logging,os,ssl,tempfile,zipfile
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request,urlopen

LOG=logging.getLogger(__name__)

def _data_root_path()->Path:
    from native.mta_audio_editor_native import _data_root
    return _data_root()

def _root()->Path:
    p=_data_root_path()/"demucs-models";p.mkdir(parents=True,exist_ok=True);return p

def local_repo()->Path:
    p=_root()/"repo";p.mkdir(parents=True,exist_ok=True);return p

def _server_url():return os.getenv("MTA_MODEL_SERVER_URL","https://mta-audio-editor.apps.desalvo.eu").rstrip('/')+'/'
def _headers()->dict[str,str]:
    headers=_headers()
    token=os.getenv('MTA_MODEL_ACCESS_TOKEN','').strip()
    if token:headers['Authorization']='Bearer '+token
    return headers
def _fetch_json(path:str):
    url=urljoin(_server_url(),path.lstrip('/'))
    if not url.lower().startswith('https://'):
        raise ValueError('model server URL must use HTTPS')
    req=Request(url,headers=_headers())  # noqa: S310 -- URL validated above.
    with urlopen(req,timeout=30,context=ssl.create_default_context()) as r:  # noqa: S310 -- validated HTTPS request.
        return json.loads(r.read())
def catalog():return _fetch_json('/api/models/catalog?platform=native')
def list_local():
    items=[]
    for marker in _root().glob('*.installed.json'):
        try:items.append(json.loads(marker.read_text(encoding='utf-8')))
        except Exception as exc:
            LOG.debug("Ignoring unreadable local model marker %s: %s", marker, exc)
    return items

def _safe_id(v:str)->str:
    import re
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}',v):raise ValueError('invalid model id')
    return v

def delete(model_id:str):
    mid=_safe_id(model_id);removed=[]
    marker=_root()/(mid+'.installed.json')
    try:meta=json.loads(marker.read_text(encoding='utf-8')) if marker.is_file() else {}
    except Exception:meta={}
    for name in meta.get('files',[]):
        p=local_repo()/str(name)
        if p.is_file():p.unlink();removed.append(p.name)
    marker.unlink(missing_ok=True)
    return {'ok':True,'removed':removed}

def update(model_id:str):
    mid=_safe_id(model_id);cat=catalog();item=next((x for x in cat.get('models',[]) if x.get('id')==mid),None)
    if not item:raise RuntimeError('model not available on server')
    url=urljoin(_server_url(),str(item.get('download_url') or f'/api/models/native/{mid}').lstrip('/'))
    if not url.lower().startswith('https://'):
        raise ValueError('model download URL must use HTTPS')
    req=Request(url,headers=_headers())  # noqa: S310 -- URL validated above.
    with urlopen(req,timeout=300,context=ssl.create_default_context()) as r:  # noqa: S310 -- validated HTTPS request.
        data=r.read()
    digest=hashlib.sha256(data).hexdigest()
    expected=str(item.get('sha256') or '')
    if expected and len(expected)==64 and expected.lower()!=digest:raise RuntimeError('SHA-256 mismatch')
    fd,tmp=tempfile.mkstemp(suffix='.zip');os.close(fd);Path(tmp).write_bytes(data)
    files=[]
    try:
        with zipfile.ZipFile(tmp) as z:
            for info in z.infolist():
                name=Path(info.filename).name
                if not name or Path(name).suffix not in {'.th','.yaml'}:continue
                target=local_repo()/name
                target.write_bytes(z.read(info));files.append(name)
    finally:Path(tmp).unlink(missing_ok=True)
    if not files:raise RuntimeError('empty/invalid native model bundle')
    marker=_root()/(mid+'.installed.json');marker.write_text(json.dumps({'id':mid,'model':item.get('model',mid),'display_name':item.get('display_name',mid),'stem_count':item.get('stem_count',0),'sha256':digest,'files':files},indent=2)+'\n',encoding='utf-8')
    return {'ok':True,'model_id':mid,'files':files,'sha256':digest}

def ensure(model_id:str):
    mid=_safe_id(model_id)
    marker=_root()/(mid+'.installed.json')
    if marker.is_file():return {'ok':True,'already':True}
    return update(mid)
