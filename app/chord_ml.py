from __future__ import annotations

import importlib.util
import json
import os
import shutil
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
    return model_root() / model_id


def installed(model_id: str) -> bool:
    return (model_dir(model_id) / ".mta-installed.json").is_file()


def _safe_extract(zf: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in zf.infolist():
        target = (destination / member.filename).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("unsafe model archive path") from exc
    zf.extractall(destination)


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
    with urllib.request.urlopen(req, timeout=180) as response, destination.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(response, out)


def download_model(model_id: str) -> dict:
    spec = MODEL_SPECS.get(model_id)
    if not spec:
        raise ValueError("unsupported chord ML model")
    root = model_dir(model_id)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"mta-{model_id}-") as raw:
        td = Path(raw)
        archive = td / "model.zip"
        _download_zip(str(spec["archive"]), archive)
        unpack = td / "unpack"
        unpack.mkdir()
        with zipfile.ZipFile(archive) as zf:
            _safe_extract(zf, unpack)
        _flatten_single_directory(unpack)
        if root.exists():
            shutil.rmtree(root)
        shutil.copytree(unpack, root)
    if model_id == "btc-hcqt":
        body_zip = root / "btc-body.zip"
        _download_zip(BTC_BODY_ARCHIVE, body_zip)
        body_unpack = root / "BTC-ISMIR19"
        body_tmp = root / ".btc-body"
        body_tmp.mkdir(exist_ok=True)
        with zipfile.ZipFile(body_zip) as zf:
            _safe_extract(zf, body_tmp)
        _flatten_single_directory(body_tmp)
        if body_unpack.exists():
            shutil.rmtree(body_unpack)
        body_tmp.rename(body_unpack)
        body_zip.unlink(missing_ok=True)
        if not (root / "btc_hcqt_beatlesft.pt").is_file():
            raise RuntimeError("BTC-HCQT checkpoint missing from downloaded archive")
    else:
        checkpoints = list((root / "cache_data").glob("*.sdict")) if (root / "cache_data").is_dir() else []
        if len(checkpoints) < 5:
            raise RuntimeError("ChordFormer five-fold checkpoints missing from downloaded archive")
    marker = {
        "id": model_id,
        "display_name": spec["display_name"],
        "source": spec["archive"],
        "license": spec["license"],
    }
    (root / ".mta-installed.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    return marker


def delete_model(model_id: str) -> bool:
    root = model_dir(model_id)
    if not root.exists():
        return False
    shutil.rmtree(root)
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
    root = model_dir("btc-hcqt")
    if not engine_available("btc-hcqt"):
        raise RuntimeError("BTC-HCQT model/runtime not installed")
    with tempfile.TemporaryDirectory(prefix="mta-btc-") as raw:
        td = Path(raw)
        manifest = td / "manifest.json"
        manifest.write_text(json.dumps({"tracks": [{"id": "mta", "title": "MTA", "audioUrl": audio.resolve().as_uri()}]}), encoding="utf-8")
        out = td / "out"
        out.mkdir()
        _run([sys.executable, "hcqt_eval.py", "btc_hcqt_beatlesft.pt", str(manifest), str(out)], cwd=root)
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
    root = model_dir("chordformer")
    if not engine_available("chordformer"):
        raise RuntimeError("ChordFormer model/runtime not installed")
    with tempfile.TemporaryDirectory(prefix="mta-chordformer-") as raw:
        output = Path(raw) / "chords.lab"
        # 'extended' enables the broad structural vocabulary included by the
        # upstream repository (root/triad/bass/7th/9th/11th/13th heads).
        _run([sys.executable, "chord_recognition.py", str(audio.resolve()), str(output), "extended"], cwd=root)
        events = _lab_to_events(output)
        if events:
            return events
    raise RuntimeError("ChordFormer returned no chord events")
