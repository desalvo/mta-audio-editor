"""Opt-in bounded batch WAV export using the isolated VST3 native chain."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import tempfile
from pathlib import Path
import sys
import wave

from .native_chain import MAX_FRAMES, MAX_INSERTS, NativeChainError, render_native_wav

MAX_JOBS = 128
MAX_MANIFEST_BYTES = 256 * 1024
MAX_TOTAL_FRAMES = 16 * MAX_FRAMES


def run_batch(manifest: Path, executable: str, *, timeout: float = 15.0,
              stop_on_error: bool = False, dry_run: bool = False, atomic_batch: bool = False,
              max_total_frames: int = MAX_TOTAL_FRAMES) -> dict:
    """Run validated exports. Each destination is atomically published separately."""
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be positive and finite")
    if isinstance(max_total_frames, bool) or not isinstance(max_total_frames, int) or not 1 <= max_total_frames <= MAX_TOTAL_FRAMES:
        raise ValueError("Invalid total frame budget")
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
    source_inodes = set()
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
        source_inodes.add((src.stat().st_dev, src.stat().st_ino))
        planned.append((src, dest, [(pair[0], pair[1]) for pair in plugins]))
    if any(dest.exists() and (dest.stat().st_dev, dest.stat().st_ino) in source_inodes
           for _, dest, _ in planned):
        raise ValueError("A batch destination aliases an input by hard link")
    if any(source in destinations for source, _, _ in planned):
        raise ValueError("A batch output may not overwrite any batch input")
    if dry_run or atomic_batch:
        checks = []
        total_frames = 0
        for index, (source, destination, plugins) in enumerate(planned):
            with wave.open(str(source), 'rb') as wav:
                channels, frames, width = wav.getnchannels(), wav.getnframes(), wav.getsampwidth()
                if (wav.getcomptype() != 'NONE' or channels not in (1, 2) or
                    width not in (2, 3, 4) or wav.getframerate() not in (44100, 48000, 96000) or
                    not 1 <= frames <= MAX_FRAMES):
                    raise ValueError(f'Unsupported WAV format in job {index}')
                if len(wav.readframes(frames)) != frames * channels * width:
                    raise ValueError(f'Truncated WAV in job {index}')
            total_frames += frames
            if total_frames > max_total_frames:
                raise ValueError('Batch exceeds total frame budget')
            if not destination.parent.is_dir():
                raise ValueError(f'Output folder does not exist in job {index}')
            checks.append({'index': index, 'status': 'ready', 'source': str(source),
                           'destination': str(destination), 'frames': frames,
                           'channels': channels, 'bit_depth': width * 8,
                           'inserts': len(plugins)})
        if dry_run:
            return {'status': 'ready', 'requested': len(planned), 'processed': 0,
                    'total_frames': total_frames, 'results': checks}
    if atomic_batch:
        return _run_atomic_batch(planned, executable, timeout)
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



def _run_atomic_batch(planned: list, executable: str, timeout: float) -> dict:
    """All-or-nothing WAV batch, including restoration on publication failures.

    Plugins run before the first destination is changed. Staging and backups
    are created beside destinations to guarantee same-filesystem os.replace.
    An OS crash/power loss during publication remains outside this guarantee.
    """
    staged: list[tuple[Path, Path]] = []
    backups: dict[Path, Path] = {}
    published: list[Path] = []
    try:
        for source, dest, plugins in planned:
            fd, name = tempfile.mkstemp(prefix='.mta-stage-', suffix='.wav', dir=dest.parent)
            os.close(fd)
            stage = Path(name)
            staged.append((stage, dest))
            render_native_wav(source, stage, plugins, executable, timeout=timeout)
        # Backup originals before publishing. copy2 preserves destination until commit.
        for _, dest in staged:
            if dest.exists():
                fd, name = tempfile.mkstemp(prefix='.mta-backup-', suffix='.wav', dir=dest.parent)
                os.close(fd)
                backup = Path(name)
                backups[dest] = backup
                shutil.copy2(dest, backup)
        for stage, dest in staged:
            os.replace(stage, dest)
            published.append(dest)
        return {'status': 'ok', 'requested': len(planned), 'processed': len(planned),
                'atomic_batch': True,
                'results': [{'index': i, 'status': 'ok', 'destination': str(dest)}
                            for i, (_, dest) in enumerate(staged)]}
    except Exception as exc:
        rollback_errors = []
        for dest in reversed(published):
            try:
                backup = backups.get(dest)
                if backup is None:
                    dest.unlink(missing_ok=True)
                else:
                    os.replace(backup, dest)
            except OSError as rollback_exc:
                rollback_errors.append(f'{dest}: {rollback_exc}')
        return {'status': 'partial_failure' if rollback_errors else 'rolled_back',
                'requested': len(planned), 'processed': 0, 'atomic_batch': True,
                'error': str(exc)[:512], 'rollback_errors': rollback_errors[:8],
                'results': []}
    finally:
        for stage, _ in staged:
            stage.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)

def _write_report(destination: Path, result: dict) -> None:
    """Save a batch receipt using same-directory atomic replace."""
    destination = Path(destination)
    if not destination.parent.is_dir():
        raise ValueError('Report directory does not exist')
    fd, path = tempfile.mkstemp(prefix='.mta-report-', suffix='.json', dir=destination.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(result, stream, sort_keys=True, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, destination)
    finally:
        Path(path).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experimental VST3 WAV batch renderer")
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--probe', required=True)
    parser.add_argument('--timeout', type=float, default=15.0)
    parser.add_argument('--stop-on-error', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='Validate WAV inputs and output paths without launching plugins')
    parser.add_argument('--max-total-frames', type=int, default=MAX_TOTAL_FRAMES,
                        help='Maximum cumulative source frames (dry-run/atomic batch)')
    parser.add_argument('--report', type=Path, help='Write validated JSON result atomically')
    parser.add_argument('--atomic-batch', action='store_true', help='Stage every render before publishing any destination')
    args = parser.parse_args(argv)
    try:
        result = run_batch(args.manifest, args.probe, timeout=args.timeout,
                           stop_on_error=args.stop_on_error, dry_run=args.dry_run,
                           atomic_batch=args.atomic_batch, max_total_frames=args.max_total_frames)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid_manifest", "error": str(exc)[:512]}), file=sys.stderr)
        return 2
    if args.report is not None:
        try:
            _write_report(args.report, result)
        except (OSError, ValueError) as exc:
            print(json.dumps({'status': 'report_error', 'error': str(exc)[:512]}), file=sys.stderr)
            return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('ok', 'ready') else 1


if __name__ == '__main__':
    raise SystemExit(main())
