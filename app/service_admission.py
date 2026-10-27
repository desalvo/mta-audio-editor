"""Durable service admission/drain for one pinned authority and HTTPS workers.

The authority's journal is local SQLite, never a worker-mounted database or an
HA lease. Lost processes do not expire admissions or certify worker quiescence.
"""
from contextlib import contextmanager, closing
from contextvars import ContextVar
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import threading
import time

from .regime_operation_fence import FenceBlocked

MODE = 'authority-v1'
_CURRENT = ContextVar('mta_service_admission', default=None)
_CONTROL = ContextVar('mta_service_control', default=False)
_SCHEMA = '''
CREATE TABLE state(singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 generation INTEGER NOT NULL,phase TEXT NOT NULL CHECK(phase IN ('open','draining')),
 build TEXT NOT NULL,instance TEXT NOT NULL,drain_id TEXT);
CREATE TABLE admissions(id TEXT PRIMARY KEY,nonce TEXT NOT NULL,source TEXT NOT NULL,
 parent TEXT,generation INTEGER NOT NULL,pid INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('open','closed')),created REAL NOT NULL,closed REAL);
CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT,drain_id TEXT NOT NULL,
 action TEXT NOT NULL CHECK(action IN ('begin','resume','upgrade')),actor INTEGER NOT NULL,
 generation INTEGER NOT NULL,created REAL NOT NULL);
CREATE TRIGGER immutable_admission BEFORE UPDATE ON admissions WHEN
 OLD.id IS NOT NEW.id OR OLD.nonce IS NOT NEW.nonce OR OLD.source IS NOT NEW.source OR
 OLD.parent IS NOT NEW.parent OR OLD.generation IS NOT NEW.generation OR OLD.pid IS NOT NEW.pid OR
 OLD.created IS NOT NEW.created OR OLD.state!='open' OR NEW.state!='closed' OR NEW.closed IS NULL
 BEGIN SELECT RAISE(ABORT,'Immutable service admission'); END;
CREATE TRIGGER no_admission_delete BEFORE DELETE ON admissions
 BEGIN SELECT RAISE(ABORT,'Immutable service admission'); END;
CREATE TRIGGER no_event_update BEFORE UPDATE ON events
 BEGIN SELECT RAISE(ABORT,'Immutable service drain event'); END;
CREATE TRIGGER no_event_delete BEFORE DELETE ON events
 BEGIN SELECT RAISE(ABORT,'Immutable service drain event'); END;
CREATE INDEX active_admissions ON admissions(state);
'''


def path():
    from .auth import data_root
    return data_root() / 'service-admission.sqlite3'


def active():
    setting = os.getenv('MTA_SERVICE_ADMISSION', 'off')
    if setting not in ('off', MODE):
        raise FenceBlocked('Unknown service admission protocol')
    return setting == MODE or path().exists() or path().is_symlink() or path().with_suffix('.instance').exists()


@lru_cache(maxsize=1)
def build():
    # Pin the actual participating implementation, not mutable VERSION/build text.
    root = Path(__file__).parent
    sources = sorted(root.rglob('*.py'))
    if not sources or any(p.is_symlink() for p in sources):
        raise FenceBlocked('Complete authority source inventory required')
    return hashlib.sha256(b''.join(p.relative_to(root).as_posix().encode()+b'\0'+p.read_bytes() for p in sources)).hexdigest()


