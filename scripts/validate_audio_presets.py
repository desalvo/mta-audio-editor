#!/usr/bin/env python3
"""Runtime-smoke every factory preset and custom builder through FFmpeg."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.plugins import PRESETS, SCHEMAS, custom_filter


def check(expr: str, label: str) -> None:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
        "sine=frequency=1000:sample_rate=44100:duration=0.12", "-af", expr, "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode:
        raise RuntimeError(f"{label}: {proc.stderr.strip()[-1200:]}")


def main() -> int:
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found; preset runtime validation cannot run", file=sys.stderr)
        return 2
    count = 0
    for kind, presets in PRESETS.items():
        for name, expr in presets.items():
            check(expr, f"factory {kind}:{name}")
            count += 1
    for kind, schema in SCHEMAS.items():
        params = {key: value["default"] for key, value in schema.items()}
        check(custom_filter(kind, params), f"custom-builder {kind}")
        count += 1
    print(f"Validated {count} audio preset/filter configurations with FFmpeg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
