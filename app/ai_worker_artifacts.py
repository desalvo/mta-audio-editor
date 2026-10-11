"""Validated multi-artifact output for the fixed AI worker subprocess protocol.

An adapter writes output.wav (legacy) OR output.manifest.json plus named files
into its private job directory. Never accept paths chosen by an API caller.
"""
from __future__ import annotations
import io
import json
import re
import zipfile
from pathlib import Path

MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_FILES = 16
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def package_artifacts(directory: Path) -> tuple[bytes, str]:
    """Return validated ZIP or legacy WAV; disallow traversal and symlinks."""
    from .ai_worker_protocol import verify_preview_wav
    manifest_path = directory / 'output.manifest.json'
    if not manifest_path.exists():
        wav = directory / 'preview.wav'
        verify_preview_wav(wav)
        return wav.read_bytes(), 'audio/wav'
    doc = json.loads(manifest_path.read_text(encoding='utf-8'))
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
            if not isinstance(name, str) or not SAFE_NAME.fullmatch(name) or name in names or name.startswith('.'):
                raise ValueError('Unsafe or duplicate AI artifact name')
            names.add(name)
            media = entry.get('type')
            if media not in {'audio/wav', 'application/json', 'text/plain'}:
                raise ValueError('Unsupported AI artifact type')
            if media == 'audio/wav' and not name.endswith('.wav'):
                raise ValueError('WAV file extension required')
            if media == 'application/json' and not name.endswith('.json'):
                raise ValueError('JSON file extension required')
            path = directory / name
            if path.is_symlink() or not path.is_file() or path.parent != directory:
                raise ValueError('Invalid AI artifact location')
            length = path.stat().st_size
            total += length
            if total > MAX_ARTIFACT_BYTES:
                raise ValueError('AI artifacts exceed size limit')
            if media == 'audio/wav':
                verify_preview_wav(path)
            elif media == 'application/json':
                json.loads(path.read_text(encoding='utf-8'))
            archive.write(path, arcname=name)
        archive.writestr('manifest.json', json.dumps(doc, separators=(',', ':'), ensure_ascii=False))
    if package.tell() > MAX_ARTIFACT_BYTES:
        raise ValueError('AI archive exceeds size limit')
    return package.getvalue(), 'application/zip'
