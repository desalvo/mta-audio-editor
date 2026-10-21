"""Per-job crash recovery for asynchronous track uploads.

The caller holds project_publication_lock while creating/finishing receipts.
Only exact predeclared, newly created audio paths can be deleted; unrelated
files from concurrent project writers are never swept.
"""
from .fs_durability import sync_directory
import json
import os
import re
import shutil
from pathlib import Path
from .storage import pdir, load_project

_PREFIX = '.async-track-'
_SUFFIX = '.pending.json'
_JOB = re.compile(r'^[a-f0-9]{16}$')


def _receipt(pid, job):
    if not _JOB.fullmatch(job):
        raise ValueError('Invalid async track job identity')
    return pdir(pid) / (_PREFIX + job + _SUFFIX)


def begin(pid, job, filename):
    if not isinstance(filename, str) or not re.fullmatch(r'[a-f0-9]{10}\.[a-zA-Z0-9]{1,12}', filename):
        raise ValueError('Invalid async track audio filename')
    folder = pdir(pid)
    audio = folder / 'audio'
    variants = [filename] + [Path(filename).stem + '-sr' + str(rate) + '.wav' for rate in (44100, 48000, 96000)]
    if any((audio / name).exists() or (audio / name).is_symlink() for name in variants):
        raise RuntimeError('Async upload destination already exists')
    path = _receipt(pid, job)
    if path.exists() or path.is_symlink():
        raise RuntimeError('Async track receipt already exists')
    obj = {'version': 1, 'files': variants}
    with path.open('x', encoding='utf-8') as out:
        os.chmod(path, 0o600)
        json.dump(obj, out, sort_keys=True)
        out.flush(); os.fsync(out.fileno())
    _fsync(folder)


def _fsync(directory):
    sync_directory(directory)



def preserve_job_original(pid, job, source, original_name):
    """Predeclare and durably copy a per-job original, never overwriting another file.

    Caller holds the shared project lock. A crash during the copy leaves a
    discoverable path which reconciliation can safely remove if uncommitted.
    """
    from .storage import find_duplicate_project_file, original_path, _unique_original_name
    duplicate = find_duplicate_project_file(pid, source)
    if duplicate and duplicate['category'] == 'original':
        return original_path(pid, duplicate['name'])
    name = _unique_original_name(pid, original_name)
    if not isinstance(name, str) or not re.fullmatch(r'[^/\\\x00]{1,240}', name) or name in {'.', '..'}:
        raise ValueError('Invalid original filename')
    receipt = _receipt(pid, job)
    if receipt.is_symlink() or not receipt.is_file():
        raise RuntimeError('Missing or unsafe async upload receipt')
    obj = json.loads(receipt.read_text(encoding='utf-8'))
    if obj.get('version') != 1 or obj.get('originals'):
        raise RuntimeError('Unexpected async upload receipt state')
    dst = original_path(pid, name)
    if dst.exists() or dst.is_symlink():
        raise RuntimeError('Async original destination exists')
    obj['version'] = 2
    obj['originals'] = [name]
    temporary = receipt.with_name(receipt.name + '.writing')
    try:
        with temporary.open('x', encoding='utf-8') as out:
            os.chmod(temporary, 0o600)
            json.dump(obj, out, sort_keys=True)
            out.flush(); os.fsync(out.fileno())
        os.replace(temporary, receipt)
        _fsync(receipt.parent)
    finally:
        temporary.unlink(missing_ok=True)
    with source.open('rb') as inp, dst.open('xb') as out:
        from .ai_media_identity import record
        record(receipt, dst)
        shutil.copyfileobj(inp, out)
        out.flush(); os.fsync(out.fileno())
    _fsync(dst.parent)
    return dst


def reconcile(pid, job):
    path = _receipt(pid, job)
    if not path.exists() and not path.is_symlink():
        return {'recovered': False, 'removed': 0}
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Unsafe async track receipt')
    obj = json.loads(path.read_text(encoding='utf-8'))
    names = obj.get('files') if isinstance(obj, dict) and obj.get('version') in (1, 2) else None
    if (not isinstance(names, list) or len(names) != 4 or len(set(names)) != 4
        or any(not isinstance(name, str) or not re.fullmatch(r'[a-f0-9]{10}(?:-sr(?:44100|48000|96000))?\.(?:[a-zA-Z0-9]{1,12})', name) for name in names)
        or any(name != (Path(names[0]).stem + '-sr' + str(rate) + '.wav') for name, rate in zip(names[1:], (44100, 48000, 96000)))):
        raise RuntimeError('Invalid async track receipt')
    originals = obj.get('originals', [])
    if (not isinstance(originals, list) or len(originals) > 1 or
        any(not isinstance(n, str) or not re.fullmatch(r'[^/\\\x00]{1,240}', n) or n in {'.', '..'} for n in originals) or
        (obj['version'] == 2 and len(originals) != 1) or
        (obj['version'] == 1 and originals)):
        raise RuntimeError('Invalid async original receipt')
    for dirname in ('audio', 'originals'):
        if (pdir(pid) / dirname).is_symlink():
            raise RuntimeError('Unsafe async upload media directory')
    from .ai_media_identity import validate, matches
    identities = validate(obj)
    project = load_project(pid)
    referenced = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
    removed = 0
    for name in names:
        if name in referenced:
            continue
        target = pdir(pid) / 'audio' / name
        if target.is_file() and not target.is_symlink() and matches(target, identities):
            target.unlink(); removed += 1
    # Originals are retained for successfully committed imports. An uncommitted
    # import owns only the explicitly predeclared original path.
    if not any(n in referenced for n in names):
        for original in originals:
            target = pdir(pid) / 'originals' / original
            if target.is_file() and not target.is_symlink() and matches(target, identities):
                target.unlink(); removed += 1
    for dirname in ('audio', 'originals'):
        directory = pdir(pid) / dirname
        if directory.is_dir():
            _fsync(directory)
    path.unlink()
    _fsync(path.parent)
    return {'recovered': True, 'removed': removed}


def reconcile_on_startup():
    from .storage import ROOT, PID_RE
    from .ai_project_lock import project_publication_lock
    report = {'checked': 0, 'recovered': 0, 'removed': 0, 'errors': {}}
    if not ROOT.is_dir():
        return report
    for folder in ROOT.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not PID_RE.fullmatch(folder.name) or not (folder / 'project.json').is_file():
            continue
        for path in folder.glob(_PREFIX + '*' + _SUFFIX):
            job = path.name[len(_PREFIX):-len(_SUFFIX)]
            report['checked'] += 1
            try:
                with project_publication_lock(folder.name):
                    result = reconcile(folder.name, job)
                report['recovered'] += int(result['recovered'])
                report['removed'] += result['removed']
            except (ValueError, RuntimeError, OSError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
                report['errors'][folder.name + '/' + job] = str(exc)[:250]
    return report
