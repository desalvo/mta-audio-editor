"""Local-authority cross-process service lease for administrative maintenance.

This is a local POSIX deployment protocol, not a network filesystem/HA lock.
Every server replica must run this build against the same local data root.
No lease timeout, PID guess or stale-file deletion grants exclusive access.
"""
from contextlib import contextmanager
import os
import sqlite3
import stat
import threading

from .regime_operation_fence import FenceBlocked

_OWNER = threading.local()
MODE = 'local-authority-v1'


def enabled():
    return os.getenv('MTA_REGIME_CUTOVER', 'off') == MODE and os.name == 'posix'


def _path():
    from . import auth
    return auth.data_root() / 'regime-service.lock'


def _owns_lease():
    return getattr(_OWNER, 'value', None) == (os.getpid(), threading.get_ident(), str(_path()))


@contextmanager
def lease(*, exclusive=False):
    """Nonblocking flock; held through the entire transaction/request lifetime."""
    if os.name != 'posix':
        if exclusive:
            raise FenceBlocked('Cutover requires a local POSIX authority')
        yield
        return
    import fcntl
    path = _path()
    owner = (os.getpid(), threading.get_ident(), str(path))
    if getattr(_OWNER, 'value', None) == owner:
        if exclusive:
            raise FenceBlocked('Nested exclusive cutover refused')
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                (info.st_dev, info.st_ino) != (path.stat().st_dev, path.stat().st_ino)):
            raise FenceBlocked('Unsafe service lease inode')
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise FenceBlocked('Service activity or another cutover holds the lease') from exc
        if exclusive:
            _OWNER.value = owner
        try:
            yield
        finally:
            if exclusive:
                _OWNER.value = None
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def fence_held():
    """Read durable barrier without entering the accounting connection factory."""
    from . import auth
    path = auth.db_path()
    if not path.exists():
        return False
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)
    try:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='regime_admin_cutovers'").fetchone():
            return False
        row = con.execute('SELECT transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
        if row is None:
            raise FenceBlocked('Service barrier state unavailable')
        return bool(row[0]) or bool(con.execute("SELECT 1 FROM regime_admin_cutovers WHERE phase!='finalized' LIMIT 1").fetchone())
    finally:
        con.close()


class _Connection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        self._service_lease = lease()
        self._service_lease.__enter__()
        try:
            super().__init__(*args, **kwargs)
            # An interrupted cutover outlives the flock. New non-owner database
            # connections may inspect it, but cannot mutate any financial/schema
            # state. Login/session operations remain available for recovery.
            if not _owns_lease() and fence_held():
                writes = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
                ddl = {sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_CREATE_TABLE,
                       sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW,
                       sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TABLE,
                       sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_DROP_VIEW,
                       sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH}
                def authorize(action, table, column, database, source):
                    login_write = table == 'sessions' or (table == 'users' and action == sqlite3.SQLITE_UPDATE
                        and column in {'last_login_at', 'updated_at', 'browser_language'})
                    if action in ddl or (action in writes and not login_write):
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK
                self.set_authorizer(authorize)
        except BaseException:
            self.close()
            raise

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

    def close(self):
        try:
            super().close()
        finally:
            active = self._service_lease
            self._service_lease = None
            if active is not None:
                active.__exit__(None, None, None)


def connect(*args, **kwargs):
    return sqlite3.connect(*args, factory=_Connection, **kwargs)


class ServiceLeaseMiddleware:
    """Cover full ASGI response/background lifetime, including streaming/errors."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope.get('path', '')
        if path.startswith('/api/admin/service-regime/cutovers'):
            return await self.app(scope, receive, send)
        active = lease()
        entered = False
        try:
            active.__enter__()
            entered = True
            recovery_read = (scope['method'] in {'GET', 'HEAD'} and
                (path.startswith(('/api/admin/', '/static/')) or path in {'/settings', '/login'}))
            login = path == '/login' and scope['method'] == 'POST'
            if fence_held() and not (recovery_read or login):
                raise FenceBlocked('Service cutover requires administrative recovery')
        except FenceBlocked:
            if entered:
                active.__exit__(None, None, None)
            from starlette.responses import JSONResponse
            response = JSONResponse({'detail': 'Service maintenance in progress; retry after administrative recovery'},
                                    status_code=503, headers={'Retry-After': '5', 'Cache-Control': 'no-store'})
            return await response(scope, receive, send)
        try:
            return await self.app(scope, receive, send)
        finally:
            active.__exit__(None, None, None)
