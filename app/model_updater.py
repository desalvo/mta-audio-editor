from __future__ import annotations
import hashlib, json, logging, os, re, ssl, tempfile, threading, time, zipfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOG=logging.getLogger(__name__)
ROOT=Path(os.getenv("MTA_DEMUCS_MOBILE_MODEL_DIR","/data/projects/.models")).expanduser()
COREML_DIR=Path(os.getenv("MTA_DEMUCS_COREML_MODEL_DIR",str(ROOT/"coreml"))).expanduser()
ONNX_DIR=Path(os.getenv("MTA_DEMUCS_ONNX_MODEL_DIR",str(ROOT/"onnx"))).expanduser()
SERVER_DIR=Path(os.getenv("MTA_DEMUCS_SERVER_MODEL_DIR",str(ROOT/"server"))).expanduser()
BLACKLIST_FILE=Path(os.getenv("MTA_DEMUCS_MODEL_BLACKLIST_FILE",str(ROOT/"blacklist.json"))).expanduser()
CATALOG_FILE=Path(os.getenv("MTA_DEMUCS_MODEL_CATALOG_FILE",str(ROOT/"catalog.json"))).expanduser()
MANIFEST_URL=os.getenv("MTA_DEMUCS_MODEL_MANIFEST_URL","https://github.com/desalvo/mta-audio-editor/releases/download/demucs-models/manifest.json").strip()
INTERVAL=max(3600,int(os.getenv("MTA_DEMUCS_MODEL_UPDATE_INTERVAL_SECONDS","21600")))
ENABLED=os.getenv("MTA_DEMUCS_MODEL_AUTO_UPDATE","true").lower() in {"1","true","yes","on"}
MAX_BYTES=max(64*1024*1024,int(os.getenv("MTA_DEMUCS_MODEL_MAX_MB","2048"))*1024*1024)
TIMEOUT=max(5,int(os.getenv("MTA_DEMUCS_MODEL_UPDATE_TIMEOUT_SECONDS","180")))
_lock=threading.Lock(); _started=False

OFFICIAL_DEMUCS_MODELS={
 "htdemucs":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "htdemucs_ft":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "htdemucs_6s":{"stem_count":6,"stem_labels":["drums","bass","other","vocals","guitar","piano"]},
 "hdemucs_mmi":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx_extra":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx_q":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx_extra_q":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "repro_mdx_a":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "repro_mdx_a_hybrid_only":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "repro_mdx_a_time_only":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
}

def _https(url:str)->bool:return urlparse(url).scheme.lower()=="https"
def _read_url(url:str)->bytes:
    if not _https(url): raise ValueError("Demucs model updates require HTTPS")
    req=Request(url,headers={"User-Agent":"MTA-Audio-Editor-model-updater/2"})  # noqa: S310 -- URL is validated as HTTPS above.
    with urlopen(req,timeout=TIMEOUT,context=ssl.create_default_context()) as r:  # noqa: S310 -- validated HTTPS request.
        size=int(r.headers.get("Content-Length") or 0)
        if size and size>MAX_BYTES: raise ValueError("model payload too large")
        data=r.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise ValueError("model payload too large")
    return data

def _atomic_write(path:Path,data:bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent); os.close(fd)
    try: Path(tmp).write_bytes(data); os.replace(tmp,path)
    finally: Path(tmp).unlink(missing_ok=True)

def _safe_id(value:str)->str:
    value=re.sub(r"[^A-Za-z0-9._-]+","-",str(value).strip()).strip("-.")
    if not value: raise ValueError("invalid model id")
    return value[:128]

def load_blacklist()->set[str]:
    try:
        raw=json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
        items=raw.get("models",[]) if isinstance(raw,dict) else raw
        return {_safe_id(x) for x in items if str(x).strip()}
    except (OSError,ValueError,TypeError): return set()

def save_blacklist(items:set[str]):
    _atomic_write(BLACKLIST_FILE,(json.dumps({"models":sorted(items)},indent=2)+"\n").encode())

def is_blacklisted(model_id:str)->bool:
    try:return _safe_id(model_id) in load_blacklist()
    except ValueError:return True

def _metadata_files():
    for d in (COREML_DIR,ONNX_DIR,SERVER_DIR):
        if d.is_dir(): yield from d.glob("*.json")

