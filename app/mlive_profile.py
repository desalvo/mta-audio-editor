"""Per-user M-Live export settings, isolated from portable projects."""
import re

from . import auth
from .models import DEFAULT_MERISH_SYL_KEY, DEFAULT_MERISH_USER_ID


def _validate(user_id, identifier, key):
    if type(user_id) is not int or user_id < 0:
        raise ValueError('Utente non valido')
    if not isinstance(identifier, str) or not re.fullmatch(r'[0-9]{6}', identifier) or identifier == '000000':
        raise ValueError('L’identificativo M-Live deve contenere sei cifre valide')
    if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{512}', key) or len(set(bytes.fromhex(key))) != 256:
        raise ValueError('Parametro SYL non valido: occorrono 256 byte esadecimali distinti')


def get(user_id):
    if type(user_id) is not int or user_id < 0:
        raise ValueError('Utente non valido')
    with auth.db() as con:
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mlive_user_profiles'").fetchone()
        row = con.execute('SELECT merish_user_id,merish_syl_key FROM mlive_user_profiles WHERE user_id=?', (user_id,)).fetchone() if exists else None
    result = {'merish_user_id': row[0], 'merish_syl_key': row[1]} if row else {
        'merish_user_id': DEFAULT_MERISH_USER_ID, 'merish_syl_key': DEFAULT_MERISH_SYL_KEY}
    _validate(user_id, result['merish_user_id'], result['merish_syl_key'])
    return result


def save(user_id, identifier, key):
    identifier = identifier.strip() if isinstance(identifier, str) else identifier
    key = key.strip().lower() if isinstance(key, str) else key
    _validate(user_id, identifier, key)
    with auth.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS mlive_user_profiles (user_id INTEGER PRIMARY KEY, merish_user_id TEXT NOT NULL, merish_syl_key TEXT NOT NULL)')
        con.execute('INSERT INTO mlive_user_profiles VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET merish_user_id=excluded.merish_user_id,merish_syl_key=excluded.merish_syl_key', (user_id, identifier, key))
    return {'merish_user_id': identifier, 'merish_syl_key': key}


def adopt_legacy(user_id, project):
    """Preserve the first complete, nondefault legacy pair for its owner only."""
    identifier, key = project.merish_user_id, project.merish_syl_key
    if (identifier, key) == (DEFAULT_MERISH_USER_ID, DEFAULT_MERISH_SYL_KEY):
        return
    try:
        _validate(user_id, identifier, key)
    except ValueError:
        return
    with auth.db() as con:
        exists = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mlive_user_profiles'").fetchone()
        if exists and con.execute('SELECT 1 FROM mlive_user_profiles WHERE user_id=?', (user_id,)).fetchone():
            return
    with auth.db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS mlive_user_profiles (user_id INTEGER PRIMARY KEY, merish_user_id TEXT NOT NULL, merish_syl_key TEXT NOT NULL)')
        con.execute('INSERT INTO mlive_user_profiles VALUES (?,?,?) ON CONFLICT(user_id) DO NOTHING', (user_id, identifier, key))


def apply(project, settings):
    """An in-memory export view: no profile data enters project serialization."""
    _validate(0, settings.get('merish_user_id'), settings.get('merish_syl_key'))
    return project.model_copy(deep=True, update=settings)
