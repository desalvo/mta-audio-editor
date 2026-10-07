from __future__ import annotations

import gc
import importlib.util
import json
import logging
import os
from pathlib import Path
from urllib.parse import urlparse


LOGGER = logging.getLogger(__name__)


LYRICS_MODELS = [
    {"id": "tiny", "display_name": "Whisper tiny", "quality": "fast", "approx_bytes": 75_000_000},
    {"id": "base", "display_name": "Whisper base", "quality": "fast", "approx_bytes": 145_000_000},
    {"id": "small", "display_name": "Whisper small", "quality": "balanced", "approx_bytes": 465_000_000},
    {"id": "medium", "display_name": "Whisper medium", "quality": "high", "approx_bytes": 1_500_000_000},
    {"id": "large-v2", "display_name": "Whisper large-v2", "quality": "very-high", "approx_bytes": 3_000_000_000},
    {"id": "large-v3", "display_name": "Whisper large-v3", "quality": "recommended", "approx_bytes": 3_000_000_000, "recommended": True},
    {"id": "turbo", "display_name": "Whisper turbo", "quality": "fast-high", "approx_bytes": 1_700_000_000},
]
LYRICS_DEFAULT_MODEL = os.getenv("MTA_LYRICS_WHISPER_MODEL", "turbo").strip() or "turbo"

CHORD_MODELS = [
    {
        "id": "madmom-deep-chroma-crf",
        "display_name": "Madmom Deep Chroma + CRF",
        "engine": "madmom-deep-chroma",
        "quality": "recommended",
        "recommended": True,
        "license": "CC BY-NC-SA 4.0 (checkpoint weights; non-commercial)",
    },
    {
        "id": "madmom-cnn-crf",
        "display_name": "Madmom CNN + CRF",
        "engine": "madmom-cnn-crf",
        "quality": "high",
        "license": "CC BY-NC-SA 4.0 (checkpoint weights; non-commercial)",
    },
    {"id": "btc-hcqt", "display_name": "BTC-HCQT (Beatles-FT)", "engine": "btc-hcqt", "quality": "high", "license": "MIT (code + published weights)"},
    {"id": "chordformer", "display_name": "ChordFormer 5-fold ensemble", "engine": "chordformer", "quality": "very-high", "license": "Research implementation; upstream checkpoints downloaded on demand"},
]
CHORD_ENGINES = [
    {"id": "profile-stable", "display_name": "Songbook / Stable · Madmom CRF / Chordino · fewer changes", "model_id": None, "ai": True, "profile": "stable", "recommended": True},
    {"id": "profile-fast", "display_name": "Fast · Chordino/Chromagram + harmonic refinement", "model_id": None, "ai": False, "profile": "fast"},
    {"id": "profile-accurate", "display_name": "Accurate · ChordFormer/BTC + harmonic refinement", "model_id": None, "ai": True, "profile": "accurate"},
    {"id": "profile-maximum", "display_name": "Maximum accuracy · Ensemble multi-engine", "model_id": None, "ai": True, "profile": "maximum"},
    {"id": "chordformer", "display_name": "ChordFormer 5-fold ensemble", "model_id": "chordformer", "ai": True},
    {"id": "btc-hcqt", "display_name": "BTC-HCQT (Beatles-FT)", "model_id": "btc-hcqt", "ai": True},
    {"id": "madmom-deep-chroma", "display_name": "Madmom Deep Chroma + CRF", "model_id": "madmom-deep-chroma-crf", "ai": True},
    {"id": "madmom-cnn-crf", "display_name": "Madmom CNN + CRF", "model_id": "madmom-cnn-crf", "ai": True},
    {"id": "chordino", "display_name": "Chordino / NNLS-Chroma", "model_id": None, "ai": False},
    {"id": "mta-chromagram", "display_name": "MTA Chromagram", "model_id": None, "ai": False},
]
CHORD_DEFAULT_ENGINE = os.getenv("MTA_CHORDS_ENGINE", "madmom-deep-chroma").strip() or "madmom-deep-chroma"

