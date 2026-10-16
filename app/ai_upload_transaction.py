"""Recover ordinary track upload/replace file writes after process termination.

The caller MUST hold project_publication_lock from begin through commit/finish.
Only files absent at begin and unreferenced by the persisted project are removed.
"""
import json
import os
import uuid
from .storage import pdir, load_project

NAME = '.ordinary-upload-pending.json'

def _names(path):
    if path.is_symlink():
        raise RuntimeError('Unsafe upload media directory')
    return {p.name for p in path.iterdir() if p.is_file() and not p.is_symlink()} if path.is_dir() else set()

def _sync_dir(path):
    # Windows cannot open directories with the POSIX os.open API. File fsync
    # and atomic replacement remain mandatory; Linux directory fsync is unchanged.
    if os.name == 'nt': return
    fd = os.open(str(path), os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def begin(pid):
    folder = pdir(pid)
    path = folder / NAME
    if path.exists() or path.is_symlink():
        reconcile(pid)
    data = {'version': 1, 'audio_before': sorted(_names(folder / 'audio')),
            'originals_before': sorted(_names(folder / 'originals'))}
    tmp = folder / (NAME + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('x', encoding='utf-8') as out:
            os.chmod(tmp, 0o600)
            json.dump(data, out, sort_keys=True)
            out.flush(); os.fsync(out.fileno())
        os.replace(tmp, path)
        _sync_dir(folder)
    finally:
        tmp.unlink(missing_ok=True)

def reconcile(pid):
    folder = pdir(pid)
    path = folder / NAME
    if not path.exists() and not path.is_symlink():
        return {'recovered': False, 'removed': 0}
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Unsafe ordinary upload journal')
    # A malformed journal never authorizes deletion.
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or obj.get('version') != 1:
        raise RuntimeError('Invalid ordinary upload journal')
    snapshots = {}
    for key in ('audio_before', 'originals_before'):
        values = obj.get(key)
        if (not isinstance(values, list) or any(not isinstance(s, str) or not s or '\x00' in s or '/' in s or '\\' in s or s in ('.','..') for s in values)
                or len(set(values)) != len(values)):
            raise RuntimeError('Invalid ordinary upload snapshot')
        snapshots[key] = set(values)
    from .ai_media_identity import validate, matches
    identities = validate(obj)
    project = load_project(pid)
    referenced = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
    removed = 0
    # Validate both media roots before the first destructive operation.
    audio_names = _names(folder / 'audio')
    original_names = _names(folder / 'originals')
    audio_new = audio_names - snapshots['audio_before']
    committed = bool(audio_new & referenced)
    for name in audio_new - referenced:
        item = folder / 'audio' / name
        if item.is_file() and not item.is_symlink() and matches(item, identities):
            item.unlink(); removed += 1
    # Originals have no project-level reference; only remove if transaction did not commit.
    if not committed:
        for name in original_names - snapshots['originals_before']:
            item = folder / 'originals' / name
            if item.is_file() and not item.is_symlink() and matches(item, identities):
                item.unlink(); removed += 1
    for directory in (folder / 'audio', folder / 'originals'):
        if directory.is_dir():
            _sync_dir(directory)
    path.unlink(); _sync_dir(folder)
    return {'recovered': True, 'removed': removed, 'committed': committed}

def finish(pid):
    return reconcile(pid)

def reconcile_on_startup():
    from .storage import ROOT, PID_RE
    from .ai_project_lock import project_publication_lock
    result = {'checked': 0, 'recovered': 0, 'removed': 0, 'errors': {}}
    if not ROOT.is_dir(): return result
    for folder in ROOT.iterdir():
        if (folder.is_symlink() or not folder.is_dir() or not PID_RE.fullmatch(folder.name)
                or not (folder / 'project.json').is_file()): continue
        if not (folder / NAME).exists() and not (folder / NAME).is_symlink(): continue
        result['checked'] += 1
        try:
            with project_publication_lock(folder.name):
                rec = reconcile(folder.name)
            result['recovered'] += int(rec['recovered'])
            result['removed'] += rec['removed']
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, AttributeError, json.JSONDecodeError) as exc:
            result['errors'][folder.name] = str(exc)[:250]
    return result
