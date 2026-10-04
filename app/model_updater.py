from __future__ import annotations
import hashlib, json, logging, os, shutil, ssl, tempfile, threading, time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

LOG=logging.getLogger(__name__)
ROOT=Path(os.getenv("MTA_DEMUCS_MOBILE_MODEL_DIR","/data/projects/.models")).expanduser()
COREML_DIR=Path(os.getenv("MTA_DEMUCS_COREML_MODEL_DIR",str(ROOT/"coreml"))).expanduser()
ONNX_DIR=Path(os.getenv("MTA_DEMUCS_ONNX_MODEL_DIR",str(ROOT/"onnx"))).expanduser()
MANIFEST_URL=os.getenv("MTA_DEMUCS_MODEL_MANIFEST_URL","https://github.com/desalvo/mta-audio-editor/releases/download/demucs-models/manifest.json").strip()
INTERVAL=max(3600,int(os.getenv("MTA_DEMUCS_MODEL_UPDATE_INTERVAL_SECONDS","21600")))
ENABLED=os.getenv("MTA_DEMUCS_MODEL_AUTO_UPDATE","true").lower() in {"1","true","yes","on"}
MAX_BYTES=max(64*1024*1024,int(os.getenv("MTA_DEMUCS_MODEL_MAX_MB","1024"))*1024*1024)
TIMEOUT=max(5,int(os.getenv("MTA_DEMUCS_MODEL_UPDATE_TIMEOUT_SECONDS","120")))
_lock=threading.Lock(); _started=False

def _https(url:str)->bool:
    return urlparse(url).scheme.lower()=="https"

def _read_url(url:str)->bytes:
    if not _https(url): raise ValueError("Demucs model updates require HTTPS")
    req=Request(url,headers={"User-Agent":"MTA-Audio-Editor-model-updater/1"})
    with urlopen(req,timeout=TIMEOUT,context=ssl.create_default_context()) as r:
        size=int(r.headers.get("Content-Length") or 0)
        if size and size>MAX_BYTES: raise ValueError("model payload too large")
        data=r.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES: raise ValueError("model payload too large")
    return data

def _atomic_write(path:Path,data:bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent); os.close(fd)
    try:
        Path(tmp).write_bytes(data); os.replace(tmp,path)
    finally:
        Path(tmp).unlink(missing_ok=True)

def update_once()->dict:
    result={"updated":[],"unchanged":[],"errors":[]}
    if not ENABLED or not MANIFEST_URL:return result
    with _lock:
        try: manifest=json.loads(_read_url(MANIFEST_URL))
        except Exception as exc:
            result["errors"].append(str(exc)); LOG.warning("Demucs model manifest update failed: %s",exc); return result
        for platform,dest,ext in (("ios",COREML_DIR,".mlmodel"),("android",ONNX_DIR,".onnx")):
            entries=(manifest.get("models") or {}).get(platform) or {}
            for key,item in entries.items():
                try:
                    count=int(key); url=str(item["url"]); expected=str(item["sha256"]).lower()
                    if count not in {2,4,6,8} or len(expected)!=64: raise ValueError("invalid model manifest entry")
                    target=dest/f"demucs-{count}{ext}"
                    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==expected:
                        result["unchanged"].append(f"{platform}:{count}"); continue
                    data=_read_url(url); actual=hashlib.sha256(data).hexdigest()
                    if actual!=expected: raise ValueError(f"SHA-256 mismatch for {platform}:{count}")
                    _atomic_write(target,data)
                    meta={"version":str(item.get("version",manifest.get("version",""))),"sha256":actual,"source":url,"updated_at":int(time.time())}
                    _atomic_write(target.with_suffix(target.suffix+'.json'),json.dumps(meta,sort_keys=True).encode())
                    result["updated"].append(f"{platform}:{count}")
                except Exception as exc:
                    result["errors"].append(f"{platform}:{key}: {exc}"); LOG.warning("Demucs model update failed for %s:%s: %s",platform,key,exc)
    return result

def _loop():
    while True:
        update_once(); time.sleep(INTERVAL)

def start_background_updater():
    global _started
    if not ENABLED or _started:return
    _started=True
    threading.Thread(target=_loop,name="demucs-model-updater",daemon=True).start()