CHORD_PIPELINE_PRESETS = [
    {"id":"default-complete","display_name":"Default / Completa","description":"Default MTA: sensibilità 45, tutti gli stadi armonici e di stabilizzazione attivi tranne la quantizzazione ai beat.","sensitivity":45,"harmonic_refinement":True,"detect_sevenths":True,"detect_sus":True,"detect_dim_aug":True,"detect_slash_bass":True,"temporal_smoothing":True,"beat_sync":False,"min_chord_ms":1100,"max_changes_per_minute":36},
    {"id":"stable","display_name":"Songbook / Stabile","description":"Pochi cambi, accordi leggibili; privilegia major/minor e stabilità temporale.","sensitivity":25,"harmonic_refinement":False,"detect_sevenths":False,"detect_sus":False,"detect_dim_aug":False,"detect_slash_bass":False,"temporal_smoothing":True,"beat_sync":False,"min_chord_ms":1800,"max_changes_per_minute":24},
    {"id":"balanced","display_name":"Bilanciato","description":"Buon compromesso tra dettaglio armonico e numero di cambi.","sensitivity":45,"harmonic_refinement":True,"detect_sevenths":True,"detect_sus":True,"detect_dim_aug":False,"detect_slash_bass":False,"temporal_smoothing":True,"beat_sync":False,"min_chord_ms":1100,"max_changes_per_minute":36},
    {"id":"detailed","display_name":"Dettagliato","description":"Più cambi e qualità armoniche; adatto a revisione manuale successiva.","sensitivity":70,"harmonic_refinement":True,"detect_sevenths":True,"detect_sus":True,"detect_dim_aug":True,"detect_slash_bass":True,"temporal_smoothing":True,"beat_sync":False,"min_chord_ms":550,"max_changes_per_minute":60},
    {"id":"raw","display_name":"Solo recognizer / Raw","description":"Nessun refinement MTA e nessun filtro di densità; restituisce il recognizer quasi direttamente.","sensitivity":100,"harmonic_refinement":False,"detect_sevenths":True,"detect_sus":True,"detect_dim_aug":True,"detect_slash_bass":True,"temporal_smoothing":False,"beat_sync":False,"min_chord_ms":0,"max_changes_per_minute":0},
]
CHORD_PIPELINE_STAGES = [
    {"id":"harmonic_refinement","display_name":"Refinement chroma armonica"},
    {"id":"detect_sevenths","display_name":"Riconosci 7 / maj7 / m7"},
    {"id":"detect_sus","display_name":"Riconosci sus2 / sus4"},
    {"id":"detect_dim_aug","display_name":"Riconosci dim / aug"},
    {"id":"detect_slash_bass","display_name":"Inversioni / slash bass"},
    {"id":"temporal_smoothing","display_name":"Stabilizzazione temporale"},
    {"id":"beat_sync","display_name":"Quantizza i cambi ai beat del progetto"},
]


def _data_root() -> Path:
    return Path(os.getenv("MTA_DATA_DIR", "/data/projects")).expanduser().resolve()


def lyrics_model_dir() -> Path:
    return Path(os.getenv("MTA_LYRICS_MODEL_DIR", str(_data_root() / ".cache" / "lyrics-models"))).expanduser().resolve()


def _whisper_filename(model_id: str) -> str | None:
    try:
        import whisper  # type: ignore
        url = getattr(whisper, "_MODELS", {}).get(model_id)
        return Path(urlparse(url).path).name if url else None
    except Exception:
        return None


def lyrics_catalog(*, native: bool = False) -> dict:
    directory = lyrics_model_dir()
    items=[]
    for raw in LYRICS_MODELS:
        item=dict(raw)
        filename=_whisper_filename(item["id"])
        item["filename"]=filename
        item["installed"]=bool(filename and (directory/filename).is_file())
        item["engine"]="OpenAI Whisper"
        item["license"]="MIT code; model weights downloaded from the upstream Whisper model source"
        items.append(item)
    default=LYRICS_DEFAULT_MODEL if any(x["id"]==LYRICS_DEFAULT_MODEL for x in LYRICS_MODELS) else "base"
    return {"engine":"OpenAI Whisper","default_model":default,"models":items,"storage":"local" if native else "server","on_demand":True,"model_dir":str(directory)}