def delete_model_artifacts(model_id:str)->list[str]:
    mid=_safe_id(model_id); removed=[]
    for meta in list(_metadata_files()):
        try:data=json.loads(meta.read_text(encoding="utf-8"))
        except Exception as exc:
            LOG.debug("Ignoring unreadable model metadata %s: %s", meta, exc)
            continue
        if str(data.get("id") or data.get("model") or "")!=mid:continue
        artifact=meta.with_suffix("") if meta.name.endswith('.json') else None
        # Metadata normally sits beside artifact as <artifact>.json.
        artifact=Path(str(meta)[:-5])
        for p in (artifact,meta):
            if p.exists(): p.unlink(missing_ok=True); removed.append(str(p))
    bundle=SERVER_DIR/"bundles"/f"{mid}.zip"
    if bundle.exists():bundle.unlink();removed.append(str(bundle))
    Path(str(bundle)+'.json').unlink(missing_ok=True)
    yaml_path,sigs=_demucs_signatures(mid)
    checkpoint_dir=SERVER_DIR/"torch-hub"/"checkpoints"
    for sig in sigs:
        for p in checkpoint_dir.glob(f"{sig}-*.th") if checkpoint_dir.is_dir() else []:
            p.unlink(missing_ok=True);removed.append(str(p))
    # Legacy artifacts whose id is encoded by filename.
    for d,ext in ((COREML_DIR,'.mlmodel'),(ONNX_DIR,'.onnx')):
        for p in (d/f"{mid}{ext}",):
            if p.exists():p.unlink();removed.append(str(p))
            Path(str(p)+'.json').unlink(missing_ok=True)
    return removed

def blacklist_model(model_id:str)->dict:
    mid=_safe_id(model_id); items=load_blacklist();items.add(mid);save_blacklist(items)
    return {"model_id":mid,"blacklisted":True,"removed":delete_model_artifacts(mid)}

def unblacklist_model(model_id:str)->dict:
    mid=_safe_id(model_id);items=load_blacklist();items.discard(mid);save_blacklist(items)
    return {"model_id":mid,"blacklisted":False}

def _normalize_manifest(manifest:dict)->list[dict]:
    out=[]
    # v2 list format: {models:[{id,platform,url,sha256,...}]}
    raw=manifest.get("models",[])
    if isinstance(raw,list):
        source=raw
    else:
        # backward-compatible platform maps keyed by stem count.
        source=[]
        if isinstance(raw,dict):
            for platform,items in raw.items():
                if not isinstance(items,dict):continue
                for key,item in items.items():
                    if not isinstance(item,dict):continue
                    obj=dict(item);obj.setdefault("platform",platform);obj.setdefault("stem_count",key);obj.setdefault("id",obj.get("model") or f"demucs-{key}");obj["_legacy_key"]=str(key);source.append(obj)
    for item in source:
        if not isinstance(item,dict):continue
        try:
            mid=_safe_id(item.get("id") or item.get("model") or '')
            platform=str(item.get("platform") or item.get("format") or 'server').lower()
            count=int(item.get("stem_count",0) or 0)
            if count and (count < 2 or count > 64):continue
            obj={"id":mid,"model":str(item.get("model") or mid),"platform":platform,"stem_count":count,"stem_labels":item.get("stem_labels",[]) if isinstance(item.get("stem_labels",[]),list) else [],"display_name":str(item.get("display_name") or mid),"engine":str(item.get("engine") or 'demucs'),"version":str(item.get("version") or manifest.get("version") or ''),"url":str(item.get("url") or ''),"sha256":str(item.get("sha256") or '').lower(),"_legacy_key":str(item.get("_legacy_key") or "")}
            out.append(obj)
        except (ValueError,TypeError):continue
    return out

def _target_for(item:dict)->Path|None:
    platform=item['platform'];mid=_safe_id(item['id'])
    if platform in {'ios','coreml'}:return COREML_DIR/f"{mid}.mlmodel"
    if platform in {'android','onnx'}:return ONNX_DIR/f"{mid}.onnx"
    if platform in {'native','desktop'}:
        suffix=Path(urlparse(item.get('url','')).path).suffix or '.bin';return SERVER_DIR/f"{mid}{suffix}"
    return None

def _install_item(item:dict,result:dict,force=False):
    mid=item['id']; target=_target_for(item)
    if target is None or not item.get('url') or len(item.get('sha256',''))!=64:return
    expected=item['sha256']; key=f"{item['platform']}:{item.get('_legacy_key') or mid}"
    if not force and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==expected:
        result['unchanged'].append(key);return
    data=_read_url(item['url']);actual=hashlib.sha256(data).hexdigest()
    if actual!=expected:raise ValueError(f"SHA-256 mismatch for {key}")
    _atomic_write(target,data)
    meta=dict(item);meta.update({"sha256":actual,"updated_at":int(time.time()),"filename":target.name})
    _atomic_write(Path(str(target)+'.json'),json.dumps(meta,sort_keys=True).encode())
    result['updated'].append(key)

