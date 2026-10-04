"""Safe audio-processing and stem-separation plugin registry.

All processing is translated server-side to allow-listed FFmpeg filters. Factory
presets are immutable; user presets store validated parameter dictionaries only.
No user-supplied FFmpeg expression or shell command is accepted.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import re
import queue
import threading
import sys
from copy import deepcopy
from pathlib import Path

from .models import InsertPlugin

BANDS_32 = [20, 25, 31, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
            800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000,
            12500, 16000, 20000, 22000]

LEGACY_EQ_PRESETS: dict[str, str] = {
        "default": "equalizer=f=1000:t=q:w=1:g=0",
        "flat": "equalizer=f=1000:t=q:w=1:g=0",
        "drums-punchy": "equalizer=f=80:t=q:w=1:g=2,equalizer=f=350:t=q:w=1.2:g=-2,equalizer=f=4500:t=q:w=1:g=2",
        "bass-warm": "equalizer=f=90:t=q:w=0.8:g=3,equalizer=f=320:t=q:w=1.2:g=-2,equalizer=f=2500:t=q:w=1:g=1",
        "vocals-presence": "highpass=f=80,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=3200:t=q:w=1:g=2.5,equalizer=f=8500:t=q:w=1:g=1",
        "guitar-clarity": "highpass=f=70,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=2200:t=q:w=1:g=2",
        "piano-natural": "highpass=f=45,equalizer=f=300:t=q:w=1:g=-1,equalizer=f=3500:t=q:w=1:g=1.5",
        "master-gentle": "highpass=f=25,equalizer=f=250:t=q:w=1:g=-0.5,equalizer=f=9000:t=q:w=0.7:g=0.8",
}

PRESETS: dict[str, dict[str, str]] = {
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
    "delay": {
        "default": "aecho=0.8:0.5:180:0.22",
        "slapback": "aecho=0.85:0.55:95:0.24",
        "vocal-quarter": "aecho=0.82:0.55:320:0.20",
        "stereo-space": "aecho=0.82:0.48:140|210:0.20|0.14",
        "long-echo": "aecho=0.78:0.50:480|760:0.20|0.12",
    },
    "reverb_lexicon": {
        "default": "aecho=0.82:0.72:38|67|103|149:0.22|0.16|0.11|0.07,highpass=f=70,lowpass=f=12500",
        "lexicon-vocal-plate": "aecho=0.84:0.72:45|83|127|191:0.24|0.17|0.11|0.07,highpass=f=110,lowpass=f=11000",
        "lexicon-large-hall": "aecho=0.80:0.70:75|121|189|277:0.24|0.18|0.13|0.09,highpass=f=55,lowpass=f=12000",
        "lexicon-small-hall": "aecho=0.84:0.66:42|69|105:0.20|0.14|0.09,highpass=f=80,lowpass=f=13000",
        "lexicon-ambient": "aecho=0.78:0.74:110|177|269|401:0.21|0.16|0.11|0.07,highpass=f=90,lowpass=f=10000",
    },
    "room_ambience": {
        "default": "aecho=0.88:0.45:18|31|47:0.12|0.08|0.05",
        "tight-room": "aecho=0.90:0.42:12|23|36:0.10|0.07|0.04",
        "studio-a": "aecho=0.88:0.48:20|37|58:0.12|0.08|0.05",
        "drum-room": "aecho=0.86:0.50:24|43|71:0.15|0.10|0.06",
        "live-stage": "aecho=0.84:0.52:35|61|96:0.16|0.11|0.07",
    },
    "graphic_eq_32": {
        "default": "anull",
        "flat-32": "anull",
        "drums-punchy": "equalizer=f=80:t=q:w=1:g=2,equalizer=f=315:t=q:w=1:g=-2,equalizer=f=5000:t=q:w=1:g=2",
        "bass-warm": "equalizer=f=80:t=q:w=0.8:g=3,equalizer=f=315:t=q:w=1.2:g=-2,equalizer=f=2500:t=q:w=1:g=1",
        "vocals-presence": "highpass=f=80,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=3150:t=q:w=1:g=2.5,equalizer=f=8000:t=q:w=1:g=1",
        "guitar-clarity": "highpass=f=70,equalizer=f=250:t=q:w=1:g=-1.5,equalizer=f=2500:t=q:w=1:g=2",
        "piano-natural": "highpass=f=45,equalizer=f=315:t=q:w=1:g=-1,equalizer=f=3150:t=q:w=1:g=1.5",
        "smile": "equalizer=f=63:t=q:w=1:g=2,equalizer=f=125:t=q:w=1:g=1.5,equalizer=f=500:t=q:w=1:g=-1,equalizer=f=2000:t=q:w=1:g=-1,equalizer=f=8000:t=q:w=1:g=2,equalizer=f=16000:t=q:w=1:g=1.5",
        "speech": "highpass=f=80,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=1250:t=q:w=1:g=1,equalizer=f=3150:t=q:w=1:g=2.5,equalizer=f=8000:t=q:w=1:g=1",
        "master-air": "highpass=f=25,equalizer=f=125:t=q:w=1:g=0.8,equalizer=f=315:t=q:w=1:g=-0.8,equalizer=f=10000:t=q:w=1:g=1.2,equalizer=f=16000:t=q:w=1:g=0.8",
    },
    "amplify": {
        "default": "volume=0dB",
        "plus-3db": "volume=3dB",
        "plus-6db": "volume=6dB",
        "minus-3db": "volume=-3dB",
        "minus-6db": "volume=-6dB",
        "minus-12db": "volume=-12dB",
    },
    "stereo_imager": {
        "default": "aformat=channel_layouts=stereo,stereowiden=delay=12:feedback=0.15:crossfeed=0.22:drymix=0.9",
        "mono-safe": "aformat=channel_layouts=stereo,stereotools=mode=lr>ms:mlev=1:slev=0.35,stereotools=mode=ms>lr",
        "narrow": "aformat=channel_layouts=stereo,stereotools=mode=lr>ms:mlev=1:slev=0.65,stereotools=mode=ms>lr",
        "wide": "aformat=channel_layouts=stereo,stereowiden=delay=14:feedback=0.18:crossfeed=0.22:drymix=0.92",
        "extra-wide": "aformat=channel_layouts=stereo,stereowiden=delay=20:feedback=0.24:crossfeed=0.18:drymix=0.88",
    },
    "maximizer_loudness": {
        "default": "acompressor=threshold=0.20:ratio=2.5:attack=18:release=180:makeup=1.25,alimiter=limit=0.891:attack=5:release=60:level=disabled",
        "transparent": "acompressor=threshold=0.23:ratio=1.8:attack=30:release=260:makeup=1.12,alimiter=limit=0.891:attack=5:release=80:level=disabled",
        "streaming": "loudnorm=I=-14:LRA=9:TP=-1,alimiter=limit=0.891:attack=5:release=60:level=disabled",
        "loud": "acompressor=threshold=0.16:ratio=3:attack=12:release=150:makeup=1.45,alimiter=limit=0.933:attack=4:release=50:level=disabled",
        "live": "acompressor=threshold=0.19:ratio=2.2:attack=20:release=220:makeup=1.25,alimiter=limit=0.85:attack=8:release=90:level=disabled",
    },
    "mastering_wizard": {
        "default": "highpass=f=25,equalizer=f=250:t=q:w=1:g=-0.6,equalizer=f=9500:t=q:w=0.8:g=0.9,acompressor=threshold=0.20:ratio=2:attack=30:release=280:makeup=1.10,alimiter=limit=0.891:attack=5:release=70:level=disabled",
        "balanced": "highpass=f=25,equalizer=f=280:t=q:w=1:g=-0.5,equalizer=f=10000:t=q:w=0.8:g=0.8,acompressor=threshold=0.20:ratio=2:attack=30:release=280:makeup=1.10,alimiter=limit=0.891:attack=5:release=70:level=disabled",
        "warm": "highpass=f=25,equalizer=f=110:t=q:w=0.9:g=1,equalizer=f=350:t=q:w=1:g=-0.7,equalizer=f=8500:t=q:w=1:g=0.4,acompressor=threshold=0.21:ratio=1.9:attack=35:release=300:makeup=1.08,alimiter=limit=0.891:attack=6:release=80:level=disabled",
        "clear": "highpass=f=28,equalizer=f=300:t=q:w=1:g=-0.8,equalizer=f=3200:t=q:w=1:g=0.7,equalizer=f=12000:t=q:w=0.8:g=1.1,acompressor=threshold=0.21:ratio=1.8:attack=32:release=260:makeup=1.08,alimiter=limit=0.891:attack=5:release=65:level=disabled",
        "live-pa": "highpass=f=35,equalizer=f=250:t=q:w=1:g=-1,equalizer=f=3500:t=q:w=1:g=0.5,acompressor=threshold=0.18:ratio=2.3:attack=22:release=220:makeup=1.12,alimiter=limit=0.84:attack=8:release=90:level=disabled",
    },
    "denoise": {
        "default": "afftdn=nr=10:nf=-50:tn=1",
        "light": "afftdn=nr=6:nf=-55:tn=1",
        "moderate": "afftdn=nr=10:nf=-50:tn=1",
        "strong": "afftdn=nr=16:nf=-45:tn=1",
        "voice": "highpass=f=70,afftdn=nr=12:nf=-52:tn=1",
    },
    "crackle_cleaner": {
        "default": "adeclick",
        "light": "adeclick=w=45:o=75:a=2:t=2",
        "moderate": "adeclick=w=55:o=75:a=2:t=2",
        "strong": "adeclick=w=75:o=70:a=2:t=2",
    },
}

# UI/server validation schema. All values are numeric and converted by builders.
SCHEMAS: dict[str, dict[str, dict[str, float | str]]] = {
    "delay": {"delay_ms": {"min": 1, "max": 2000, "step": 1, "default": 180}, "decay": {"min": 0.01, "max": 0.9, "step": 0.01, "default": 0.22}},
    "reverb_lexicon": {"size": {"min": 0.1, "max": 1.0, "step": 0.01, "default": 0.55}, "mix": {"min": 0.01, "max": 0.7, "step": 0.01, "default": 0.22}, "damping_hz": {"min": 3000, "max": 18000, "step": 100, "default": 12000}},
    "room_ambience": {"size": {"min": 0.05, "max": 1.0, "step": 0.01, "default": 0.3}, "mix": {"min": 0.01, "max": 0.6, "step": 0.01, "default": 0.12}},
    "graphic_eq_32": {f"g{f}": {"min": -12, "max": 12, "step": 0.5, "default": 0} for f in BANDS_32},
    "amplify": {"gain_db": {"min": -60, "max": 24, "step": 0.1, "default": 0}},
    "stereo_imager": {"width": {"min": 0, "max": 2, "step": 0.01, "default": 1}},
    "maximizer_loudness": {"drive_db": {"min": 0, "max": 12, "step": 0.1, "default": 2}, "ceiling_db": {"min": -6, "max": -0.1, "step": 0.1, "default": -1}},
    "mastering_wizard": {"tone": {"min": -1, "max": 1, "step": 0.05, "default": 0}, "glue": {"min": 0, "max": 1, "step": 0.05, "default": 0.5}, "ceiling_db": {"min": -3, "max": -0.1, "step": 0.1, "default": -1}},
    "denoise": {"reduction_db": {"min": 0, "max": 30, "step": 1, "default": 10}, "noise_floor_db": {"min": -80, "max": -20, "step": 1, "default": -50}},
    "crackle_cleaner": {"strength": {"min": 0, "max": 1, "step": 0.05, "default": 0.5}},
    "eq": {"frequency": {"min": 20, "max": 20000, "step": 1, "default": 1000}, "gain_db": {"min": -18, "max": 18, "step": 0.1, "default": 0}, "q": {"min": 0.1, "max": 10, "step": 0.1, "default": 1}},
    "normalizer": {"target_lufs": {"min": -30, "max": -5, "step": 0.5, "default": -14}, "true_peak_db": {"min": -6, "max": -0.1, "step": 0.1, "default": -1}},
    "compressor": {"threshold_db": {"min": -50, "max": -1, "step": 0.5, "default": -18}, "ratio": {"min": 1, "max": 20, "step": 0.1, "default": 3}, "attack_ms": {"min": 0.1, "max": 200, "step": 0.1, "default": 20}, "release_ms": {"min": 10, "max": 2000, "step": 1, "default": 250}},
    "limiter": {"ceiling_db": {"min": -12, "max": -0.1, "step": 0.1, "default": -1}},
}

CUSTOM_FILE = Path(os.environ.get("MTA_DATA_DIR", "/data/projects")).resolve() / "_custom_presets.json"


# Human-editable parameter values associated with factory presets. These are
# exposed to the UI so selecting a preset immediately updates every visible
# control. The values are chosen to match the factory processing intent and are
# validated through the same SCHEMAS used by custom presets.
def _factory_params() -> dict[str, dict[str, dict[str, float]]]:
    defaults = {
        plugin: {key: float(spec["default"]) for key, spec in schema.items()}
        for plugin, schema in SCHEMAS.items() if plugin != "eq"
    }
    out: dict[str, dict[str, dict[str, float]]] = {
        plugin: {name: dict(defaults.get(plugin, {})) for name in presets}
        for plugin, presets in PRESETS.items()
    }
    def put(plugin: str, preset: str, **params: float) -> None:
        if plugin in out and preset in out[plugin]:
            out[plugin][preset].update({k: float(v) for k, v in params.items()})

    # Level / dynamics
    put("normalizer", "streaming-14", target_lufs=-14, true_peak_db=-1)
    put("normalizer", "broadcast-23", target_lufs=-23, true_peak_db=-2)
    put("normalizer", "music-12", target_lufs=-12, true_peak_db=-1)
    put("normalizer", "gentle-16", target_lufs=-16, true_peak_db=-1.5)
    for name, th, ratio, attack, release in [
        ("moderate", -18.1, 3, 20, 250), ("vocal", -20, 3.5, 8, 180),
        ("drums", -15.9, 4, 5, 120), ("bass", -17.1, 4, 12, 220),
        ("master-glue", -14.9, 2, 30, 300),
    ]: put("compressor", name, threshold_db=th, ratio=ratio, attack_ms=attack, release_ms=release)
    put("limiter", "brickwall-1", ceiling_db=-1)
    put("limiter", "brickwall-0.3", ceiling_db=-0.3)
    put("limiter", "safe-2", ceiling_db=-2)

    # Time / space
    put("delay", "slapback", delay_ms=95, decay=.24)
    put("delay", "vocal-quarter", delay_ms=320, decay=.20)
    put("delay", "stereo-space", delay_ms=175, decay=.20)
    put("delay", "long-echo", delay_ms=620, decay=.20)
    for name, size, mix, damping in [
        ("lexicon-vocal-plate", .34, .24, 11000), ("lexicon-large-hall", .72, .24, 12000),
        ("lexicon-small-hall", .28, .20, 13000), ("lexicon-ambient", .92, .21, 10000),
    ]: put("reverb_lexicon", name, size=size, mix=mix, damping_hz=damping)
    for name, size, mix in [
        ("tight-room", .13, .10), ("studio-a", .38, .12), ("drum-room", .50, .15), ("live-stage", .84, .16),
    ]: put("room_ambience", name, size=size, mix=mix)

    # EQ: start flat and transfer named gains from the factory expression.
    for preset, expr in PRESETS["graphic_eq_32"].items():
        params = dict(defaults["graphic_eq_32"])
        for freq, gain in re.findall(r"equalizer=f=([0-9.]+):[^,]*?:g=([-0-9.]+)", expr):
            nearest = min(BANDS_32, key=lambda item: abs(item - float(freq)))
            params[f"g{nearest}"] = float(gain)
        out["graphic_eq_32"][preset] = params

    # Gain / width / loudness
    for name, gain in [("plus-3db",3),("plus-6db",6),("minus-3db",-3),("minus-6db",-6),("minus-12db",-12)]:
        put("amplify", name, gain_db=gain)
    for name, width in [("mono-safe",.35),("narrow",.65),("wide",1.35),("extra-wide",1.7)]:
        put("stereo_imager", name, width=width)
    for name, drive, ceiling in [("transparent",1,-1),("streaming",2,-1),("loud",6,-.6),("live",3,-1.4)]:
        put("maximizer_loudness", name, drive_db=drive, ceiling_db=ceiling)
    for name, tone, glue, ceiling in [
        ("balanced",0,.50,-1),("warm",-.45,.40,-1),("clear",.55,.35,-1),("live-pa",.15,.65,-1.5),
    ]: put("mastering_wizard", name, tone=tone, glue=glue, ceiling_db=ceiling)
    for name, reduction, floor in [("light",6,-55),("moderate",10,-50),("strong",16,-45),("voice",12,-52)]:
        put("denoise", name, reduction_db=reduction, noise_floor_db=floor)
    for name, strength in [("light",.20),("moderate",.50),("strong",.85)]:
        put("crackle_cleaner", name, strength=strength)
    return out

FACTORY_PARAMS = _factory_params()


def _load_custom() -> dict[str, dict[str, dict[str, float | int | str | bool]]]:
    try:
        raw = json.loads(CUSTOM_FILE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_custom(data: dict) -> None:
    CUSTOM_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CUSTOM_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(CUSTOM_FILE)


def _num(params: dict, key: str, plugin: str) -> float:
    spec = SCHEMAS[plugin][key]
    try:
        value = float(params.get(key, spec["default"]))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {plugin}.{key}") from exc
    if value < float(spec["min"]) or value > float(spec["max"]):
        raise ValueError(f"{plugin}.{key} outside allowed range")
    return value


def validate_custom_params(plugin: str, params: dict) -> dict[str, float]:
    if plugin not in SCHEMAS:
        raise ValueError(f"custom configuration is not supported for {plugin}")
    allowed = SCHEMAS[plugin]
    unknown = set(params) - set(allowed)
    if unknown:
        raise ValueError(f"unsupported parameter(s): {', '.join(sorted(unknown))}")
    return {key: _num(params, key, plugin) for key in allowed}


def custom_filter(plugin: str, params: dict) -> str:
    p = validate_custom_params(plugin, params)
    if plugin == "eq":
        return f"equalizer=f={p['frequency']:.2f}:t=q:w={p['q']:.2f}:g={p['gain_db']:.2f}"
    if plugin == "normalizer":
        return f"loudnorm=I={p['target_lufs']:.2f}:LRA=11:TP={p['true_peak_db']:.2f}"
    if plugin == "compressor":
        # acompressor threshold uses linear amplitude.
        threshold = 10 ** (p["threshold_db"] / 20.0)
        return f"acompressor=threshold={threshold:.6f}:ratio={p['ratio']:.2f}:attack={p['attack_ms']:.2f}:release={p['release_ms']:.2f}:makeup=1"
    if plugin == "limiter":
        limit = 10 ** (p["ceiling_db"] / 20.0)
        return f"alimiter=limit={limit:.6f}:attack=5:release=70:level=disabled"
    if plugin == "delay":
        return f"aecho=0.82:0.52:{p['delay_ms']:.0f}:{p['decay']:.3f}"
    if plugin == "reverb_lexicon":
        base = 30 + 120 * p["size"]
        mix = p["mix"]
        return (f"aecho=0.82:0.70:{base:.0f}|{base*1.61:.0f}|{base*2.43:.0f}|{base*3.37:.0f}:"
                f"{mix:.3f}|{mix*.70:.3f}|{mix*.48:.3f}|{mix*.30:.3f},highpass=f=70,lowpass=f={p['damping_hz']:.0f}")
    if plugin == "room_ambience":
        base = 8 + 32 * p["size"]
        mix = p["mix"]
        return f"aecho=0.90:0.45:{base:.0f}|{base*1.7:.0f}|{base*2.55:.0f}:{mix:.3f}|{mix*.66:.3f}|{mix*.42:.3f}"
    if plugin == "graphic_eq_32":
        parts = []
        for freq in BANDS_32:
            gain = p[f"g{freq}"]
            if abs(gain) >= 0.05:
                parts.append(f"equalizer=f={freq}:t=q:w=1:g={gain:.2f}")
        return ",".join(parts) or "anull"
    if plugin == "amplify":
        return f"volume={p['gain_db']:.2f}dB"
    if plugin == "stereo_imager":
        # Explicitly upmix mono to stereo before mid/side processing. This makes
        # the insert a real mono->stereo processor when used on mono tracks.
        return (
            "aformat=channel_layouts=stereo,"
            f"stereotools=mode=lr>ms:mlev=1:slev={p['width']:.3f},"
            "stereotools=mode=ms>lr"
        )
    if plugin == "maximizer_loudness":
        ceiling = 10 ** (p["ceiling_db"] / 20.0)
        return f"volume={p['drive_db']:.2f}dB,acompressor=threshold=0.20:ratio=2.5:attack=18:release=180:makeup=1,alimiter=limit={ceiling:.6f}:attack=5:release=70:level=disabled"
    if plugin == "mastering_wizard":
        tone = p["tone"]
        ratio = 1.5 + p["glue"] * 1.5
        ceiling = 10 ** (p["ceiling_db"] / 20.0)
        return (f"highpass=f=25,equalizer=f=250:t=q:w=1:g={-0.7*tone:.2f},"
                f"equalizer=f=10000:t=q:w=0.8:g={1.1*tone:.2f},acompressor=threshold=0.20:ratio={ratio:.2f}:"
                f"attack=30:release=280:makeup=1.08,alimiter=limit={ceiling:.6f}:attack=5:release=70:level=disabled")
    if plugin == "denoise":
        return f"afftdn=nr={p['reduction_db']:.1f}:nf={p['noise_floor_db']:.1f}:tn=1"
    if plugin == "crackle_cleaner":
        w = 35 + p["strength"] * 50
        overlap = 80 - p["strength"] * 12
        return f"adeclick=w={w:.0f}:o={overlap:.0f}:a=2:t=2"
    raise ValueError(f"unsupported plugin: {plugin}")


def save_user_preset(plugin: str, name: str, params: dict) -> dict[str, float]:
    validated = validate_custom_params(plugin, params)
    data = _load_custom()
    data.setdefault(plugin, {})[name] = validated
    _save_custom(data)
    return validated


def delete_user_preset(plugin: str, name: str) -> bool:
    data = _load_custom()
    if name not in data.get(plugin, {}):
        return False
    del data[plugin][name]
    if not data[plugin]:
        del data[plugin]
    _save_custom(data)
    return True


def user_presets() -> dict[str, dict[str, dict]]:
    return deepcopy(_load_custom())


def plugin_catalog() -> dict[str, list[str]]:
    custom = _load_custom()
    return {
        kind: list(presets) + [f"user:{name}" for name in sorted(custom.get(kind, {}))]
        for kind, presets in PRESETS.items()
    }


def plugin_manifest() -> dict[str, object]:
    public_schemas = {key: value for key, value in SCHEMAS.items() if key != "eq"}
    public_custom = {key: value for key, value in user_presets().items() if key != "eq"}
    return {
        "presets": plugin_catalog(),
        "schemas": public_schemas,
        "custom": public_custom,
        "factory_params": deepcopy(FACTORY_PARAMS),
        "channel_behavior": {
            "stereo_imager": {"mono_to_stereo": True, "output_channels": 2},
        },
        "notes": {
            "reverb_lexicon": "Lexicon-style preset family implemented with open FFmpeg processing; not a Lexicon algorithm/emulation.",
            "mastering_wizard": "Rule-based mastering chain; final level should still be auditioned on representative playback systems.",
        },
    }


def plugin_filter(plugin: InsertPlugin) -> str | None:
    if not plugin.enabled:
        return None
    if plugin.params:
        return custom_filter(plugin.plugin, plugin.params)
    if plugin.preset.startswith("user:"):
        name = plugin.preset[5:]
        params = _load_custom().get(plugin.plugin, {}).get(name)
        if params is None:
            raise ValueError(f"user preset not found: {plugin.preset}")
        return custom_filter(plugin.plugin, params)
    if plugin.plugin == "eq":
        presets = LEGACY_EQ_PRESETS
    else:
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


def insert_expands_to_stereo(plugin: InsertPlugin) -> bool:
    """Return True when an enabled insert turns mono input into stereo output."""
    return bool(plugin.enabled and plugin.plugin == "stereo_imager")


def effective_output_channels(source_channels: int, inserts: list[InsertPlugin]) -> int:
    """Resolve logical channel count after an insert chain."""
    channels = 1 if int(source_channels or 0) == 1 else 2
    if channels == 1 and any(insert_expands_to_stereo(item) for item in inserts):
        return 2
    return channels


class DemucsStemSplitter:
    name = "demucs"
    display_name = "Demucs stem separation"

    @staticmethod
    def available() -> bool:
        return shutil.which("demucs") is not None or importlib.util.find_spec("demucs") is not None

    @classmethod
    def _model_profiles(cls) -> list[dict[str, object]]:
        """Return built-in and administrator-configured stem model profiles.

        Custom profiles are supplied through MTA_DEMUCS_MODEL_REGISTRY as JSON,
        or MTA_DEMUCS_MODEL_REGISTRY_FILE pointing to a JSON file.  The registry
        may be either a list of profile objects or {"models": [...]}.  A profile
        minimally declares id/model and stem_count; labels and display_name are
        optional.  This keeps the application independent from a hard-coded
        maximum such as 8 or 16 stems.
        """
        profiles: list[dict[str, object]] = [
            {"id": "htdemucs", "model": "htdemucs", "stem_count": 4, "display_name": "HTDemucs 4 stem", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "htdemucs_ft", "model": "htdemucs_ft", "stem_count": 4, "display_name": "HTDemucs FT 4 stem", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "htdemucs_6s", "model": "htdemucs_6s", "stem_count": 6, "display_name": "HTDemucs 6 stem", "stem_labels": ["drums", "bass", "other", "vocals", "guitar", "piano"]},
            {"id": "hdemucs_mmi", "model": "hdemucs_mmi", "stem_count": 4, "display_name": "HDemucs MMI", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "mdx", "model": "mdx", "stem_count": 4, "display_name": "MDX", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "mdx_extra", "model": "mdx_extra", "stem_count": 4, "display_name": "MDX Extra", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "mdx_q", "model": "mdx_q", "stem_count": 4, "display_name": "MDX Quantized", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "mdx_extra_q", "model": "mdx_extra_q", "stem_count": 4, "display_name": "MDX Extra Quantized", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "repro_mdx_a", "model": "repro_mdx_a", "stem_count": 4, "display_name": "Repro MDX A", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "repro_mdx_a_hybrid_only", "model": "repro_mdx_a_hybrid_only", "stem_count": 4, "display_name": "Repro MDX A Hybrid", "stem_labels": ["drums", "bass", "other", "vocals"]},
            {"id": "repro_mdx_a_time_only", "model": "repro_mdx_a_time_only", "stem_count": 4, "display_name": "Repro MDX A Time", "stem_labels": ["drums", "bass", "other", "vocals"]},
        ]
        raw = os.getenv("MTA_DEMUCS_MODEL_REGISTRY", "").strip()
        registry_file = os.getenv("MTA_DEMUCS_MODEL_REGISTRY_FILE", "").strip()
        if registry_file:
            try:
                raw = Path(registry_file).read_text(encoding="utf-8")
            except OSError:
                raw = raw or ""
        if raw:
            try:
                parsed = json.loads(raw)
                items = parsed.get("models", []) if isinstance(parsed, dict) else parsed
                for item in items if isinstance(items, list) else []:
                    if not isinstance(item, dict):
                        continue
                    model = str(item.get("model") or item.get("id") or "").strip()
                    try:
                        count = int(item.get("stem_count", 0))
                    except (TypeError, ValueError):
                        continue
                    if not model or count < 2 or count > 64:
                        continue
                    labels = item.get("stem_labels")
                    if not isinstance(labels, list) or len(labels) != count:
                        labels = [f"stem_{index + 1}" for index in range(count)]
                    profiles.append({
                        "id": str(item.get("id") or model),
                        "model": model,
                        "stem_count": count,
                        "display_name": str(item.get("display_name") or f"{model} ({count} stem)"),
                        "stem_labels": [str(label) for label in labels],
                        "engine": str(item.get("engine") or "demucs"),
                    })
            except (ValueError, TypeError):
                pass
        # Backward-compatible 8-stem environment variable.
        extended_8_model = os.getenv("MTA_DEMUCS_8_MODEL", "").strip()
        if extended_8_model and not any(str(item.get("model")) == extended_8_model for item in profiles):
            profiles.append({"id": extended_8_model, "model": extended_8_model, "stem_count": 8, "display_name": f"{extended_8_model} (8 stem)", "stem_labels": [f"stem_{index + 1}" for index in range(8)], "engine": "demucs"})
        # Deduplicate by model id while preserving administrator overrides.
        dedup: dict[str, dict[str, object]] = {}
        for item in profiles:
            dedup[str(item["model"])] = item
        try:
            from .model_updater import load_blacklist
            blacklist = load_blacklist()
        except Exception:
            blacklist = set()
        return [item for item in dedup.values() if str(item.get("id") or item.get("model")) not in blacklist and str(item.get("model")) not in blacklist]

    @classmethod
    def status(cls) -> dict[str, object]:
        profiles = cls._model_profiles()
        models = [str(item["model"]) for item in profiles]
        supported_counts = sorted({2, *(int(item["stem_count"]) for item in profiles)})
        return {
            "name": cls.name,
            "display_name": cls.display_name,
            "available": cls.available(),
            "models": models,
            "model_profiles": profiles,
            "recommended_model": "htdemucs_6s",
            "supported_stem_counts": supported_counts,
            "default_stem_count": 0,
            "max_supported_stem_count": max(supported_counts, default=6),
            "model_driven": True,
        }

    @classmethod
    def split(
        cls,
        source: Path,
        output_dir: Path,
        model: str = "htdemucs_6s",
        *,
        stem_count: int = 0,
        progress=None,
        cancel_event=None,
    ) -> list[Path]:
        if stem_count != 0 and not 2 <= stem_count <= 64:
            raise ValueError("unsupported stem count")
        profiles = cls._model_profiles()
        by_model = {str(item["model"]): item for item in profiles}
        if stem_count == 2:
            # Demucs two-stem mode is derived from the standard 4-stem model.
            if model not in {"htdemucs", "htdemucs_ft"}:
                model = "htdemucs"
        elif stem_count:
            matching = [item for item in profiles if int(item["stem_count"]) == stem_count]
            if model not in by_model or int(by_model[model]["stem_count"]) != stem_count:
                if not matching:
                    raise ValueError(f"no configured model provides {stem_count} stems")
                model = str(matching[0]["model"])
        if model not in by_model:
            raise ValueError("unsupported Demucs model")
        if not cls.available():
            raise RuntimeError("Demucs stem plugin is not installed in this runtime")
        local_repo = os.getenv("MTA_DEMUCS_LOCAL_REPO", "").strip()
        # Native desktop builds intentionally use Demucs' own upstream resolver/cache.
        # Do not proxy model acquisition through the MTA server: this keeps native
        # splitting usable offline after first download and avoids coupling desktop
        # inference to server authentication/catalog availability.
        if getattr(sys, "frozen", False):
            local_repo = ""
        output_dir.mkdir(parents=True, exist_ok=True)
        if getattr(sys, "frozen", False):
            # In native .app/.exe builds, starting the frozen GUI executable as a
            # Demucs subprocess is fragile on macOS (the child can be treated as
            # another app instance and terminate/reload the main window). Run the
            # packaged Demucs module in the existing background worker thread.
            if progress:
                progress(20, "Caricamento modello Demucs nell'app nativa")
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("stem separation cancelled")
            from demucs.separate import main as demucs_main

            old_argv = sys.argv[:]
            try:
                sys.argv = ["demucs.separate", "-n", model, "--out", str(output_dir)]
                if local_repo:
                    sys.argv += ["--repo", local_repo]
                if stem_count == 2:
                    sys.argv += ["--two-stems", "vocals"]
                sys.argv.append(str(source))
                try:
                    result = demucs_main()
                except SystemExit as exc:
                    code = int(exc.code or 0)
                    if code:
                        raise RuntimeError(f"Demucs terminated with exit code {code}") from exc
                else:
                    if result not in {None, 0}:
                        raise RuntimeError(f"Demucs terminated with exit code {result}")
            finally:
                sys.argv = old_argv
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("stem separation cancelled")
            if progress:
                progress(88, "Raccolta delle tracce separate")
            candidates = sorted(output_dir.glob(f"{model}/**/*.wav"))
            if not candidates:
                candidates = sorted(output_dir.rglob("*.wav"))
            if not candidates:
                raise RuntimeError("stem separator produced no WAV files")
            return candidates

        if shutil.which("demucs"):
            cmd = ["demucs", "-n", model, "--out", str(output_dir)]
        else:
            cmd = [sys.executable, "-m", "demucs.separate", "-n", model, "--out", str(output_dir)]
        if local_repo:
            cmd += ["--repo", local_repo]
        if stem_count == 2:
            cmd += ["--two-stems", "vocals"]
        cmd.append(str(source))
        if progress:
            progress(20, "Avvio del modello Demucs")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        tail: list[str] = []
        percent_re = re.compile(r"(?<!\d)(\d{1,3})%")
        if proc.stdout is None:
            proc.kill()
            raise RuntimeError("unable to capture Demucs progress output")

        lines: queue.Queue[str | None] = queue.Queue()

        def _read_output() -> None:
            try:
                for item in proc.stdout:
                    lines.put(item)
            finally:
                lines.put(None)

        reader = threading.Thread(target=_read_output, daemon=True, name="demucs-output")
        reader.start()
        stream_done = False
        while True:
            if cancel_event is not None and cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                raise RuntimeError("stem separation cancelled")
            try:
                line = lines.get(timeout=0.25)
            except queue.Empty:
                line = ""
            if line is None:
                stream_done = True
            elif line:
                clean = line.strip()
                if clean:
                    tail.append(clean)
                    tail = tail[-40:]
                    match = percent_re.search(clean)
                    if match and progress:
                        raw = max(0, min(100, int(match.group(1))))
                        progress(20 + int(raw * 0.65), clean[-180:])
            if proc.poll() is not None and stream_done:
                break
        reader.join(timeout=1)
        if proc.returncode:
            raise RuntimeError("\n".join(tail)[-3000:] or "stem separation failed")
        if progress:
            progress(88, "Raccolta delle tracce separate")
        candidates = sorted(output_dir.glob(f"{model}/**/*.wav"))
        if not candidates:
            candidates = sorted(output_dir.rglob("*.wav"))
        if not candidates:
            raise RuntimeError("stem separator produced no WAV files")
        return candidates


STEM_SPLITTER = DemucsStemSplitter