def download_lyrics_model(model_id: str, *, native: bool = False) -> dict:
    if not any(x["id"]==model_id for x in LYRICS_MODELS):
        raise ValueError("unsupported lyrics model")
    if not importlib.util.find_spec("whisper"):
        raise RuntimeError("OpenAI Whisper is not installed in this runtime")
    import whisper  # type: ignore
    directory=lyrics_model_dir();directory.mkdir(parents=True,exist_ok=True)
    model=whisper.load_model(model_id, download_root=str(directory))
    del model;gc.collect()
    return next(x for x in lyrics_catalog(native=native)["models"] if x["id"]==model_id)


def delete_lyrics_model(model_id: str, *, native: bool = False) -> dict:
    if not any(x["id"]==model_id for x in LYRICS_MODELS):
        raise ValueError("unsupported lyrics model")
    filename=_whisper_filename(model_id)
    removed=False
    if filename:
        p=lyrics_model_dir()/filename
        if p.is_file(): p.unlink(); removed=True
    return {"ok":True,"model_id":model_id,"removed":removed,"storage":"local" if native else "server"}


def _chord_cache_root() -> Path:
    # madmom-infer caches below $XDG_CACHE_HOME/madmom_infer/models.
    xdg=Path(os.getenv("XDG_CACHE_HOME", str(_data_root()/".cache"))).expanduser().resolve()
    return xdg/"madmom_infer"/"models"


def _chord_marker_dir() -> Path:
    p=_data_root()/".cache"/"mta-model-manager"/"chords";p.mkdir(parents=True,exist_ok=True);return p


def _chord_marker(model_id: str) -> Path:
    return _chord_marker_dir()/f"{model_id}.installed.json"


def chord_engine_available(engine_id: str) -> bool:
    if engine_id in {"profile-stable", "profile-fast", "profile-accurate", "profile-maximum"}:
        return True
    if engine_id in {"btc-hcqt", "chordformer"}:
        from .chord_ml import engine_available
        return engine_available(engine_id)
    if engine_id in {"madmom-deep-chroma", "madmom-cnn-crf"}:
        # Check the actual lazily-imported modules, not only the top-level package.
        # This keeps frozen/native builds from advertising an engine whose PyInstaller
        # bundle is missing the chord recogniser modules.
        return bool(
            importlib.util.find_spec("madmom_infer")
            and importlib.util.find_spec("madmom_infer.features.chords")
            and importlib.util.find_spec("madmom_infer.audio.chroma")
        )
    if engine_id == "chordino":
        from .chordino_runtime import chordino_status
        return bool(chordino_status()["available"])
    return engine_id == "mta-chromagram"


def chords_catalog(*, native: bool = False) -> dict:
    models=[]
    for raw in CHORD_MODELS:
        item=dict(raw)
        if item["id"] in {"btc-hcqt", "chordformer"}:
            from .chord_ml import installed
            item["installed"] = installed(item["id"])
        else:
            item["installed"]=_chord_marker(item["id"]).is_file()
        models.append(item)
    engines=[]
    for raw in CHORD_ENGINES:
        item=dict(raw);item["available"]=chord_engine_available(item["id"])
        if item["id"] == "chordino":
            from .chordino_runtime import chordino_status
            item["runtime"] = chordino_status()
        engines.append(item)
    default=CHORD_DEFAULT_ENGINE if any(x["id"]==CHORD_DEFAULT_ENGINE for x in CHORD_ENGINES) else "madmom-deep-chroma"
    return {"default_engine":default,"engines":engines,"models":models,"presets":CHORD_PIPELINE_PRESETS,"pipeline_stages":CHORD_PIPELINE_STAGES,"storage":"local" if native else "server","on_demand":True,"model_dir":str(_chord_cache_root())}