def _registry_server_profiles()->list[dict]:
    profiles=[{"id":k,"model":k,"engine":"demucs",**v} for k,v in OFFICIAL_DEMUCS_MODELS.items()]
    raw=os.getenv('MTA_DEMUCS_MODEL_REGISTRY','').strip(); f=os.getenv('MTA_DEMUCS_MODEL_REGISTRY_FILE','').strip()
    if f:
        try:raw=Path(f).read_text(encoding='utf-8')
        except OSError as exc:
            LOG.warning("Unable to read Demucs model registry file %s: %s", f, exc)
    if raw:
        try:
            parsed=json.loads(raw);items=parsed.get('models',[]) if isinstance(parsed,dict) else parsed
            for x in items if isinstance(items,list) else []:
                if isinstance(x,dict) and str(x.get('engine','demucs'))=='demucs':profiles.append(dict(x))
        except Exception as exc:
            LOG.warning("Unable to parse Demucs model registry: %s", exc)
    return profiles

def _demucs_signatures(model_name:str)->tuple[Path|None,list[str]]:
    try:
        import demucs.pretrained as pretrained
        yaml_path=Path(pretrained.REMOTE_ROOT)/f"{model_name}.yaml"
        if not yaml_path.is_file(): return None,[]
        import yaml
        raw=yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        return yaml_path,[str(x) for x in raw.get("models",[]) if str(x)]
    except Exception:return None,[]

