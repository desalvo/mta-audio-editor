"""Command-line entry point for the isolated experimental VST3 WAV renderer."""
from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

from .native_chain import NativeChainError, render_native_wav


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render 44.1/48/96-kHz PCM16/24/32 WAV through isolated VST3 inserts (experimental)")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--probe", required=True, help="Native SDK-enabled probe executable")
    parser.add_argument("--insert", action="append", nargs=2, metavar=("VST3_PATH", "CID"), required=True,
                        help="Module path and 32-character hex VST3 class ID; repeat in chain order")
    parser.add_argument("--timeout", type=float, default=15.0, help="Per-insert subprocess timeout in seconds")
    arguments = parser.parse_args(argv)
    try:
        if not 1 <= len(arguments.insert) <= 8:
            raise ValueError("Expected 1..8 VST3 inserts")
        result = render_native_wav(arguments.source, arguments.destination, arguments.insert,
                                   arguments.probe, timeout=arguments.timeout)
        with wave.open(str(result), "rb") as wav:
            summary = {"status": "ok", "output": str(result), "frames": wav.getnframes(),
                       "channels": wav.getnchannels(), "sample_rate": wav.getframerate(),
                       "bit_depth": wav.getsampwidth() * 8, "inserts": len(arguments.insert)}
        print(json.dumps(summary, sort_keys=True))
        return 0
    except (OSError, ValueError, EOFError, wave.Error, NativeChainError) as exc:
        print(f"VST3 WAV export failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
