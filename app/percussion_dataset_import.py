"""Strict import of administrator-declared audio benchmark datasets.

A rights acknowledgement records the administrator's declaration. It does not
verify copyright ownership and never grants model rights or quality approval.
"""
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile

import numpy as np
import soundfile as sf

from . import percussion_corpus as corpus

MAX_COMPRESSED_BYTES = 256 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_FILES = 2048
_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')
_RESERVED_NAMES = frozenset({'con', 'prn', 'aux', 'nul', *(f'com{n}' for n in range(1, 10)),
                            *(f'lpt{n}' for n in range(1, 10))})
_AUTHORITY_FIELDS = frozenset({'approval', 'professional_approval', 'human_approval', 'release_approved',
                               'approved_manually', 'benchmark_results', 'technical_pass'})


def _name(value, *, directory=False):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or unicodedata.normalize('NFC', value) != value or len(value.encode('utf-8')) > 240
            or any(unicodedata.category(ch) in ('Cc', 'Cf') for ch in value)):
        raise ValueError('Non-canonical dataset archive path')
    if directory:
        value = value[:-1]
    parts = PurePosixPath(value)
    if (parts.is_absolute() or not parts.parts or any(not part or part in ('.', '..') for part in value.split('/'))
            or len(parts.parts) > 8):
        raise ValueError('Dataset archive path escapes its root')
    for part in parts.parts:
        if (part[-1:] in ('.', ' ') or any(ch in part for ch in '<>:"|?*')
                or part.split('.', 1)[0].casefold() in _RESERVED_NAMES):
            raise ValueError('Dataset archive path is not portable')
    return value


def _json(payload):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON manifest key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Non-finite JSON manifest value')
    try:
        value = json.loads(payload.decode('utf-8'), object_pairs_hook=object_pairs, parse_constant=constant)
        # Exponent overflow such as 1e999 is not handled by parse_constant.
        json.dumps(value, allow_nan=False)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise ValueError('Invalid dataset manifest JSON') from exc
    pending = [(value, 0)]; visited = 0
    while pending:
        node, depth = pending.pop(); visited += 1
        if depth > 16 or visited > 100_000:
            raise ValueError('Dataset manifest structure exceeds limits')
        if isinstance(node, dict):
            pending.extend((child, depth + 1) for child in node.values())
        elif isinstance(node, list):
            pending.extend((child, depth + 1) for child in node)
        elif isinstance(node, str) and len(node) > 8192:
            raise ValueError('Dataset manifest string exceeds limits')
    return value


def _rights(case):
    rights = case.get('rights')
    if not isinstance(rights, dict):
        raise ValueError('Prepared real cases require explicit rights provenance')
    basis = rights.get('basis')
    source = rights.get('source')
    if basis not in ('user_owned', 'licensed') or not isinstance(source, str) or not 8 <= len(source.strip()) <= 2000:
        raise ValueError('Real recording rights require an ownership/licence basis and source provenance')
    normalized = {'basis': basis, 'source': source.strip()}
    if basis == 'licensed':
        for key in ('license', 'evidence'):
            value = rights.get(key)
            if not isinstance(value, str) or not 3 <= len(value.strip()) <= 2000:
                raise ValueError('Licensed recordings require licence identification and permission evidence')
            normalized[key] = value.strip()
    for key in ('attribution', 'permission'):
        if key in rights:
            if not isinstance(rights[key], str) or len(rights[key]) > 2000:
                raise ValueError('Invalid rights provenance field')
            normalized[key] = rights[key]
    # A supplied reviewed_by/verified/approved field is not server authority.
    return normalized


