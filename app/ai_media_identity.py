"""Durable inode guards shared by upload recovery journals.

Caller holds the project publication lock when recording ownership. Legacy
receipts without identity entries retain their historical recovery behavior.
"""
import json
import os
import stat
import uuid


def validate(document):
    identities = document.get('identities', {})
    if not isinstance(identities, dict):
        raise RuntimeError('Invalid media identities')
    for key, value in identities.items():
        if (not isinstance(key, str) or key.count('/') != 1 or
                key.split('/')[0] not in ('audio', 'originals') or
                key.split('/')[1] in ('', '.', '..') or '\\' in key or '\x00' in key or
                not isinstance(value, list) or len(value) != 2 or
                any(type(n) is not int or n < 0 for n in value)):
            raise RuntimeError('Invalid media identity entry')
    return identities


def matches(path, identities):
    key = path.parent.name + '/' + path.name
    identity = identities.get(key)
    st = path.lstat()
    return stat.S_ISREG(st.st_mode) and (identity is None or list((st.st_dev, st.st_ino)) == identity)


def record(journal, path):
    if journal.is_symlink() or not journal.is_file():
        raise RuntimeError('Missing or unsafe media journal')
    document = json.loads(journal.read_text(encoding='utf-8'))
    identities = validate(document)
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode):
        raise RuntimeError('Unsafe owned media')
    key = path.parent.name + '/' + path.name
    identity = [st.st_dev, st.st_ino]
    if key in identities and identities[key] != identity:
        raise RuntimeError('Owned media was replaced during import')
    identities[key] = identity
    document['identities'] = identities
    temporary = journal.with_name(journal.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as out:
            os.chmod(temporary, 0o600)
            json.dump(document, out, sort_keys=True)
            out.flush(); os.fsync(out.fileno())
        os.replace(temporary, journal)
        if os.name != 'nt':
            fd = os.open(str(journal.parent), os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


def record_upload(pid, path):
    from .storage import pdir
    folder = pdir(pid)
    for name in ('.ordinary-upload-pending.json', '.recovered-stems-pending.json'):
        journal = folder / name
        if journal.exists() or journal.is_symlink():
            record(journal, path)
