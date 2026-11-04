from __future__ import annotations
from app.secure_https import https_urlopen

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse, urlsplit
import zipfile
from pathlib import Path
from typing import Iterable

from .models import Chord

BTC_DOWNLOAD_UNAVAILABLE = (
    "BTC-HCQT Beatles-FT was withdrawn; configure an authorized replacement checkpoint URL and SHA-256"
)
BTC_CODE_ARCHIVE = "https://github.com/marcusfkelley/btc-hcqt/archive/e25119e20fa265cb4c6023bf1e47c94f79a8feae.zip"
BTC_BODY_CODE_URL = "https://raw.githubusercontent.com/jayg996/BTC-ISMIR19/2682317be668032e6e4b269ded36adaa2ad57df0/"
BTC_BODY_FILES = (
    "LICENSE", "btc_model.py", "run_config.yaml", "utils/__init__.py",
    "utils/hparams.py", "utils/mir_eval_modules.py", "utils/transformer_modules.py",
)
BTC_CHECKPOINT = "btc_hcqt_beatlesft.pt"  # Historical on-disk name; provenance is recorded separately.
CHORDFORMER_ARCHIVE = "https://github.com/shojha24/ChordFormer-Artificial-Dataset-Benchmarking/archive/refs/heads/main.zip"

CHORDMINI_REVISION = "aa6e3a8d7b017f082fd2aaff9329d5c26af49c03"
CHORDMINI_REPO = "ptnghia-j/ChordMini"
CHORDMINI_ARCHIVE = f"https://github.com/{CHORDMINI_REPO}/archive/{CHORDMINI_REVISION}.zip"
CHORDMINI_CODE_URL = f"https://raw.githubusercontent.com/{CHORDMINI_REPO}/{CHORDMINI_REVISION}/"
CHORDMINI_CODE_FILES = (
    'LICENSE',
    'config/ChordMini.yaml',
    'src/evaluation/test.py',
    'src/evaluation/utils/__init__.py',
    'src/evaluation/utils/common.py',
    'src/evaluation/utils/inference.py',
    'src/evaluation/utils/quality_analysis.py',
    'src/models/__init__.py',
    'src/models/btc_model.py',
    'src/models/chord_net.py',
    'src/models/common/__init__.py',
    'src/models/common/base_transformer.py',
    'src/models/common/checkpoint_loading.py',
    'src/models/common/config.py',
    'src/models/common/temporal_smoothing.py',
    'src/models/common/transformer_modules.py',
    'src/utils/__init__.py',
    'src/utils/audio_io.py',
    'src/utils/checkpoint_utils.py',
    'src/utils/chords.py',
    'src/utils/cli.py',
    'src/utils/config_utils.py',
    'src/utils/dataloader.py',
    'src/utils/device.py',
    'src/utils/gradient_utils.py',
    'src/utils/hparams.py',
    'src/utils/logger.py',
    'src/utils/paths.py',
    'src/utils/random_utils.py',
)
CHORDMINI = {
    "chordmini-btc": ("BTC", "btc_model_best.pth", 35942692, "a691af56aec01fcd52d3bd46992f96bb9874ee59"),
    "chordmini-2e1d": ("ChordNet", "2e1d_model_best.pth", 27523646, "b61f6b3a02cc42b87afa38392f80d185a49f719a"),
}