def archive_identifier(data: bytes):
    """Read a bounded, unambiguous manifest ID before choosing its destination.

    This performs no writes and is not a substitute for import_archive validation.
    """
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_COMPRESSED_BYTES:
        raise ValueError('Dataset archive exceeds the compressed byte limit or is empty')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= MAX_FILES or sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError('Dataset archive file count or uncompressed size exceeds limits')
            aliases = set(); manifest = None
            for info in infos:
                if info.orig_filename != info.filename:
                    raise ValueError('Non-canonical original dataset archive path')
                name = _name(info.filename, directory=info.is_dir())
                if name.casefold() in aliases:
                    raise ValueError('Duplicate or case-colliding dataset archive path')
                aliases.add(name.casefold())
                if name == 'manifest.json' and not info.is_dir():
                    manifest = info
            if manifest is None or manifest.file_size > corpus.MAX_MANIFEST_BYTES:
                raise ValueError('Dataset manifest is absent or oversized')
            value = _json(archive.read(manifest))
            if (not isinstance(value, dict) or value.get('schema') != corpus.CORPUS_VERSION
                    or not isinstance(value.get('id'), str) or not _ID.fullmatch(value['id'])):
                raise ValueError('Invalid dataset manifest identifier or schema')
            return value['id']
    except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        raise ValueError('Dataset manifest cannot be read') from exc


def _manifest(value, dataset_id):
    if (not isinstance(value, dict) or value.get('schema') != corpus.CORPUS_VERSION
            or value.get('id') != dataset_id or not isinstance(value.get('cases'), list)
            or not 1 <= len(value['cases']) <= 512):
        raise ValueError('Dataset schema or destination identifier mismatch')
    # Corpus manifests contain data and provenance, not imported acceptance.
    for field in _AUTHORITY_FIELDS:
        value.pop(field, None)
    registered = set(); hash_splits = {}
    for case in value['cases']:
        if not isinstance(case, dict):
            raise ValueError('Invalid corpus case')
        for field in _AUTHORITY_FIELDS:
            case.pop(field, None)
        if type(case.get('prepared')) is not bool:
            raise ValueError('Corpus case availability must be explicit')
        if not case['prepared']:
            continue
        if case.get('group') == 'real':
            case['rights'] = _rights(case)
        hashes = case.get('sha256')
        if not isinstance(hashes, dict) or not 1 <= len(hashes) <= 96:
            raise ValueError('Prepared corpus files require SHA-256 registration')
        for relative, digest in hashes.items():
            canonical = _name(relative)
            if not canonical.lower().endswith('.wav'):
                raise ValueError('Only registered WAV audio files can be imported')
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('Invalid registered corpus SHA-256')
            registered.add(canonical)
            previous = hash_splits.setdefault(digest, case.get('split'))
            if previous != case.get('split'):
                raise ValueError('Byte-identical source recordings cannot cross corpus splits')
    if not registered:
        raise ValueError('Imported dataset has no prepared audio')
    if len(registered) + 1 > MAX_FILES:
        raise ValueError('Dataset contains too many files')
    return registered


def _audio(path):
    info = sf.info(path)
    if (info.format not in ('WAV', 'WAVEX', 'RF64') or not 1 <= info.channels <= 8
            or not 8000 <= info.samplerate <= 192000 or info.frames <= 0):
        raise ValueError('Dataset audio is not a supported WAV recording')
    decoded = 0
    with sf.SoundFile(path) as stream:
        for block in stream.blocks(blocksize=65536, dtype='float64', always_2d=True):
            decoded += len(block)
            if not np.isfinite(block).all():
                raise ValueError('Dataset audio contains NaN or Inf')
    if decoded != info.frames:
        raise ValueError('Dataset audio is truncated')


def _check_parent(path):
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('Dataset destination must not include symlinks')


