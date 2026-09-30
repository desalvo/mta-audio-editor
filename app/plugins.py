"""Safe audio-processing and stem-separation plugin registry.

Insert plugins are translated to a fixed allow-list of FFmpeg filters. User input
never becomes an arbitrary filter expression or shell command.
"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from .models import InsertPlugin

PRESETS: dict[str, dict[str, str]] = {
    "eq": {
        "default": "equalizer=f=1000:t=q:w=1:g=0",
        "flat": "equalizer=f=1000:t=q:w=1:g=0",
        "drums-punchy": "equalizer=f=80:t=q:w=1:g=2,equalizer=f=350:t=q:w=1.2:g=-2,equalizer=f=4500:t=q:w=1:g=2",
        "bass-warm": "equalizer=f=90:t=q:w=0.8:g=3,equalizer=f=320:t=q:w=1.2:g=-2,equalizer=f=2500:t=q:w=1:g=1",
        "vocals-presence": "highpass=f=80,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1:g=2.5,equalizer=f=8500:t=q:w=1:g=1",
        "guitar-clarity": "highpass=f=70,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=2200:t=q:w=1:g=2",
        "piano-natural": "highpass=f=45,equalizer=f=300:t=q:w=1:g=-1,equalizer=f=3500:t=q:w=1:g=1.5",
        "master-gentle": "highpass=f=25,equalizer=f=250:t=q:w=1:g=-0.5,equalizer=f=9000:t=q:w=0.7:g=0.8",
    },
    "normalizer": {
        "default": "loudnorm=I=-14:LRA=11:TP=-1",
        "streaming-14": "loudnorm=I=-14:LRA=11:TP=-1",
        "broadcast-23": "loudnorm=I=-23:LRA=7:TP=-2",
        "music-12": "loudnorm=I=-12:LRA=9:TP=-1",
        "gentle-16": "loudnorm=I=-16:LRA=11:TP=-1.5",
    },
    "compressor": {
        "default": "acompressor=threshold=0.125:ratio=3:attack=20:release=250:makeup=1.25",
        "moderate": "acompressor=threshold=0.125:ratio=3:attack=20:release=250:makeup=1.25",
        "vocal": "acompressor=threshold=0.1:ratio=3.5:attack=8:release=180:makeup=1.4",
        "drums": "acompressor=threshold=0.16:ratio=4:attack=5:release=120:makeup=1.25",
        "bass": "acompressor=threshold=0.14:ratio=4:attack=12:release=220:makeup=1.3",
        "master-glue": "acompressor=threshold=0.18:ratio=2:attack=30:release=300:makeup=1.1",
    },
    "limiter": {
        "default": "alimiter=limit=0.891:attack=5:release=50:level=disabled",
        "brickwall-1": "alimiter=limit=0.891:attack=5:release=50:level=disabled",
        "brickwall-0.3": "alimiter=limit=0.966:attack=5:release=50:level=disabled",
        "safe-2": "alimiter=limit=0.794:attack=8:release=80:level=disabled",
    },
}


def plugin_catalog() -> dict[str, list[str]]:
    return {kind: list(presets) for kind, presets in PRESETS.items()}


def plugin_filter(plugin: InsertPlugin) -> str | None:
    if not plugin.enabled:
        return None
    presets = PRESETS.get(plugin.plugin)
    if not presets:
        raise ValueError(f"unsupported plugin: {plugin.plugin}")
    expr = presets.get(plugin.preset)
    if expr is None:
        raise ValueError(f"unsupported preset {plugin.preset!r} for {plugin.plugin}")
    return expr


def chain_filter(inserts: list[InsertPlugin]) -> str:
    parts = [expr for item in inserts if (expr := plugin_filter(item))]
    return ",".join(parts)


class DemucsStemSplitter:
    name = "demucs"
    display_name = "Demucs stem separation"

    @staticmethod
    def available() -> bool:
        return shutil.which("demucs") is not None or importlib.util.find_spec("demucs") is not None

    @classmethod
    def status(cls) -> dict[str, object]:
        return {
            "name": cls.name,
            "display_name": cls.display_name,
            "available": cls.available(),
            "models": ["htdemucs", "htdemucs_ft", "htdemucs_6s"],
            "recommended_model": "htdemucs_6s",
        }

    @classmethod
    def split(cls, source: Path, output_dir: Path, model: str = "htdemucs_6s") -> list[Path]:
        if model not in {"htdemucs", "htdemucs_ft", "htdemucs_6s"}:
            raise ValueError("unsupported Demucs model")
        if not cls.available():
            raise RuntimeError("Demucs stem plugin is not installed in this runtime")
        output_dir.mkdir(parents=True, exist_ok=True)
        if shutil.which("demucs"):
            cmd = ["demucs", "-n", model, "--out", str(output_dir), str(source)]
        else:
            cmd = [sys.executable, "-m", "demucs.separate", "-n", model, "--out", str(output_dir), str(source)]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip()[-3000:] or "stem separation failed")
        # Demucs emits <out>/<model>/<basename>/*.wav.
        candidates = sorted(output_dir.glob(f"{model}/**/*.wav"))
        if not candidates:
            candidates = sorted(output_dir.rglob("*.wav"))
        if not candidates:
            raise RuntimeError("stem separator produced no WAV files")
        return candidates


STEM_SPLITTER = DemucsStemSplitter
