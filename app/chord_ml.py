from __future__ import annotations
from app.secure_https import https_urlopen

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse
import zipfile
from pathlib import Path
from typing import Iterable

from .models import Chord

BTC_ARCHIVE = "https://github.com/marcusfkelley/btc-hcqt/archive/refs/heads/main.zip"
BTC_BODY_ARCHIVE = "https://github.com/jayg996/BTC-ISMIR19/archive/refs/heads/master.zip"
CHORDFORMER_ARCHIVE = "https://github.com/shojha24/ChordFormer-Artificial-Dataset-Benchmarking/archive/refs/heads/main.zip"

MODEL_SPECS = {
    "btc-hcqt": {
        "id": "btc-hcqt",
        "display_name": "BTC-HCQT (Beatles-FT)",
        "license": "MIT (code + published checkpoint)",
        "quality": "high",
        "approx_bytes": 180_000_000,
        "archive": BTC_ARCHIVE,
    },
    "chordformer": {
        "id": "chordformer",
        "display_name": "ChordFormer 5-fold ensemble",
        "license": "Research implementation derived from MIT upstream; checkpoints distributed by upstream repository",
        "quality": "very-high",
        "approx_bytes": 650_000_000,
        "archive": CHORDFORMER_ARCHIVE,
    },
}


def model_root() -> Path:
    data = Path(os.getenv("MTA_DATA_DIR", "/data/projects")).expanduser().resolve()
    return Path(os.getenv("MTA_CHORD_ML_MODEL_DIR", str(data / ".cache" / "chord-ml"))).expanduser().resolve()


def model_dir(model_id: str) -> Path:
    if not isinstance(model_id,str) or model_id not in MODEL_SPECS:raise ValueError("unsupported chord ML model")
    return model_root() / model_id


def installed(model_id: str) -> bool:
    return (model_dir(model_id) / ".mta-installed.json").is_file()


MAX_DOWNLOAD_BYTES=2*1024**3
MAX_EXPANDED_BYTES=4*1024**3
MAX_ARCHIVE_MEMBERS=20000


def _safe_extract(zf: zipfile.ZipFile, destination: Path) -> None:
    """Preflight the complete cross-platform inventory, then stream privately."""
    entries=zf.infolist();seen={};total=0
    if len(entries)>MAX_ARCHIVE_MEMBERS:raise RuntimeError('too many model archive members')
    for item in entries:
        name=item.filename.rstrip('/') if item.is_dir() else item.filename
        parts=name.split('/')
        if (not name or len(name)>1024 or '\\' in name or ':' in name or '\x00' in name
                or any(p in ('','.','..') or p.endswith((' ','.')) or
                    p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))} for p in parts)):
            raise RuntimeError('unsafe model archive path')
        folded=name.casefold();mode=stat.S_IFMT(item.external_attr>>16)
        if (folded in seen or item.flag_bits&1 or mode not in (0,stat.S_IFREG,stat.S_IFDIR)
                or (mode==stat.S_IFDIR and not item.is_dir()) or (mode==stat.S_IFREG and item.is_dir())):
            raise RuntimeError('duplicate, encrypted or special model archive member')
        seen[folded]=item.is_dir();total+=item.file_size
        if item.file_size>MAX_DOWNLOAD_BYTES or total>MAX_EXPANDED_BYTES or item.file_size<0:
            raise RuntimeError('expanded model archive exceeds size limit')
    for name in seen:
        if any(seen.get('/'.join(name.split('/')[:i])) is False for i in range(1,len(name.split('/')))):
            raise RuntimeError('conflicting model archive member paths')
    if destination.is_symlink() or (destination.exists() and (not destination.is_dir() or any(destination.iterdir()))):
        raise RuntimeError('model extraction requires a fresh private directory')
    destination.mkdir(parents=True,exist_ok=True)
    for item in entries:
        target=destination/item.filename
        if item.is_dir():target.mkdir(parents=True,exist_ok=True);continue
        target.parent.mkdir(parents=True,exist_ok=True)
        with zf.open(item) as source,target.open('xb') as output:
            copied=0
            while block:=source.read(1024*1024):
                copied+=len(block)
                if copied>item.file_size:raise RuntimeError('model member exceeds declared size')
                output.write(block)
            if copied!=item.file_size:raise RuntimeError('truncated model archive member')