def import_archive(data: bytes, dataset_root: Path, actor: int, acknowledge_rights: bool):
    """Validate completely, reserve a new directory, then publish manifest last.

    Existing files/directories are never replaced. An administrator explicitly
    acknowledges all uploaded audio rights; per-real-case provenance is required.
    """
    if type(actor) is not int or not 0 < actor < 2 ** 63 or acknowledge_rights is not True:
        raise ValueError('An authenticated administrator and explicit audio-rights acknowledgement are required')
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_COMPRESSED_BYTES:
        raise ValueError('Dataset archive exceeds the compressed byte limit or is empty')
    dataset_root = Path(dataset_root)
    if not dataset_root.is_absolute() or not _ID.fullmatch(dataset_root.name):
        raise ValueError('Dataset destination requires an absolute path and safe identifier')
    _check_parent(dataset_root)
    if dataset_root.exists():
        raise ValueError('Dataset already exists; imports never overwrite it')
    dataset_root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _check_parent(dataset_root)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError('Invalid dataset ZIP archive') from exc
    with archive, tempfile.TemporaryDirectory(prefix='.dataset-import-', dir=dataset_root.parent) as work:
        stage = Path(work)
        infos = archive.infolist()
        if not 1 <= len(infos) <= MAX_FILES:
            raise ValueError('Dataset archive file count exceeds limits')
        entries = {}; aliases = set(); directories = set(); declared = 0
        for info in infos:
            if info.orig_filename != info.filename:
                raise ValueError('Non-canonical original dataset archive path')
            directory = info.is_dir()
            name = _name(info.filename, directory=directory)
            alias = name.casefold()
            if alias in aliases:
                raise ValueError('Duplicate or case-colliding dataset archive path')
            aliases.add(alias)
            kind = stat.S_IFMT(info.external_attr >> 16)
            if (kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or directory and kind == stat.S_IFREG
                    or not directory and kind == stat.S_IFDIR
                    or info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError('Dataset archive contains a link, special file, encryption or unsupported compression')
            if directory:
                directories.add(name)
                if info.file_size:
                    raise ValueError('Directory archive entry has file content')
                continue
            declared += info.file_size
            if info.file_size < 0 or declared > MAX_UNCOMPRESSED_BYTES:
                raise ValueError('Dataset archive exceeds the uncompressed byte limit')
            entries[name] = info
        if 'manifest.json' not in entries or entries['manifest.json'].file_size > corpus.MAX_MANIFEST_BYTES:
            raise ValueError('Dataset manifest is absent or oversized')
        file_aliases = {name.casefold() for name in entries}
        if any(parent.as_posix().casefold() in file_aliases for name in entries
               for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise ValueError('Dataset file and directory paths collide')
        try:
            manifest = _json(archive.read(entries['manifest.json']))
            registered = _manifest(manifest, dataset_root.name)
        except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
            raise ValueError('Dataset manifest cannot be read') from exc
        if set(entries) != registered | {'manifest.json'}:
            raise ValueError('Archive files must exactly match the registered WAV manifest')
        expected_directories = {parent.as_posix() for name in registered for parent in PurePosixPath(name).parents if str(parent) != '.'}
        if not directories <= expected_directories:
            raise ValueError('Unregistered directory in dataset archive')
        extracted = 0
        try:
            for name in sorted(registered):
                info = entries[name]
                path = stage.joinpath(*PurePosixPath(name).parts)
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.open(info) as source, path.open('xb') as target:
                    os.chmod(path, 0o600)
                    size = 0
                    while chunk := source.read(65536):
                        size += len(chunk); extracted += len(chunk)
                        if size > info.file_size or extracted + entries['manifest.json'].file_size > MAX_UNCOMPRESSED_BYTES:
                            raise ValueError('Actual dataset decompression exceeds its declared limits')
                        target.write(chunk)
                    if size != info.file_size:
                        raise ValueError('Dataset archive file is truncated')
                _audio(path)
        except (zipfile.BadZipFile, RuntimeError, EOFError, sf.LibsndfileError) as exc:
            raise ValueError('Invalid or damaged dataset audio') from exc
        manifest['import_record'] = {
            'actor_user_id': actor, 'acknowledged_audio_rights': True,
            'recorded_at': datetime.now(timezone.utc).isoformat(),
            'archive_sha256': hashlib.sha256(data).hexdigest(),
            'declaration_only': True, 'automated_rights_verification': False,
            'professional_quality_approval': False,
        }
        (stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        corpus.load(stage)
        # mkdir is the no-overwrite reservation, including empty directories.
        # No reader can open a partially copied corpus: manifest is committed last.
        _check_parent(dataset_root)
        try:
            dataset_root.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise ValueError('Dataset already exists; imports never overwrite it') from exc
        owned = dataset_root.stat()
        published = False
        try:
            for child in stage.iterdir():
                if child.name != 'manifest.json':
                    child.rename(dataset_root / child.name)
            os.replace(stage / 'manifest.json', dataset_root / 'manifest.json')
            published = True
        finally:
            if not published and not dataset_root.is_symlink() and dataset_root.exists():
                current = dataset_root.stat()
                if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino):
                    shutil.rmtree(dataset_root)
        return manifest

