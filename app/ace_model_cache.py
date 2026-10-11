"""Bounded, read-only inspection of server-side ACE-Step model caches.

Never expose filenames, absolute paths, or filesystem contents to remote users.
"""
from __future__ import annotations
import os
from pathlib import Path


def cache_status(*, roots: tuple[Path, ...] | None = None, file_limit: int = 20000) -> dict:
    if not 1 <= file_limit <= 100000:
        raise ValueError("invalid file limit")
    if roots is None:
        roots = (Path(os.environ.get("MTA_ACE_MODEL_CACHE", "/app/checkpoints")),
                 Path(os.environ.get("HF_HOME", "/root/.cache/huggingface")))
    total_bytes = 0
    count = 0
    truncated = False
    available = []
    for root in roots:
        available.append(root.is_dir())
        if not root.is_dir():
            continue
        for base, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [name for name in dirs if not (Path(base) / name).is_symlink()]
            for name in files:
                item = Path(base) / name
                if item.is_symlink():
                    continue
                if count >= file_limit:
                    truncated = True
                    break
                try:
                    size = item.stat().st_size
                    if size >= 0:
                        total_bytes += size
                        count += 1
                except OSError:
                    continue
            if truncated:
                break
        if truncated:
            break
    return {"cache_available": any(available), "bytes_cached": total_bytes,
            "file_count": count, "scan_truncated": truncated,
            "models_ready": None, "inference_verified": False,
            "note": "Cache occupancy is not proof that model checkpoints are complete or usable."}
