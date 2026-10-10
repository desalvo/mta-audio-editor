"""Opt-in bounded batch WAV export using the isolated VST3 native chain."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import wave

from .native_chain import MAX_INSERTS, NativeChainError, render_native_wav

MAX_JOBS = 128
MAX_MANIFEST_BYTES = 256 * 1024


def run_batch(manifest: Path, executable: str, *, timeout: float = 15.0,
              stop_on_error: bool = False) -> dict:
    """Run validated exports. Each destination is atomically published separately."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be positive and finite")
    manifest = Path(manifest).resolve(strict=True)
    if manifest.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Batch manifest is too large")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != 1:
        raise ValueError("Batch manifest requires schema: 1")
    entries = document.get("jobs")
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_JOBS:
        raise ValueError("Expected 1..128 batch jobs")
    planned = []
    destinations = set()
    for number, job in enumerate(entries):
        if not isinstance(job, dict) or set(job) != {"source", "destination", "plugins"}:
            raise ValueError(f"Invalid job {number}")
        source, destination, plugins = job["source"], job["destination"], job["plugins"]
        if not isinstance(source, str) or not isinstance(destination, str) or not source or not destination:
            raise ValueError(f"Invalid paths in job {number}")
        if not isinstance(plugins, list) or not 1 <= len(plugins) <= MAX_INSERTS:
            raise ValueError(f"Invalid inserts in job {number}")
        for insert in plugins:
            if not isinstance(insert, list) or len(insert) != 2 or not all(isinstance(value, str) for value in insert):
                raise ValueError(f"Invalid insert in job {number}")
            cid = insert[1]
            if len(cid) != 32 or any(char not in "0123456789abcdefABCDEF" for char in cid):
                raise ValueError(f"Invalid VST3 CID in job {number}")
        src = (manifest.parent / source).resolve(strict=True)
        dest = (manifest.parent / destination).resolve()
        if src == dest or dest in destinations or src in destinations:
            raise ValueError("Duplicate or colliding batch destination")
        destinations.add(dest)
        planned.append((src, dest, [(pair[0], pair[1]) for pair in plugins]))
    if any(source in destinations for source, _, _ in planned):
        raise ValueError("A batch output may not overwrite any batch input")
    results = []
    for index, (source, destination, plugins) in enumerate(planned):
        try:
            result = render_native_wav(source, destination, plugins, executable, timeout=timeout)
            with wave.open(str(result), 'rb') as wav:
                data = {"index": index, "status": "ok", "destination": str(result),
                        "frames": wav.getnframes(), "channels": wav.getnchannels(),
                        "bit_depth": wav.getsampwidth() * 8}
        except (OSError, ValueError, EOFError, wave.Error, NativeChainError) as exc:
            data = {"index": index, "status": "error", "error": str(exc)[:512]}
        results.append(data)
        if data["status"] == "error" and stop_on_error:
            break
    return {"status": "ok" if len(results) == len(planned) and all(item["status"] == "ok" for item in results) else "partial_failure",
            "requested": len(planned), "processed": len(results), "results": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experimental VST3 WAV batch renderer")
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--probe', required=True)
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--stop-on-error', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = run_batch(args.manifest, args.probe, timeout=args.timeout,
                           stop_on_error=args.stop_on_error)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid_manifest", "error": str(exc)[:512]}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
