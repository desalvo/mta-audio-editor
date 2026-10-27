"""Sample only dedicated per-user persistent AI data, never host filesystem metrics.

Configure MTA_AI_USER_STORAGE_ROOT to an administrator-controlled directory whose
immediate subdirectories are numeric MTA user IDs. Disabled unless configured.
Missing user directory is zero usage; inaccessible roots fail closed.
"""
from __future__ import annotations

import os
from pathlib import Path
from .auth import db
from . import ai_billing


from .service_admission import admitted

@admitted('storage-sampling')
def sample_all(*, root=None, sampled_at=None):
    configured = root if root is not None else os.getenv('MTA_AI_USER_STORAGE_ROOT', '')
    if not configured:
        return {'enabled': False, 'samples': 0}
    base = Path(configured)
    if not base.is_absolute() or not base.is_dir() or base.is_symlink():
        raise ValueError('Storage sampling root must be an existing, real absolute directory')
    with db() as c:
        users = [int(row[0]) for row in c.execute('SELECT id FROM users WHERE active=1')]
    count = 0
    for uid in users:
        user_dir = base / str(uid)
        if user_dir.is_symlink():
            raise ValueError('Symlinked user storage directory not permitted')
        if user_dir.exists():
            if not user_dir.is_dir():
                raise ValueError('User storage path must be a directory')
            ai_billing.measure_persistent_directory(uid, user_dir, sampled_at=sampled_at)
        else:
            ai_billing.record_persistent_storage(uid, 0, sampled_at=sampled_at)
        count += 1
    return {'enabled': True, 'samples': count}


def main():
    import json
    print(json.dumps(sample_all(), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