def _server_bundle(model_name:str)->Path|None:
    yaml_path,sigs=_demucs_signatures(model_name)
    if not yaml_path or not sigs:return None
    checkpoint_dir=SERVER_DIR/"torch-hub"/"checkpoints"
    files=[]
    for sig in sigs:
        match=next(iter(checkpoint_dir.glob(f"{sig}-*.th")),None) if checkpoint_dir.is_dir() else None
        if match is None:return None
        files.append(match)
    bundle_dir=SERVER_DIR/"bundles";bundle_dir.mkdir(parents=True,exist_ok=True)
    target=bundle_dir/f"{_safe_id(model_name)}.zip"
    fd,tmp=tempfile.mkstemp(prefix=target.name+'.',dir=bundle_dir);os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            z.write(yaml_path,yaml_path.name)
            for f in files:z.write(f,f.name)
        os.replace(tmp,target)
    finally:Path(tmp).unlink(missing_ok=True)
    meta={"id":_safe_id(model_name),"model":model_name,"platform":"native","filename":target.name,"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"size":target.stat().st_size,"updated_at":int(time.time())}
    _atomic_write(Path(str(target)+'.json'),json.dumps(meta,sort_keys=True).encode())
    return target

def native_bundle(model_id:str)->Path|None:
    if is_blacklisted(model_id):return None
    p=SERVER_DIR/"bundles"/f"{_safe_id(model_id)}.zip"
    return p if p.is_file() else None

def _load_server_model(model_name:str):
    """Load/download one Demucs model into the managed torch hub cache.

    Kept behind a helper so the lightweight quality-test environment does not
    need the large Demucs/PyTorch stem dependencies installed. Production
    containers/native builds still call the real implementation.
    """
    import torch
    torch.hub.set_dir(str(SERVER_DIR/'torch-hub'))
    from demucs.pretrained import get_model
    return get_model(model_name)


def _prefetch_server_models(result:dict,only:set[str]|None=None):
    if os.getenv('MTA_DEMUCS_SERVER_PREFETCH','true').lower() not in {'1','true','yes','on'}:return
    blacklist=load_blacklist();SERVER_DIR.mkdir(parents=True,exist_ok=True)
    # Demucs itself owns the weight files; the marker makes inventory/blacklist explicit.
    for p in _registry_server_profiles():
        mid=_safe_id(p.get('id') or p.get('model') or '')
        if mid in blacklist or (only is not None and mid not in only):continue
        marker=SERVER_DIR/f"{mid}.server.json"
        try:
            model_name=str(p.get('model') or mid)
            _load_server_model(model_name)
            _server_bundle(model_name)
            meta={"id":mid,"model":model_name,"platform":"server","engine":"demucs","stem_count":int(p.get('stem_count',0) or 0),"stem_labels":p.get('stem_labels',[]),"display_name":str(p.get('display_name') or mid),"updated_at":int(time.time()),"managed_cache":True}
            _atomic_write(marker,json.dumps(meta,sort_keys=True).encode());result['server_ready'].append(mid)
        except Exception as exc:
            result['errors'].append(f"server:{mid}: {exc}");LOG.warning("Demucs prefetch failed for %s: %s",mid,exc)

def cached_catalog()->list[dict]:
    try:
        raw=json.loads(CATALOG_FILE.read_text(encoding='utf-8'));return raw.get('models',[]) if isinstance(raw,dict) else []
    except Exception:return []

def update_once(model_ids:set[str]|None=None,force=False,prefetch_server=False)->dict:
    if not ENABLED and not prefetch_server:
        return {"updated":[],"unchanged":[],"errors":[]}
    result={"updated":[],"unchanged":[],"server_ready":[],"skipped_blacklist":[],"errors":[]}
    with _lock:
        blacklist=load_blacklist();entries=[]
        if ENABLED and MANIFEST_URL:
            try:
                manifest=json.loads(_read_url(MANIFEST_URL));entries=_normalize_manifest(manifest)
                _atomic_write(CATALOG_FILE,(json.dumps({"version":manifest.get('version',''),"models":entries,"updated_at":int(time.time())},indent=2)+"\n").encode())
            except Exception as exc:
                result['errors'].append(str(exc));LOG.warning("Demucs manifest update failed: %s",exc);entries=cached_catalog()
        for item in entries:
            mid=item['id']
            if model_ids is not None and mid not in model_ids:continue
            if mid in blacklist:
                result['skipped_blacklist'].append(mid);delete_model_artifacts(mid);continue
            try:_install_item(item,result,force=force)
            except Exception as exc:result['errors'].append(f"{item.get('platform')}:{mid}: {exc}");LOG.warning("Demucs model update failed for %s: %s",mid,exc)
        if prefetch_server:
            _prefetch_server_models(result,model_ids)
    return result

def public_catalog(platform:str|None=None)->dict:
    blacklist=load_blacklist();items=[]
    for item in cached_catalog():
        mid=str(item.get("id") or "")
        if not mid or mid in blacklist:continue
        p=str(item.get("platform") or "").lower()
        if platform and p not in {platform.lower(), {"ios":"coreml","android":"onnx"}.get(platform.lower(),platform.lower())}:continue
        target=_target_for(item)
        obj=dict(item);obj["installed_on_server"]=bool(target and target.is_file());obj["size"]=target.stat().st_size if target and target.is_file() else 0
        if p in {"ios","coreml"}:obj["download_url"]=f"/api/models/coreml/{mid}"
        elif p in {"android","onnx"}:obj["download_url"]=f"/api/models/onnx/{mid}"
        elif p in {"native","desktop"}:obj["download_url"]=f"/api/models/native/{mid}"
        items.append(obj)
    if platform in {None,"native","desktop","server"}:
        for p in _registry_server_profiles():
            mid=_safe_id(p.get('id') or p.get('model') or '')
            if mid in blacklist:continue
            bundle=native_bundle(mid)
            items.append({"id":mid,"model":str(p.get('model') or mid),"platform":"native","engine":"demucs","stem_count":int(p.get('stem_count',0) or 0),"stem_labels":p.get('stem_labels',[]),"display_name":str(p.get('display_name') or mid),"version":"official-demucs","installed_on_server":bundle is not None,"size":bundle.stat().st_size if bundle else 0,"download_url":f"/api/models/native/{mid}"})
    # Deduplicate platform/id pairs, keeping manifest entries over synthesized native entries.
    dedup={}
    for item in items:dedup[(str(item.get('platform')),str(item.get('id')))]=item
    return {"models":list(dedup.values()),"blacklist":sorted(blacklist),"updated_at":int(time.time())}

def server_inventory()->dict:
    blacklist=load_blacklist(); entries=cached_catalog(); models=[]
    for item in entries:
        obj=dict(item);obj['blacklisted']=obj['id'] in blacklist;target=_target_for(obj);obj['installed']=bool(target and target.is_file());obj['size']=target.stat().st_size if target and target.is_file() else 0;models.append(obj)
    for p in _registry_server_profiles():
        mid=_safe_id(p.get('id') or p.get('model') or '')
        if any(x.get('id')==mid and x.get('platform')=='server' for x in models):continue
        marker=SERVER_DIR/f"{mid}.server.json"
        models.append({"id":mid,"model":str(p.get('model') or mid),"platform":"server","engine":"demucs","stem_count":int(p.get('stem_count',0) or 0),"stem_labels":p.get('stem_labels',[]),"display_name":str(p.get('display_name') or mid),"version":"bundled-registry","installed":marker.is_file(),"size":0,"blacklisted":mid in blacklist})
    return {"models":models,"blacklist":sorted(blacklist),"auto_update":ENABLED,"interval_seconds":INTERVAL,"manifest_url":MANIFEST_URL}

def _loop():
    while True:update_once(prefetch_server=True);time.sleep(INTERVAL)
def start_background_updater():
    global _started
    if not ENABLED or _started:return
    _started=True;threading.Thread(target=_loop,name='demucs-model-updater',daemon=True).start()