def _cache_snapshot() -> set[str]:
    root=_chord_cache_root()
    if not root.exists(): return set()
    return {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}


def download_chord_model(model_id: str, *, native: bool = False) -> dict:
    spec=next((x for x in CHORD_MODELS if x["id"]==model_id),None)
    if not spec: raise ValueError("unsupported chord model")
    if model_id in {"btc-hcqt", "chordformer"}:
        from .chord_ml import download_model
        download_model(model_id)
        return next(x for x in chords_catalog(native=native)["models"] if x["id"]==model_id)
    if not importlib.util.find_spec("madmom_infer"):
        raise RuntimeError("madmom-infer is not installed in this runtime")
    before=_cache_snapshot()
    if spec["engine"]=="madmom-deep-chroma":
        from madmom_infer.audio.chroma import DeepChromaProcessor  # type: ignore
        from madmom_infer.features.chords import DeepChromaChordRecognitionProcessor  # type: ignore
        a=DeepChromaProcessor();b=DeepChromaChordRecognitionProcessor();del a,b
    else:
        from madmom_infer.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor  # type: ignore
        a=CNNChordFeatureProcessor();b=CRFChordRecognitionProcessor();del a,b
    gc.collect()
    after=_cache_snapshot();files=sorted(after-before)
    # If weights were already cached before MTA started tracking them, keep a marker
    # without claiming ownership of those files for deletion.
    _chord_marker(model_id).write_text(json.dumps({"id":model_id,"engine":spec["engine"],"files":files},indent=2)+"\n",encoding="utf-8")
    return next(x for x in chords_catalog(native=native)["models"] if x["id"]==model_id)


def delete_chord_model(model_id: str, *, native: bool = False) -> dict:
    spec=next((x for x in CHORD_MODELS if x["id"]==model_id),None)
    if not spec: raise ValueError("unsupported chord model")
    if model_id in {"btc-hcqt", "chordformer"}:
        from .chord_ml import delete_model
        removed = delete_model(model_id)
        return {"ok": True, "model_id": model_id, "removed": [model_id] if removed else [], "storage": "local" if native else "server"}
    marker=_chord_marker(model_id);removed=[]
    if marker.is_file():
        try: meta=json.loads(marker.read_text(encoding='utf-8'))
        except Exception: meta={}
        root=_chord_cache_root()
        for name in meta.get('files',[]):
            p=(root/name).resolve()
            try: p.relative_to(root.resolve())
            except ValueError: continue
            if p.is_file(): p.unlink();removed.append(name)
        marker.unlink(missing_ok=True)
    return {"ok":True,"model_id":model_id,"removed":removed,"storage":"local" if native else "server"}



def _accelerator_info() -> dict:
    forced=os.getenv("MTA_AI_DEVICE","").strip()
    if forced:
        return {"device":forced,"hardware_accelerated":forced.lower()!="cpu","source":"MTA_AI_DEVICE"}
    try:
        import torch  # type: ignore
        if torch.cuda.is_available():
            name="CUDA"
            try:
                name = f"CUDA · {torch.cuda.get_device_name(0)}"
            except Exception as exc:
                LOGGER.debug("Unable to read CUDA device name: %s", exc)
            return {"device":name,"hardware_accelerated":True,"source":"torch"}
        mps=getattr(getattr(torch,"backends",None),"mps",None)
        if mps is not None and mps.is_available():
            return {"device":"Apple Metal / MPS","hardware_accelerated":True,"source":"torch"}
    except Exception as exc:
        LOGGER.debug("Unable to probe Torch AI accelerators: %s", exc)
    return {"device":"CPU","hardware_accelerated":False,"source":"fallback"}

def ai_catalog(*, native: bool = False) -> dict:
    return {"storage":"local" if native else "server","lyrics":lyrics_catalog(native=native),"chords":chords_catalog(native=native),"accelerator":_accelerator_info()}
