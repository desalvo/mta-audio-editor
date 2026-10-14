"""Validated multi-artifact output for the fixed AI worker subprocess protocol.

An adapter writes output.wav (legacy) OR output.manifest.json plus named files
into its private job directory. Never accept paths chosen by an API caller.
"""
from __future__ import annotations
import io
import hashlib
import os
import stat
import wave
import json
import re
import zipfile
from pathlib import Path

MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_FILES = 16
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _read_private_file(path: Path, limit: int) -> bytes:
    """Read one inode once; prevent symlink/hardlink replacement during packaging."""
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError('AI artifact could not be safely opened') from exc
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('AI artifact is not a private regular file within limits')
        data = stream.read(limit + 1)
        if len(data) > limit or len(data) != info.st_size:
            raise ValueError('AI artifact changed size or exceeded limit')
        if os.fstat(stream.fileno()).st_size != info.st_size:
            raise ValueError('AI artifact changed during packaging')
        return data


def package_artifacts(directory: Path) -> tuple[bytes, str]:
    """Package immutable, bounded snapshots of private worker output files."""
    from .ai_worker_protocol import verify_preview_wav
    manifest_path = directory / 'output.manifest.json'
    if not manifest_path.exists() and not manifest_path.is_symlink():
        wav = directory / 'preview.wav'
        audio = _read_private_file(wav, MAX_ARTIFACT_BYTES)
        _verify_wav_bytes(audio)
        return audio, 'audio/wav'
    raw_manifest = _read_private_file(manifest_path, 256_000)
    doc = json.loads(raw_manifest.decode('utf-8'))
    if not isinstance(doc, dict) or doc.get('version') != 1 or not isinstance(doc.get('files'), list):
        raise ValueError('Invalid AI output manifest')
    files = doc['files']
    if not files or len(files) > MAX_FILES:
        raise ValueError('Invalid number of AI artifacts')
    names = set()
    total = 0
    package = io.BytesIO()
    with zipfile.ZipFile(package, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in files:
            if not isinstance(entry, dict):
                raise ValueError('Invalid artifact entry')
            name = entry.get('name')
            if not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or name.casefold() in names or name.startswith('.') or name.casefold() == 'manifest.json':
                raise ValueError('Unsafe or duplicate AI artifact name')
            names.add(name.casefold())
            media = entry.get('type')
            if media not in {'audio/wav', 'application/json', 'text/plain'}:
                raise ValueError('Unsupported AI artifact type')
            if media == 'audio/wav' and not name.endswith('.wav'):
                raise ValueError('WAV file extension required')
            if media == 'application/json' and not name.endswith('.json'):
                raise ValueError('JSON file extension required')
            if media == 'text/plain' and not name.endswith('.txt'):
                raise ValueError('Text file extension required')
            remaining = MAX_ARTIFACT_BYTES - total
            data = _read_private_file(directory / name, remaining)
            total += len(data)
            digest = entry.get('sha256')
            if digest is not None:
                if (not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)
                        or hashlib.sha256(data).hexdigest() != digest):
                    raise ValueError('AI artifact manifest checksum mismatch')
            if media == 'audio/wav':
                _verify_wav_bytes(data)
            elif media == 'application/json':
                json.loads(data.decode('utf-8'))
            archive.writestr(name, data)
        archive.writestr('manifest.json', json.dumps(doc, separators=(',', ':'), ensure_ascii=False))
    if package.tell() > MAX_ARTIFACT_BYTES:
        raise ValueError('AI archive exceeds size limit')
    return package.getvalue(), 'application/zip'


def _verify_wav_bytes(data: bytes) -> None:
    """Validate exactly the WAV bytes that are returned or archived."""
    if len(data) < 44:
        raise ValueError('Invalid AI WAV size')
    try:
        with wave.open(io.BytesIO(data), 'rb') as wav:
            channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
            width = wav.getsampwidth()
            if channels not in (1, 2) or rate not in (44100, 48000, 96000):
                raise ValueError('Unsupported AI WAV format')
            if width not in (2, 3, 4) or frames == 0 or frames > rate * 60 * 30:
                raise ValueError('Invalid AI WAV frames')
            if wav.getcomptype() != 'NONE':
                raise ValueError('Invalid or truncated AI WAV')
            if len(wav.readframes(frames)) != frames * channels * width:
                raise ValueError('Invalid or truncated AI WAV')
    except (EOFError, wave.Error) as exc:
        raise ValueError('Invalid AI WAV') from exc