MODEL_SPECS = {
    "btc-hcqt": {
        "id": "btc-hcqt",
        "display_name": "BTC-HCQT (authorized checkpoint)",
        "license": "MIT code; replacement weights require separate authorization",
        "quality": "high",
        "approx_bytes": 180_000_000,
        "archive": BTC_CODE_ARCHIVE,
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

for _variant, (_architecture, _weight, _size, _blob) in CHORDMINI.items():
    MODEL_SPECS[_variant] = {
        "id": _variant, "display_name": f"ChordMini ({_architecture})",
        "license": "MIT source code; checkpoint rights require operator review",
        "quality": "high", "approx_bytes": _size, "archive": CHORDMINI_ARCHIVE,
    }


def model_root() -> Path:
    data = Path(os.getenv("MTA_DATA_DIR", "/data/projects")).expanduser().resolve()
    return Path(os.getenv("MTA_CHORD_ML_MODEL_DIR", str(data / ".cache" / "chord-ml"))).expanduser().resolve()


def model_dir(model_id: str) -> Path:
    if not isinstance(model_id,str) or model_id not in MODEL_SPECS:raise ValueError("unsupported chord ML model")
    return model_root() / model_id


def installed(model_id: str) -> bool:
    root = model_dir(model_id)
    return (root / ".mta-installed.json").is_file() and _assets_present(root, model_id)


def _assets_present(root: Path, model_id: str) -> bool:
    if model_id == "btc-hcqt":
        required = ("hcqt_eval.py", BTC_CHECKPOINT, "BTC-ISMIR19/btc_model.py")
        return all((root / name).is_file() for name in required)
    if model_id in CHORDMINI:
        return all((root / name).is_file() for name in (
            "src/evaluation/test.py", "config/ChordMini.yaml", CHORDMINI[model_id][1]))
    checkpoints = (root / "cache_data").glob("*.sdict")
    return (root / "chord_recognition.py").is_file() and sum(p.is_file() for p in checkpoints) >= 5


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


def _download_file(url: str, destination: Path) -> None:
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


def btc_download_source() -> tuple[str, str] | None:
    url = os.getenv("MTA_BTC_HCQT_CHECKPOINT_URL", "").strip()
    digest = os.getenv("MTA_BTC_HCQT_CHECKPOINT_SHA256", "").strip().lower()
    if not url and not digest:
        return None
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or any(c.isspace() for c in url)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise ValueError("BTC-HCQT requires a credential-free HTTPS checkpoint URL and valid SHA-256")
    return url, digest


def authorize_btc_download() -> tuple[str, str]:
    from .model_license_policy import LicenseDenied, evaluate_model
    source = btc_download_source()
    if source is None:
        raise RuntimeError(BTC_DOWNLOAD_UNAVAILABLE)
    decision = evaluate_model("btc-hcqt")
    if urlsplit(decision.source).fragment != "sha256=" + source[1]:
        raise LicenseDenied("BTC-HCQT operator authorization must identify the configured checkpoint SHA-256")
    return source


def _download_archive(url: str, archive: Path, unpack: Path) -> None:
    _download_file(url, archive)
    with zipfile.ZipFile(archive) as zf:
        _safe_extract(zf, unpack)
    _flatten_single_directory(unpack)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _require_safe_btc_torch() -> None:
    from importlib.metadata import PackageNotFoundError, version
    try:
        match = re.match(r"^(\d+)\.(\d+)", version("torch"))
    except PackageNotFoundError:
        match = None
    if match is None or tuple(map(int, match.groups())) < (2, 6):
        raise RuntimeError("BTC-HCQT requires PyTorch 2.6 or newer for safe checkpoint loading")


def _stage_btc(folder: Path, temp: Path, source: tuple[str, str]) -> None:
    _require_safe_btc_torch()
    url, digest = source
    # Fetch only the files needed by HCQT. The original repository archive
    # includes separate pretrained BTC weights and an example recording.
    for name in BTC_BODY_FILES:
        target = folder / "BTC-ISMIR19" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _download_file(BTC_BODY_CODE_URL + name, target)
    checkpoint = folder / BTC_CHECKPOINT
    _download_file(url, checkpoint)
    if _sha256(checkpoint) != digest:
        raise RuntimeError("BTC-HCQT checkpoint SHA-256 mismatch")
    if not _assets_present(folder, "btc-hcqt"):
        raise RuntimeError("BTC-HCQT inference files are incomplete")
    # The pinned upstream CLI constructs the complete model and loads both the
    # BTC body and HCQT front-end state dicts. It must decode a local probe
    # before the installation becomes visible.
    import wave
    from .model_license_policy import guarded_model_call
    probe = temp / "probe.wav"
    with wave.open(str(probe), "wb") as pcm:
        pcm.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        pcm.writeframes(bytes(22050 * 4))
    output = temp / "probe-out"
    manifest = temp / "probe.json"
    _btc_manifest(probe, manifest)
    if authorize_btc_download() != source:
        raise RuntimeError("BTC-HCQT checkpoint authorization or source changed during installation")
    guarded_model_call("btc-hcqt", _run, _btc_command(manifest, output), cwd=folder,
                       timeout=120, env_overrides={"CUDA_VISIBLE_DEVICES": "", "HIP_VISIBLE_DEVICES": ""})
    result = json.loads((output / "results-btc.json").read_text())
    if not isinstance(result.get("mta"), dict) or not result["mta"].get("master"):
        raise RuntimeError("BTC-HCQT checkpoint failed the local inference probe")


def _download_chordmini(folder: Path, model_id: str) -> None:
    weight = "checkpoints/" + CHORDMINI[model_id][1]
    for name in (*CHORDMINI_CODE_FILES, weight):
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        _download_file(CHORDMINI_CODE_URL + name, target)


def _stage_chordmini(folder: Path, temp: Path, model_id: str) -> str:
    _require_safe_btc_torch()
    _, weight, size, expected_blob = CHORDMINI[model_id]
    checkpoint_dir = folder / "checkpoints"
    checkpoint = folder / weight
    (checkpoint_dir / weight).rename(checkpoint)
    shutil.rmtree(checkpoint_dir)
    if checkpoint.stat().st_size != size:
        raise RuntimeError("ChordMini checkpoint size mismatch")
    blob = hashlib.sha1(usedforsecurity=False)
    blob.update(f"blob {size}\0".encode())
    with checkpoint.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            blob.update(block)
    if blob.hexdigest() != expected_blob:
        raise RuntimeError("ChordMini checkpoint revision mismatch")
    loader = folder / "src/models/common/checkpoint_loading.py"
    code = loader.read_text()
    unsafe_load = "weights_only=False"
    strict_fallback = "    try:\n        model.load_state_dict(state_dict)\n"
    fallback_end = "\n    info(f\"Loaded"
    if code.count(unsafe_load) != 1 or code.count(strict_fallback) != 1 or code.count(fallback_end) != 1:
        raise RuntimeError("ChordMini upstream loader changed")
    start = code.index(strict_fallback)
    end = code.index(fallback_end, start)
    code = code[:start] + "    model.load_state_dict(state_dict, strict=True)\n" + code[end:]
    loader.write_text(code.replace(unsafe_load, "weights_only=True"))
    import math
    import struct
    import wave
    inputs = temp / "probe-input"
    inputs.mkdir()
    with wave.open(str(inputs / "probe.wav"), "wb") as pcm:
        pcm.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        pcm.writeframes(b"".join(struct.pack("<h", round(sum(
            2200 * math.sin(2 * math.pi * hz * index / 22050) for hz in (130.81, 164.81, 196)
        ))) for index in range(44100)))
    output = temp / "probe-output"
    _run_chordmini(folder, model_id, inputs, output, probe=True)
    if not (output / "probe.lab").stat().st_size:
        raise RuntimeError("ChordMini local inference probe produced no output")
    return _sha256(checkpoint)


def _run_chordmini(folder: Path, model_id: str, inputs: Path, output: Path, *, probe=False) -> None:
    from .model_license_policy import guarded_model_call
    architecture, weight, _, _ = CHORDMINI[model_id]
    command = [sys.executable, "-E", "-s", "src/evaluation/test.py", "--audio_dir", str(inputs),
               "--save_dir", str(output), "--config", str(folder / "config/ChordMini.yaml"),
               "--model_type", architecture, "--checkpoint", str(folder / weight),
               "--use_overlap", "--vote_aggregation", "logit", "--min_segment_duration", "0.10"]
    env = {"TORCH_FORCE_WEIGHTS_ONLY_LOAD": "1"}
    if probe:
        env.update({"CUDA_VISIBLE_DEVICES": "", "HIP_VISIBLE_DEVICES": ""})
    guarded_model_call(model_id, _run, command, cwd=folder, timeout=180 if probe else 1800, env_overrides=env)


def extract_chordmini(audio: Path, model_id: str) -> list[Chord]:
    from .model_license_policy import evaluate_model
    evaluate_model(model_id)
    _require_safe_btc_torch()
    folder = model_dir(model_id)
    if not engine_available(model_id):
        raise RuntimeError("ChordMini model/runtime not installed")
    receipt = json.loads((folder / ".mta-installed.json").read_text())
    if (receipt.get("source") != CHORDMINI_ARCHIVE or
            receipt.get("checkpoint_sha256") != _sha256(folder / CHORDMINI[model_id][1])):
        raise RuntimeError("ChordMini checkpoint integrity check failed")
    with tempfile.TemporaryDirectory(prefix="mta-chordmini-") as temp:
        inputs = Path(temp) / "audio"
        inputs.mkdir()
        shutil.copyfile(audio, inputs / ("input" + audio.suffix))
        output = Path(temp) / "out"
        _run_chordmini(folder, model_id, inputs, output)
        result = output / "input.lab"
        if not result.is_file() or result.stat().st_size == 0:
            raise RuntimeError("ChordMini returned no chord timeline")
        return _lab_to_events(result)


def download_model(model_id: str) -> dict:
    from .model_license_policy import evaluate_model
    from .ai_project_lock import project_publication_lock
    target = model_dir(model_id)
    source = authorize_btc_download() if model_id == 'btc-hcqt' else None
    with project_publication_lock('studio-model:chord-' + model_id):
        evaluate_model(model_id)
        if target.exists() or target.is_symlink():
            raise ValueError('Remove the existing chord model before a new installation')
        spec = MODEL_SPECS[model_id]
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.chord-install-', dir=target.parent) as raw:
            td = Path(raw)
            unpack = td / 'unpack'
            checkpoint_sha256 = None
            if model_id in CHORDMINI:
                _download_chordmini(unpack, model_id)
                checkpoint_sha256 = _stage_chordmini(unpack, td, model_id)
            else:
                _download_archive(str(spec['archive']), td / 'model.zip', unpack)
            if source is not None:
                _stage_btc(unpack, td, source)
                if authorize_btc_download() != source:
                    raise RuntimeError('BTC-HCQT checkpoint authorization or source changed during installation')
            elif not _assets_present(unpack, model_id):
                raise RuntimeError('ChordFormer inference script or five-fold checkpoints missing from downloaded archive')
            evaluate_model(model_id)
            marker = {key: spec[key] for key in ('id', 'display_name', 'license')} | {'source': spec['archive']}
            if source is not None or checkpoint_sha256 is not None:
                marker['checkpoint_sha256'] = source[1] if source else checkpoint_sha256
            (unpack / '.mta-installed.json').write_text(json.dumps(marker, indent=2) + '\n', encoding='utf-8')
            os.replace(unpack, target)
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


def _display_chord(label: str) -> str:
    root, separator, quality = label.partition(":")
    if not separator:
        return label
    quality, slash, bass = quality.partition("/")
    if quality == "maj":
        quality = ""
    elif quality.startswith("min"):
        quality = "m" + quality[3:]
    return root + quality + slash + bass


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
        label = _display_chord(label)
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
                candidates = value.get("master") or value.get("chords") or value.get("events") or value.get("predictions") or []
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
        label = _display_chord(label)
        events.append(Chord(time_ms=ms, chord=label))
        last = label
    return events


def _run(command: list[str], *, cwd: Path, timeout: int = 1800, env_overrides=None) -> None:
    from .ai_execution_policy import isolated_env
    env = isolated_env()
    if env_overrides:
        env.update(env_overrides)
    if "hcqt_eval.py" in command or (env_overrides or {}).get("TORCH_FORCE_WEIGHTS_ONLY_LOAD") == "1":
        env["TORCH_FORCE_WEIGHTS_ONLY_LOAD"] = "1"
        env.pop("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", None)
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603
    if proc.returncode:
        tail = (proc.stderr or proc.stdout or "").strip()[-4000:]
        raise RuntimeError(f"Chord ML engine failed ({proc.returncode}): {tail}")


def _btc_manifest(audio: Path, manifest: Path) -> None:
    # The upstream CLI strips the file:// prefix without URL decoding.
    uri = "file://" + audio.resolve().as_posix()
    manifest.write_text(json.dumps({"tracks": [{"id": "mta", "title": "MTA", "audioUrl": uri}]}), encoding="utf-8")


def _btc_command(manifest: Path, output: Path) -> list[str]:
    return [sys.executable, "-E", "-s", "hcqt_eval.py", BTC_CHECKPOINT, str(manifest), str(output)]


def extract_btc_hcqt(audio: Path) -> list[Chord]:
    from .model_license_policy import evaluate_model,guarded_model_call
    decision = evaluate_model('btc-hcqt')
    root = model_dir("btc-hcqt")
    if not engine_available("btc-hcqt"):
        raise RuntimeError("BTC-HCQT model/runtime not installed")
    metadata = json.loads((root / ".mta-installed.json").read_text())
    expected = metadata.get("checkpoint_sha256")
    if expected is not None:
        _require_safe_btc_torch()
        if (not isinstance(expected, str) or urlsplit(decision.source).fragment != "sha256=" + expected
                or _sha256(root / BTC_CHECKPOINT) != expected):
            raise RuntimeError("BTC-HCQT checkpoint SHA-256 mismatch or authorization changed")
    with tempfile.TemporaryDirectory(prefix="mta-btc-") as raw:
        td = Path(raw)
        manifest = td / "manifest.json"
        _btc_manifest(audio, manifest)
        out = td / "out"
        out.mkdir()
        guarded_model_call('btc-hcqt',_run,_btc_command(manifest, out), cwd=root)
        if expected is not None and urlsplit(evaluate_model('btc-hcqt').source).fragment != "sha256=" + expected:
            raise RuntimeError("BTC-HCQT checkpoint authorization changed during inference")
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
