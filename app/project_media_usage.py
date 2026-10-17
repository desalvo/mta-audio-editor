"""Authoritative media use: timeline, reusable library and pending publications."""
import json
import stat
import time
from contextlib import nullcontext


def lock(pid):
    from .storage import fcntl
    from .ai_project_lock import project_publication_lock
    return project_publication_lock(pid) if fcntl is not None else nullcontext()


def timeline_files(project):
    source_ids={getattr(track,'source_clip_id',None) for track in project.tracks if getattr(track,'source_clip_id',None)}
    return {track.filename for track in project.tracks} | {
        clip.filename for clip in project.clip_library if clip.id in source_ids}


def pending_files(pid):
    from .storage import pdir,SAFE_NAME_RE
    from . import ai_arranger_runtime as queue
    folder=pdir(pid)
    if any((folder/name).is_symlink() for name in ('audio','originals','attachments')):
        raise ValueError('Unsafe project media directory')
    result={'audio':set(),'original':set()}
    active=False
    journals=list(folder.glob('.async-track-*.pending.json'))
    journals += [folder/name for name in ('.ordinary-upload-pending.json','.recovered-stems-pending.json')
                 if (folder/name).exists() or (folder/name).is_symlink()]
    for path in journals:
        # An unvalidated recovery journal can never authorize destructive cleanup.
        if path.is_symlink() or not path.is_file() or path.stat().st_size>1024*1024:
            raise ValueError('Unsafe pending media journal; recover it before cleanup')
        try:data=json.loads(path.read_text())
        except (OSError,ValueError) as exc:raise ValueError('Unreadable pending media journal') from exc
        if not isinstance(data,dict) or data.get('version') not in (1,2):
            raise ValueError('Invalid pending media journal')
        active=True
        if path.name.startswith('.async-track-'):
            for key,category in (('files','audio'),('originals','original')):
                values=data.get(key,[])
                if not isinstance(values,list) or any(not isinstance(n,str) or not SAFE_NAME_RE.fullmatch(n) for n in values):
                    raise ValueError('Invalid pending media filenames')
                result[category].update(values)
        else:
            # Snapshot transactions can own any newly created file until commit.
            for category,directory in (('audio','audio'),('original','originals')):
                result[category].update(p.name for p in (folder/directory).iterdir())
    with queue._db() as con:
        rows=con.execute("SELECT payload_json,operation FROM jobs WHERE project_id=? AND state IN ('queued','running','busy','blocked')",(pid,)).fetchall()
    for row in rows:
        active=True
        try:data=json.loads(row[0] or '{}')
        except ValueError as exc:raise ValueError('Unreadable queued media payload') from exc
        if not isinstance(data,dict):raise ValueError('Invalid queued media payload')
        category,name=data.get('source_category'),data.get('source_name')
        if category in result and isinstance(name,str) and SAFE_NAME_RE.fullmatch(name):
            result[category].add(name)
        elif row[1] != 'model-download':
            # Older queues and render-from-project adapters do not carry an
            # immutable source locator. Keep their reusable project inputs until
            # termination; never guess that a running adapter has finished reading.
            from .storage import load_project,referenced_audio_files
            result['audio'].update(referenced_audio_files(load_project(pid)))
    return result,active


def cleanup(pid,*,remove_unused_library=False):
    from . import storage
    with lock(pid):
        project=storage.load_project(pid)
        pending,active=pending_files(pid)
        used=timeline_files(project)|pending['audio']
        removed_clips=0
        if remove_unused_library:
            keep=[clip for clip in project.clip_library if clip.filename in used]
            removed_clips=len(project.clip_library)-len(keep)
            if removed_clips:
                project.clip_library=keep
                storage.save_project(project)
        storage.reconcile_project_gc(pid,None)
        result=storage.run_project_gc(pid)
        temporary=0
        if not active:
            folder=storage.pdir(pid)
            # Only known rebuildable/staging formats, regular files older than a day.
            patterns=((folder,'.project.json.*.tmp'),(folder/'audio','.*.tmp.wav'),
                      (folder/'audio','.*.tmp.flac'),(folder,'.sample-fx-*'))
            for directory,pattern in patterns:
                for path in directory.glob(pattern):
                    info=path.lstat()
                    if stat.S_ISREG(info.st_mode) and time.time()-info.st_mtime>86400:
                        path.unlink();temporary+=1
        return {**result,'library_removed':removed_clips,'temporary_deleted':temporary,'active_jobs':active}
