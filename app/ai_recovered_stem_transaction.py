"""Crash reconciliation for recovered multi-stem imports.

Call under the cross-process project publication lock. The durable snapshot is
written BEFORE calling upload helpers, so a crash between file creation and
registration is recoverable. Only files absent from the initial snapshot and
still unreferenced in the saved project are eligible for cleanup.
"""
import json
import os
import uuid
from pathlib import Path

from .storage import pdir, load_project

_NAME = '.recovered-stems-pending.json'
_ORPHANS = '.recovered-stems-preserved.json'
_QUARANTINE = '.recovered-stems-quarantine.json'


def _atomic_write(path: Path, document: dict):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('x', encoding='utf-8') as handle:
            os.chmod(tmp, 0o600)
            json.dump(document, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        tmp.unlink(missing_ok=True)


def _listed(directory: Path):
    if directory.is_symlink():
        raise RuntimeError('Unsafe recovered stem media directory')
    if not directory.is_dir():
        return set()
    return {item.name for item in directory.iterdir() if item.is_file() and not item.is_symlink()}


def begin(project_id: str, receipt: str):
    folder = pdir(project_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _NAME
    if path.exists() or path.is_symlink():
        raise RuntimeError('Previous recovered stem transaction requires reconciliation')
    _atomic_write(path, {'version': 1, 'receipt': receipt,
                         'audio_before': sorted(_listed(folder / 'audio')),
                         'originals_before': sorted(_listed(folder / 'originals')),
                         'identities': {}})


def reconcile(project_id: str):
    folder = pdir(project_id)
    path = folder / _NAME
    if not path.exists() and not path.is_symlink():
        return {'recovered': False, 'removed': 0}
    if path.is_symlink():
        raise RuntimeError('Unsafe recovered stem transaction journal')
    document = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(document, dict) or document.get('version') != 1
            or not isinstance(document.get('receipt'), str)):
        raise RuntimeError('Invalid recovered stem transaction journal')
    from .ai_media_identity import validate, matches
    identities = validate(document)
    # New journals require explicitly registered inode ownership before cleanup.
    # Historical journals without this key retain their legacy behavior.
    inode_guarded = 'identities' in document
    project = load_project(project_id)
    committed = document['receipt'] in project.recovered_ai_imports
    referenced = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
    # Preflight the entire journal and both directories before unlinking anything.
    snapshots = {}
    current = {}
    for dirname, before_key in (('audio', 'audio_before'), ('originals', 'originals_before')):
        prior = document.get(before_key)
        if (not isinstance(prior, list) or any(not isinstance(x, str) or not x or
                '/' in x or '\\' in x or '\x00' in x or x in ('.', '..') for x in prior)
                or len(set(prior)) != len(prior)):
            raise RuntimeError('Invalid recovered stem transaction snapshot')
        snapshots[dirname] = set(prior)
        current[dirname] = _listed(folder / dirname)
    removed = 0
    preserved_unowned = 0
    preserved_replaced = 0
    preserved = []
    if not committed:
        for dirname in ('audio', 'originals'):
            for name in current[dirname] - snapshots[dirname]:
                if dirname == 'audio' and name in referenced:
                    continue
                if inode_guarded and f'{dirname}/{name}' not in identities:
                    preserved_unowned += 1
                    preserved.append({'file': f'{dirname}/{name}', 'reason': 'unowned'})
                    continue
                candidate = folder / dirname / name
                if candidate.is_file() and not candidate.is_symlink() and matches(candidate, identities):
                    candidate.unlink()
                    removed += 1
                else:
                    preserved_replaced += 1
                    preserved.append({'file': f'{dirname}/{name}', 'reason': 'identity_changed'})
    # Flush media deletions before durably retiring the journal.
    for directory in (folder / 'audio', folder / 'originals'):
        if directory.is_dir():
            fd = os.open(str(directory), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    # Preserve an operator-readable, durable audit before retiring the journal.
    # A crash after writing this report but before journal retirement can replay
    # safely: the report is rewritten idempotently with the same survivors.
    if preserved:
        report_path = folder / _ORPHANS
        if report_path.is_symlink():
            raise RuntimeError('Unsafe recovered stem preserved report')
        history = []
        if report_path.exists():
            previous = json.loads(report_path.read_text(encoding='utf-8'))
            if (not isinstance(previous, dict) or previous.get('version') != 1
                    or not isinstance(previous.get('items'), list)):
                raise RuntimeError('Invalid recovered stem preserved report')
            history = previous['items']
        existing = {(item['receipt'], item['file'], item['reason']) for item in history
                    if isinstance(item, dict) and all(k in item and isinstance(item[k], str)
                    for k in ('receipt', 'file', 'reason'))}
        for item in preserved:
            row = {'receipt': document['receipt'], **item}
            key = (row['receipt'], row['file'], row['reason'])
            if key not in existing:
                history.append(row)
                existing.add(key)
        _atomic_write(report_path, {'version': 1, 'items': history})
    path.unlink()
    fd = os.open(str(folder), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'recovered': True, 'committed': committed, 'removed': removed,
            'preserved_unowned': preserved_unowned, 'preserved_replaced': preserved_replaced}


def reconcile_on_startup():
    """Reconcile unfinished stem imports for all existing projects at startup.

    Project publication locks serialize against concurrent imports in other
    server processes. Errors remain visible for manual intervention; an
    invalid journal must never authorize destructive cleanup.
    """
    from .storage import ROOT, PID_RE
    from .ai_project_lock import project_publication_lock

    outcome = {'checked': 0, 'recovered': 0, 'removed': 0,
               'preserved_unowned': 0, 'preserved_replaced': 0, 'errors': {}}
    if not ROOT.is_dir():
        return outcome
    for folder in sorted(ROOT.iterdir()):
        if (folder.is_symlink() or not folder.is_dir() or not PID_RE.fullmatch(folder.name)
                or not (folder / 'project.json').is_file()):
            continue
        journal = folder / _NAME
        if not journal.exists() and not journal.is_symlink():
            continue
        outcome['checked'] += 1
        try:
            with project_publication_lock(folder.name):
                result = reconcile(folder.name)
            if result['recovered']:
                outcome['recovered'] += 1
                outcome['removed'] += result['removed']
                outcome['preserved_unowned'] += result['preserved_unowned']
                outcome['preserved_replaced'] += result['preserved_replaced']
        except (ValueError, RuntimeError, OSError, KeyError, TypeError, AttributeError) as exc:
            outcome['errors'][folder.name] = str(exc)[:250]
    return outcome


def review_preserved(project_id: str):
    """Read an operator inventory; never interpret audit entries as delete authority."""
    folder = pdir(project_id)
    path = folder / _ORPHANS
    if path.is_symlink():
        raise RuntimeError('Unsafe recovered stem preserved report')
    if not path.exists():
        return {'version': 1, 'items': []}
    document = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or document.get('version') != 1 or not isinstance(document.get('items'), list):
        raise RuntimeError('Invalid recovered stem preserved report')
    rows = []
    for item in document['items']:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ('receipt', 'file', 'reason')):
            raise RuntimeError('Invalid recovered stem audit item')
        rel = item['file']
        parts = rel.split('/')
        if (len(parts) != 2 or parts[0] not in ('audio', 'originals') or
                parts[1] in ('', '.', '..') or '\\' in parts[1] or '\x00' in parts[1]):
            raise RuntimeError('Invalid recovered stem audit path')
        if item['reason'] not in ('unowned', 'identity_changed'):
            raise RuntimeError('Invalid recovered stem audit reason')
        candidate = folder / rel
        present = candidate.is_file() and not candidate.is_symlink() and not candidate.parent.is_symlink()
        rows.append({**item, 'present': present})
    return {'version': 1, 'items': rows}


def _quarantine_records(folder: Path):
    path = folder / _QUARANTINE
    if path.is_symlink():
        raise RuntimeError('Unsafe quarantine audit')
    if not path.exists():
        return []
    doc = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(doc, dict) or doc.get('version') != 1 or not isinstance(doc.get('items'), list):
        raise RuntimeError('Invalid quarantine audit')
    rows = doc['items']
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or not all(isinstance(row.get(k), str) for k in
                ('receipt', 'file', 'quarantine_name', 'status')) or row['status'] not in ('quarantined', 'restored')
                or '/' in row['quarantine_name'] or '\\' in row['quarantine_name']
                or row['quarantine_name'] in ('', '.', '..') or '\x00' in row['quarantine_name']):
            raise RuntimeError('Invalid quarantine audit item')
        parts = row['file'].split('/')
        if (len(parts) != 2 or parts[0] not in ('audio', 'originals')
                or parts[1] in ('', '.', '..') or '\\' in parts[1] or '\x00' in parts[1]
                or not row['receipt'] or '\x00' in row['receipt']):
            raise RuntimeError('Invalid quarantine audit origin')
        if row['quarantine_name'] in seen:
            raise RuntimeError('Duplicate quarantine audit identity')
        seen.add(row['quarantine_name'])
    return rows