def _flatten_single_directory(destination: Path) -> None:
    items = [p for p in destination.iterdir() if p.name != ".mta-installed.json"]
    if len(items) != 1 or not items[0].is_dir():
        return
    wrapper = items[0]
    tmp = destination.parent / f".{destination.name}-flatten"
    tmp.mkdir(parents=True, exist_ok=True)
    for child in wrapper.iterdir():
        shutil.move(str(child), str(tmp / child.name))
    shutil.rmtree(wrapper)
    for child in tmp.iterdir():
        shutil.move(str(child), str(destination / child.name))
    tmp.rmdir()


def _download_zip(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("model downloads require an HTTPS URL")
    req = urllib.request.Request(url, headers={"User-Agent": "MTA-Audio-Editor/0.2"})  # noqa: S310
    created=False
    try:
        with https_urlopen(req, timeout=180) as response, destination.open("xb") as out:
            created=True
            total=0
            while block:=response.read(1024*1024):
                total+=len(block)
                if total>MAX_DOWNLOAD_BYTES:raise RuntimeError('model download exceeds size limit')
                out.write(block)
    except BaseException:
        if created:destination.unlink(missing_ok=True)
        raise


def download_model(model_id: str) -> dict:
    from .model_license_policy import evaluate_model
    from .ai_project_lock import project_publication_lock
    target=model_dir(model_id)
    with project_publication_lock('studio-model:chord-'+model_id):
        evaluate_model(model_id)
        if target.exists() or target.is_symlink():raise ValueError('Remove the existing chord model before a new installation')
        spec=MODEL_SPECS[model_id];target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.chord-install-',dir=target.parent) as raw:
            td=Path(raw);archive=td/'model.zip';unpack=td/'unpack'
            _download_zip(str(spec['archive']),archive)
            with zipfile.ZipFile(archive) as zf:_safe_extract(zf,unpack)
            _flatten_single_directory(unpack)
            if model_id=='btc-hcqt':
                body_zip=td/'btc-body.zip';body_tmp=td/'body'
                _download_zip(BTC_BODY_ARCHIVE,body_zip)
                with zipfile.ZipFile(body_zip) as zf:_safe_extract(zf,body_tmp)
                _flatten_single_directory(body_tmp)
                if (unpack/'BTC-ISMIR19').exists():raise RuntimeError('Conflicting BTC body destination')
                body_tmp.rename(unpack/'BTC-ISMIR19')
                if not (unpack/'btc_hcqt_beatlesft.pt').is_file():raise RuntimeError('BTC-HCQT checkpoint missing from downloaded archive')
            else:
                checkpoints=list((unpack/'cache_data').glob('*.sdict'))
                if len(checkpoints)<5:raise RuntimeError('ChordFormer five-fold checkpoints missing from downloaded archive')
            # Recheck admission before publishing downloaded code and weights.
            evaluate_model(model_id)
            marker={key:spec[key] for key in ('id','display_name','license')}|{'source':spec['archive']}
            (unpack/'.mta-installed.json').write_text(json.dumps(marker,indent=2)+'\n',encoding='utf-8')
            os.replace(unpack,target)
        return marker


def delete_model(model_id: str) -> bool:
    from .ai_project_lock import project_publication_lock
    target=model_dir(model_id)
    with project_publication_lock('studio-model:chord-'+model_id):
        if target.is_symlink():raise ValueError('Unsafe chord model directory')
        if not target.exists():return False
        shutil.rmtree(target)
    return True


def runtime_available() -> bool:
    return bool(importlib.util.find_spec("torch") and importlib.util.find_spec("librosa"))


def engine_available(engine: str) -> bool:
    return runtime_available() and installed(engine)


def _lab_to_events(path: Path) -> list[Chord]:
    events: list[Chord] = []
    last = None
    if not path.is_file():
        return events
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        try:
            start = float(parts[0])
        except ValueError:
            continue
        label = parts[-1].strip()
        if not label or label.upper() in {"N", "X"} or label == last:
            continue
        # Harte -> MTA display syntax for the common forms. The r192 harmonic
        # refinement normalises/extends this further after the recogniser pass.
        label = label.replace(":maj", "").replace(":min", "m")
        events.append(Chord(time_ms=max(0, round(start * 1000)), chord=label))
        last = label
    return events


def _json_to_events(path: Path) -> list[Chord]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    # btc-hcqt benchmark output is intentionally parsed permissively so minor
    # upstream schema changes do not require an MTA release.
    candidates: Iterable = data.get("chords") or data.get("events") or data.get("predictions") or [] if isinstance(data, dict) else data
    if isinstance(data, dict) and not candidates:
        for value in data.values():
            if isinstance(value, dict):
                candidates = value.get("chords") or value.get("events") or value.get("predictions") or []
                if candidates:
                    break
            elif isinstance(value, list):
                candidates = value
                break
    events: list[Chord] = []
    last = None
    for item in candidates or []:
        if isinstance(item, dict):
            start = item.get("start", item.get("time", item.get("start_sec", 0)))
            label = item.get("chord", item.get("label", item.get("name", "N")))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            start, label = item[0], item[-1]
        else:
            continue
        try:
            ms = max(0, round(float(start) * 1000))
        except (TypeError, ValueError):
            continue
        label = str(label).strip()
        if not label or label.upper() in {"N", "X"} or label == last:
            continue
        label = label.replace(":maj", "").replace(":min", "m")
        events.append(Chord(time_ms=ms, chord=label))
        last = label
    return events


def _run(command: list[str], *, cwd: Path, timeout: int = 1800) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603
    if proc.returncode:
        tail = (proc.stderr or proc.stdout or "").strip()[-4000:]
        raise RuntimeError(f"Chord ML engine failed ({proc.returncode}): {tail}")


def extract_btc_hcqt(audio: Path) -> list[Chord]:
    from .model_license_policy import evaluate_model,guarded_model_call
    evaluate_model('btc-hcqt')
    root = model_dir("btc-hcqt")
    if not engine_available("btc-hcqt"):
        raise RuntimeError("BTC-HCQT model/runtime not installed")
    with tempfile.TemporaryDirectory(prefix="mta-btc-") as raw:
        td = Path(raw)
        manifest = td / "manifest.json"
        manifest.write_text(json.dumps({"tracks": [{"id": "mta", "title": "MTA", "audioUrl": audio.resolve().as_uri()}]}), encoding="utf-8")
        out = td / "out"
        out.mkdir()
        guarded_model_call('btc-hcqt',_run,[sys.executable, "hcqt_eval.py", "btc_hcqt_beatlesft.pt", str(manifest), str(out)], cwd=root)
        json_files = sorted(out.rglob("*.json"))
        for candidate in json_files:
            events = _json_to_events(candidate)
            if events:
                return events
        lab_files = sorted(out.rglob("*.lab"))
        for candidate in lab_files:
            events = _lab_to_events(candidate)
            if events:
                return events
    raise RuntimeError("BTC-HCQT returned no chord events")


def extract_chordformer(audio: Path) -> list[Chord]:
    from .model_license_policy import evaluate_model,guarded_model_call
    evaluate_model('chordformer')
    root = model_dir("chordformer")
    if not engine_available("chordformer"):
        raise RuntimeError("ChordFormer model/runtime not installed")
    with tempfile.TemporaryDirectory(prefix="mta-chordformer-") as raw:
        output = Path(raw) / "chords.lab"
        # 'extended' enables the broad structural vocabulary included by the
        # upstream repository (root/triad/bass/7th/9th/11th/13th heads).
        guarded_model_call('chordformer',_run,[sys.executable, "chord_recognition.py", str(audio.resolve()), str(output), "extended"], cwd=root)
        events = _lab_to_events(output)
        if events:
            return events
    raise RuntimeError("ChordFormer returned no chord events")