def _schema_rows(con):
    return tuple(tuple(row) for row in con.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'))


@lru_cache(maxsize=1)
def _expected_schema():
    # Construct only the fixed bundled schema,never SQL from a restored archive.
    with closing(sqlite3.connect(':memory:')) as con:
        for statement in _SCHEMA.split(';\n'):
            if statement.strip():con.execute(statement)
        return _schema_rows(con)


def validate_journal(con):
    if _schema_rows(con)!=_expected_schema():
        raise FenceBlocked('Original service admission schema/immutable audit unavailable')


def _connect(*, create=False, journal=None, inspect_build=False):
    target = Path(journal) if journal else path()
    seal = target.with_suffix('.instance')
    created = False
    if not target.exists():
        if seal.exists() or seal.is_symlink():
            raise FenceBlocked('Original service admission journal is missing')
        if not create or os.getenv('MTA_SERVICE_ADMISSION') != MODE:
            raise FenceBlocked('Service admission journal is unavailable')
        if os.getenv('MTA_NATIVE_SINGLE_USER','').lower() in {'true','1','yes','on'}:
            raise FenceBlocked('Service admission authority is server-only')
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        try:
            fd = os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            os.close(fd)
            created = True
        except FileExistsError:
            pass
    info = target.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise FenceBlocked('Unsafe service admission journal')
    if not seal.exists():
        if not created or info.st_size:
            raise FenceBlocked('Original service admission instance is missing')
        try:
            fd = os.open(seal,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as out:
                out.write(secrets.token_hex(32));out.flush();os.fsync(out.fileno())
        except FileExistsError:
            pass
    seal_info = seal.lstat()
    if not stat.S_ISREG(seal_info.st_mode) or seal_info.st_nlink != 1 or seal_info.st_size != 64:
        raise FenceBlocked('Unsafe service admission instance')
    instance = seal.read_text()
    if not re.fullmatch('[a-f0-9]{64}',instance):raise FenceBlocked('Invalid original service admission instance')
    if info.st_mode & 0o077 or seal_info.st_mode & 0o077:
        raise FenceBlocked('Service admission journal and instance must be private')
    con = sqlite3.connect(target.resolve().as_uri()+'?mode=rw',uri=True,timeout=10,isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA busy_timeout=10000')
        con.execute('BEGIN IMMEDIATE')
        present = con.execute("SELECT 1 FROM sqlite_master WHERE name='state'").fetchone()
        if not present:
            if not created or target.stat().st_size != 0:
                raise FenceBlocked('Unverifiable service admission journal')
            for statement in _SCHEMA.split(';\n'):
                if statement.strip(): con.execute(statement)
            con.execute("INSERT INTO state VALUES(1,0,'open',?,?,NULL)",(build(),instance))
        row = con.execute('SELECT * FROM state WHERE singleton=1').fetchone()
        if row is None or (not inspect_build and row['build'] != build()) or row['instance'] != instance:
            raise FenceBlocked('Service admission build differs from pinned authority')
        validate_journal(con)
        con.execute('COMMIT')
        if not present:
            con.execute('PRAGMA journal_mode=WAL')
            from .fs_durability import sync_directory
            sync_directory(target.parent)
        return con
    except BaseException:
        con.close()
        raise


def _valid(con, ticket):
    if (not isinstance(ticket,dict) or ticket.get('pid') != os.getpid()
            or ticket.get('path') != str(path())):
        raise FenceBlocked('Original service admission required')
    row = con.execute('SELECT * FROM admissions WHERE id=?',(ticket['id'],)).fetchone()
    if (row is None or row['state'] != 'open' or row['pid'] != ticket['pid']
            or not secrets.compare_digest(row['nonce'],ticket['nonce'])):
        raise FenceBlocked('Original active service admission required')
    return row


def reserve(source):
    if not active(): return None
    if not isinstance(source,str) or not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,100}',source):
        raise ValueError('Invalid service admission source')
    with closing(_connect(create=True)) as con:
        con.execute('BEGIN IMMEDIATE')
        parent = _CURRENT.get()
        previous = _valid(con,parent) if parent else None
        state = con.execute('SELECT * FROM state WHERE singleton=1').fetchone()
        if state['phase'] != 'open' and previous is None:
            raise FenceBlocked('Service admission is draining')
        ticket = {'id':secrets.token_hex(16),'nonce':secrets.token_hex(32),
                  'pid':os.getpid(),'path':str(path())}
        con.execute("INSERT INTO admissions VALUES(?,?,?,?,?,?,'open',?,NULL)",
            (ticket['id'],ticket['nonce'],source,previous['id'] if previous else None,
             state['generation'],ticket['pid'],time.time()))
        con.execute('COMMIT')
        return ticket


def release(ticket):
    if ticket is None: return
    # Keep the original journal path on cleanup; a different configured root
    # cannot close or silently adopt an earlier authority's admission.
    if ticket['pid'] != os.getpid(): raise FenceBlocked('Foreign admission process')
    with closing(_connect(journal=ticket['path'])) as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT nonce,state FROM admissions WHERE id=?',(ticket['id'],)).fetchone()
        if row is None or not secrets.compare_digest(row['nonce'],ticket['nonce']):
            raise FenceBlocked('Original service admission required')
        if row['state'] == 'open':
            con.execute("UPDATE admissions SET state='closed',closed=? WHERE id=?",(time.time(),ticket['id']))
        con.execute('COMMIT')


@contextmanager
def operation(source, *, independent=False, database=False):
    if not active() or (database and _CONTROL.get()):
        yield
        return
    previous = _CURRENT.get()
    if previous and not independent:
        with closing(_connect()) as con: _valid(con,previous)
        yield
        return
    ticket = reserve(source)
    token = _CURRENT.set(ticket)
    completed = False
    try:
        yield
        completed = True
    finally:
        _CURRENT.reset(token)
        if completed: release(ticket)


@contextmanager
def existing(ticket):
    if not active():
        yield
        return
    with closing(_connect()) as con: _valid(con,ticket)
    token = _CURRENT.set(ticket)
    try: yield
    finally: _CURRENT.reset(token)


@contextmanager
def control():
    token = _CONTROL.set(True)
    try: yield
    finally: _CONTROL.reset(token)


def periodic(source, call):
    """A sleeping scheduler owns no work; each actual cycle needs admission."""
    try:
        with operation(source): return call()
    except FenceBlocked:
        return None  # Durable work stays in its original journal; no retry/expiry.


class _Thread(threading.Thread):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._admission_start_lock=threading.Lock()

    def start(self):
        with self._admission_start_lock:
            if self._started.is_set():raise RuntimeError('Threads can only be started once')
            return self._start_admitted()

    def _start_admitted(self):
        # Reserve before another process can close admission, not after scheduling.
        self._admission = reserve('thread:'+re.sub(r'[^a-zA-Z0-9_.:-]','_',self.name)[:90])
        try: return super().start()
        except BaseException:
            release(self._admission)
            raise

    def run(self):
        ticket = self._admission
        token = _CURRENT.set(ticket)
        completed = False
        try:
            result = super().run()
            completed = True
            return result
        finally:
            _CURRENT.reset(token)
            if completed: release(ticket)


def worker_thread(*args, **kwargs):
    return _Thread(*args,**kwargs) if active() else threading.Thread(*args,**kwargs)


def admitted(source):
    from functools import wraps
    def decorate(call):
        @wraps(call)
        def invoke(*args,**kwargs):
            with operation(source): return call(*args,**kwargs)
        return invoke
    return decorate


def _actor(actor):
    from . import auth
    if type(actor) is not int or actor <= 0: raise FenceBlocked('Active administrator required')
    with control(), auth.db() as con:
        if not con.execute("SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1",(actor,)).fetchone():
            raise FenceBlocked('Active administrator required')


def change(*, actor, expected_generation, draining, identifier, confirm):
    if (type(expected_generation) is not int or expected_generation < 0 or type(draining) is not bool
            or confirm is not True or not isinstance(identifier,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',identifier)):
        raise ValueError('Exact generation,identity and explicit confirmation required')
    _actor(actor)
    with closing(_connect(create=True)) as con:
        con.execute('BEGIN IMMEDIATE')
        state = con.execute('SELECT * FROM state WHERE singleton=1').fetchone()
        action = 'begin' if draining else 'resume'
        old = con.execute('SELECT * FROM events WHERE drain_id=? AND action=?',(identifier,action)).fetchone()
        if old:
            if old['actor'] != actor or old['generation'] != expected_generation+1:
                raise FenceBlocked('Service drain identity conflict')
            con.execute('COMMIT')
            return inspect(actor=actor)
        if state['generation'] != expected_generation or (state['phase']=='draining') == draining:
            raise FenceBlocked('Service drain generation conflict')
        if not draining and state['drain_id'] != identifier:
            raise FenceBlocked('Original drain identity required')
        generation = expected_generation+1
        con.execute('UPDATE state SET generation=?,phase=?,drain_id=? WHERE singleton=1',
            (generation,'draining' if draining else 'open',identifier if draining else None))
        con.execute('INSERT INTO events(drain_id,action,actor,generation,created) VALUES(?,?,?,?,?)',
            (identifier,action,actor,generation,time.time()))
        con.execute('COMMIT')
    return inspect(actor=actor)


def inspect(*, actor):
    _actor(actor)
    if not active(): return {'enabled':False,'phase':'off','drained':False,'transition_authorized':False}
    from .service_drain_obligations import audit
    from .regime_service_lease import lease
    with closing(_connect(create=True,inspect_build=True)) as con:
        # Keep phase/counts and the obligation audit in one admission snapshot.
        # A concurrent resume/child admission cannot invalidate a drained result
        # before its snapshot has even finished. OS acquisition is nonblocking.
        con.execute('BEGIN IMMEDIATE')
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise FenceBlocked('Service admission integrity unavailable')
        state = dict(con.execute('SELECT generation,phase,drain_id,build AS pinned_build FROM state WHERE singleton=1').fetchone())
        counts = {r[0]:r[1] for r in con.execute("SELECT source,COUNT(*) FROM admissions WHERE state='open' GROUP BY source")}
        history = [dict(r) for r in con.execute('SELECT drain_id,action,actor,generation,created FROM events ORDER BY seq DESC LIMIT 100')]
        try:
            with control(), lease(exclusive=True): pending = audit()
        except FenceBlocked:
            pending = {'verified':False,'count':None,'reasons':['service_activity_or_cutover_lease']}
        return {**state,'enabled':True,'current_build':build(),'build_matches':state['pinned_build']==build(),
                'active_by_source':counts,'active_count':sum(counts.values()),
                'pending':pending,'drained':state['phase']=='draining' and state['pinned_build']==build() and not counts and pending['verified'] and not pending['count'],
                'audit':history,'transition_authorized':False,'release_candidate':False}


def upgrade(*,actor,expected_generation,expected_build,confirm):
    """Explicit new-build handoff;retain every original admission/audit row."""
    if (type(expected_generation) is not int or expected_generation<0 or confirm is not True
            or not isinstance(expected_build,str) or not re.fullmatch('[a-f0-9]{64}',expected_build)):
        raise ValueError('Exact previous build,generation and confirmation required')
    _actor(actor)
    from .regime_service_lease import lease
    from .service_drain_obligations import audit
    with control(),lease(exclusive=True),closing(_connect(inspect_build=True)) as con:
        con.execute('BEGIN IMMEDIATE')
        state=con.execute('SELECT * FROM state WHERE singleton=1').fetchone()
        pending=audit()
        if (state['phase']!='draining' or state['generation']!=expected_generation
                or state['build']!=expected_build or state['build']==build()
                or con.execute("SELECT 1 FROM admissions WHERE state='open' LIMIT 1").fetchone()
                or not pending['verified'] or pending['count']):
            raise FenceBlocked('Original service work must be fully drained before build handoff')
        con.execute('UPDATE state SET build=?,generation=generation+1 WHERE singleton=1',(build(),))
        con.execute("INSERT INTO events(drain_id,action,actor,generation,created) VALUES(?,'upgrade',?,?,?)",
            (state['drain_id'],actor,expected_generation+1,time.time()))
        con.execute('COMMIT')
    return inspect(actor=actor)


def continuation(scope):
    """Only existing, independently authenticated settlement/stop control routes.

    This never authorizes a new background admission. Their handlers still
    require original user/node/task/nonce/signature before any business effect.
    """
    path_ = scope.get('path','');method = scope.get('method','')
    if path_ in {'/api/admin/service-admission','/api/admin/service-admission/change'}:
        return (path_=='/api/admin/service-admission' and method=='GET') or (path_.endswith('/change') and method=='POST')
    if path_=='/api/admin/service-admission/upgrade' and method=='POST':return True
    if path_ == '/login' and method in {'GET','POST'}: return True
    if method in {'GET','HEAD'} and (path_ in {'/settings','/api/health'} or path_.startswith('/static/')): return True
    if method=='POST' and path_ in {'/api/pull-worker/claim','/api/billing/paypal/webhook','/api/billing/credits/stripe-webhook'}: return True
    if method=='POST' and re.fullmatch(r'/api/pull-worker/[a-f0-9]{32}/(heartbeat|complete)',path_): return True
    if method=='DELETE' and re.fullmatch(r'/api/projects/[A-Za-z0-9_-]+/(audio-capture|vst3-live)/[a-f0-9]{32}',path_): return True
    if method=='POST' and re.fullmatch(r'/api/projects/[A-Za-z0-9_-]+/audio-capture/[a-f0-9]{32}/finish',path_): return True
    base = '/api/admin/service-regime/cutovers'
    if method=='GET' and (path_==base or re.fullmatch(base+r'/(preview|lifecycle|[A-Za-z0-9_-]{1,120})',path_)): return True
    if method=='POST' and (path_==base or re.fullmatch(base+r'/[A-Za-z0-9_-]{1,120}/recover',path_)
            or re.fullmatch(base+r'/reservations/[A-Za-z0-9_-]{1,120}/abort',path_)): return True
    return False


async def serve(scope, receive, send, call):
    if scope['type'] not in {'http','websocket'} or not active(): return await call(scope,receive,send)
    if scope['type']=='http' and continuation(scope):
        with control(): return await call(scope,receive,send)
    try:
        admission = operation('http' if scope['type']=='http' else 'websocket')
        admission.__enter__()
    except (FenceBlocked,sqlite3.Error,OSError):
        if scope['type']=='websocket': return await send({'type':'websocket.close','code':1013})
        from starlette.responses import JSONResponse
        return await JSONResponse({'detail':'Service admission is draining;existing work is retained'},status_code=503,
            headers={'Retry-After':'5','Cache-Control':'no-store'})(scope,receive,send)
    try:
        result = await call(scope,receive,send)
    except BaseException:
        import sys
        admission.__exit__(*sys.exc_info())
        raise
    else:
        admission.__exit__(None,None,None)
        return result


class ServiceAdmissionMiddleware:
    def __init__(self,app): self.app = app

    async def __call__(self,scope,receive,send):
        return await serve(scope,receive,send,self.app)