def review_quarantine(project_id: str):
    folder = pdir(project_id)
    rows = _quarantine_records(folder)
    vault = folder / '.recovered-stems-quarantine'
    if vault.is_symlink():
        raise RuntimeError('Unsafe quarantine directory')
    return {'version': 1, 'items': [dict(row, present=(row['status'] == 'quarantined' and
            (vault / row['quarantine_name']).is_file() and
            not (vault / row['quarantine_name']).is_symlink())) for row in rows]}


def restore_quarantined(project_id: str, quarantine_name: str):
    """Restore only an audited quarantined file into its originally reviewed path.

    Must be invoked under the project publication lock. No replacement or overwrite.
    """
    folder = pdir(project_id)
    if (folder / _NAME).exists() or (folder / _NAME).is_symlink():
        raise RuntimeError('Pending recovered stem journal requires reconciliation')
    records = _quarantine_records(folder)
    selected = [r for r in records if r['quarantine_name'] == quarantine_name and r['status'] == 'quarantined']
    if len(selected) != 1:
        raise RuntimeError('Quarantine entry not available')
    row = selected[0]
    # Validate the source path by consulting the original reviewed inventory.
    if not any(r['receipt'] == row['receipt'] and r['file'] == row['file'] for r in review_preserved(project_id)['items']):
        raise RuntimeError('Quarantine origin not audited')
    vault = folder / '.recovered-stems-quarantine'
    src = vault / quarantine_name
    target = folder / row['file']
    project = load_project(project_id)
    referenced = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
    if target.name in referenced:
        raise RuntimeError('Quarantine restore destination is referenced by project')
    if (vault.is_symlink() or src.is_symlink() or not src.is_file()
            or target.parent.is_symlink() or not target.parent.is_dir()
            or target.exists() or target.is_symlink()):
        raise RuntimeError('Unsafe quarantine restore target')
    # Hard-link with exclusive creation, then unlink source: existing targets are never overwritten.
    os.link(src, target, follow_symlinks=False)
    fd = os.open(str(target.parent), os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    updated = [dict(r, status='restored') if r is row else r for r in records]
    try:
        _atomic_write(folder / _QUARANTINE, {'version': 1, 'items': updated})
    except Exception:
        target.unlink(missing_ok=True)
        raise
    src.unlink()
    fd = os.open(str(vault), os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)
    return {'restored': True, 'receipt': row['receipt'], 'file': row['file']}


def quarantine_preserved(project_id: str, receipt: str, relative_path: str):
    """Move one reviewed orphan to an isolated quarantine; never unlink user media.

    Invoke under project_publication_lock, after authenticating project ownership.
    """
    folder = pdir(project_id)
    if (folder / _NAME).exists() or (folder / _NAME).is_symlink():
        raise RuntimeError('Pending recovered stem journal requires reconciliation')
    review = review_preserved(project_id)
    matching = [row for row in review['items'] if row['receipt'] == receipt and row['file'] == relative_path]
    if len(matching) != 1 or not matching[0]['present']:
        raise RuntimeError('Preserved stem audit entry not available')
    src = folder / relative_path
    if src.is_symlink() or src.parent.is_symlink() or not src.is_file():
        raise RuntimeError('Unsafe preserved stem media')
    # Never move media currently referenced in the project's saved state.
    project = load_project(project_id)
    referenced = {t.filename for t in project.tracks} | {c.filename for c in project.clip_library}
    if src.name in referenced:
        raise RuntimeError('Preserved stem media is referenced by project')
    stat_before = src.stat(follow_symlinks=False)
    quarantine = folder / '.recovered-stems-quarantine'
    if quarantine.is_symlink():
        raise RuntimeError('Unsafe preserved stem quarantine')
    quarantine.mkdir(mode=0o700, exist_ok=True)
    # Read and validate the ledger before moving any media. A corrupted audit
    # must not strand the source in quarantine without an indexed record.
    records = _quarantine_records(folder)
    if any(r['receipt'] == receipt and r['file'] == relative_path and r['status'] == 'quarantined' for r in records):
        raise RuntimeError('Preserved stem already quarantined')
    destination = quarantine / (uuid.uuid4().hex + '-' + src.name)
    # Fail closed for concurrent replacement even under a project lock.
    st = src.stat(follow_symlinks=False)
    if (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) != (stat_before.st_dev, stat_before.st_ino, stat_before.st_size, stat_before.st_mtime_ns):
        raise RuntimeError('Preserved stem media changed before quarantine')
    os.rename(src, destination)
    for directory in (src.parent, quarantine):
        fd = os.open(str(directory), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    # Durable quarantine ledger, preserving provenance across process restarts.
    records.append({'receipt': receipt, 'file': relative_path,
                    'quarantine_name': destination.name, 'status': 'quarantined'})
    try:
        _atomic_write(folder / _QUARANTINE, {'version': 1, 'items': records})
    except Exception:
        # Recover the original location when the audit commit fails.
        if not src.exists() and not src.is_symlink():
            os.rename(destination, src)
        raise
    # Do not remove the original audit row.
    return {'quarantined': True, 'receipt': receipt, 'file': relative_path,
            'quarantine_name': destination.name}
