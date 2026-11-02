"""Replace a project audio source while retaining restorable original bytes."""
import json
import logging
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from . import storage
from .models import ProjectMediaBackup
from .project_media_usage import lock, pending_files

LOGGER = logging.getLogger(__name__)


def _probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
        'stream=codec_name,sample_rate,channels,bits_per_raw_sample', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True, timeout=120)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('Impossibile leggere il formato audio')
    return streams[0]


def _pcm_hash(path):
    result = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-map', '0:a:0',
        '-c:a', 'pcm_s32le', '-f', 'hash', '-hash', 'sha256', '-'],
        capture_output=True, text=True, check=True, timeout=1800)
    return result.stdout.strip()


def _backup_copy(pid, source):
    name = storage._unique_original_name(pid, f'backup-{uuid.uuid4().hex[:12]}-{source.name[:85]}')
    dest = storage.original_path(pid, name)
    with source.open('rb') as src, dest.open('xb') as out:
        shutil.copyfileobj(src, out, length=1024 * 1024)
        out.flush()
        os.fsync(out.fileno())
    if storage.file_sha256(source) != storage.file_sha256(dest):
        raise ValueError('La verifica della copia di backup non è riuscita')
    storage._fsync_directory(dest.parent)
    return dest


def _replace_references(project, old_name, new_name):
    count = 0
    for track in [*project.tracks, *project.archived_tracks]:
        if track.filename == old_name:
            track.filename = new_name
            count += 1
    for clip in project.clip_library:
        if clip.filename == old_name:
            clip.filename = new_name
            clip.current_location = f'audio/{new_name}'
    for backup in project.media_backups:
        if backup.current_filename == old_name:
            backup.current_filename = new_name
    return count


def _ensure_available(pid, name):
    pending, active = pending_files(pid)
    if active or name in pending['audio']:
        raise ValueError('Attendi la fine dei job del progetto prima di sostituire i file')


def _retire_old(pid, name):
    try:
        storage.reconcile_project_gc(pid, {name})
        storage.run_project_gc(pid)
    except Exception:
        # The new project is already committed. Keeping an orphan is safe.
        LOGGER.exception('Unable to retire the old project media')


def convert(pid, name, target, *, capacity_check=None):
    if target not in {'wav', 'flac'}:
        raise ValueError('Formato non supportato: scegli WAV o FLAC')
    with lock(pid):
        project = storage.load_project(pid)
        if (storage.pdir(pid) / 'audio' / name).is_symlink():
            raise ValueError('Collegamento audio non consentito')
        source = storage.audio_path(pid, name)
        if source.is_symlink() or not source.is_file():
            raise ValueError('File audio non disponibile')
        if not any(x.filename == name for x in [*project.tracks, *project.archived_tracks, *project.clip_library]):
            raise ValueError('Il file non è associato al progetto')
        _ensure_available(pid, name)
        info = _probe(source)
        codec = info.get('codec_name', '')
        if codec not in {'pcm_u8', 'pcm_s16le', 'pcm_s24le', 'flac'}:
            raise ValueError('Per una conversione senza perdita usa WAV PCM a 8/16/24 bit o FLAC')
        if source.suffix.lower() == '.' + target:
            raise ValueError('Il file è già nel formato richiesto')
        bit_depth = int(info.get('bits_per_raw_sample') or (24 if codec == 'pcm_s24le' else 16))
        if bit_depth > 24:
            raise ValueError('Profondità non convertibile senza perdita')
        stem = ''.join(c if c.isalnum() and c.isascii() else '_' for c in Path(name).stem)[:70] or 'audio'
        out = storage.audio_path(pid, f'{stem}-{uuid.uuid4().hex[:12]}.{target}')
        stage = out.with_name(f'.{out.stem}.tmp.{target}')
        backup = None
        try:
            encoder = 'flac' if target == 'flac' else ('pcm_s24le' if bit_depth > 16 else 'pcm_s16le')
            subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(source), '-map', '0:a:0',
                '-c:a', encoder, str(stage)], capture_output=True, text=True, check=True, timeout=1800)
            converted = _probe(stage)
            if any(str(info.get(k)) != str(converted.get(k)) for k in ('sample_rate', 'channels')) or _pcm_hash(source) != _pcm_hash(stage):
                raise ValueError('La verifica dei campioni convertiti non è riuscita')
            if capacity_check:
                capacity_check(project.owner_user_id, source.stat().st_size)
            backup = _backup_copy(pid, source)
            os.replace(stage, out)
            storage._fsync_directory(out.parent)
            count = _replace_references(project, name, out.name)
            project.media_backups.append(ProjectMediaBackup(id=uuid.uuid4().hex, filename=backup.name,
                current_filename=out.name, original_filename=name))
            if target == 'wav':
                project.audio_storage_mode = 'wav'
            storage.save_project(project, _skip_flac_conversion=True)
        except Exception:
            stage.unlink(missing_ok=True)
            # Preserve published files and backups on uncertain commits; cleanup
            # can remove an unreferenced copy without risking source data.
            raise
        _retire_old(pid, name)
        return {'project': project, 'old_filename': name, 'filename': out.name,
                'backup': backup.name, 'tracks_updated': count}


def restore(pid, backup_id, target_filename=None, *, capacity_check=None):
    with lock(pid):
        project = storage.load_project(pid)
        record = next((x for x in project.media_backups if x.id == backup_id), None)
        if record is None:
            raise ValueError('Backup non trovato')
        target = target_filename or record.current_filename
        _ensure_available(pid, target)
        if ((storage.pdir(pid) / 'audio' / target).is_symlink()
                or (storage.pdir(pid) / 'originals' / record.filename).is_symlink()):
            raise ValueError('Collegamento audio non consentito')
        current = storage.audio_path(pid, target)
        original = storage.original_path(pid, record.filename)
        if current.is_symlink() or not current.is_file() or original.is_symlink() or not original.is_file():
            raise ValueError('File corrente o backup non disponibile')
        if not any(x.filename == target for x in [*project.tracks, *project.archived_tracks, *project.clip_library]):
            raise ValueError('Il file corrente non è più associato al progetto')
        if capacity_check:
            capacity_check(project.owner_user_id, current.stat().st_size + original.stat().st_size)
        suffix = Path(record.original_filename).suffix.lower()
        if suffix not in {'.wav', '.flac', '.mp3', '.m4a', '.ogg', '.aac', '.aif', '.aiff'}:
            raise ValueError('Formato del backup non supportato')
        backup = _backup_copy(pid, current)
        out = storage.audio_path(pid, f'restored-{uuid.uuid4().hex[:16]}{suffix}')
        with original.open('rb') as src, out.open('xb') as dest:
            shutil.copyfileobj(src, dest, length=1024 * 1024)
            dest.flush()
            os.fsync(dest.fileno())
        if storage.file_sha256(original) != storage.file_sha256(out):
            raise ValueError('La verifica del backup ripristinato non è riuscita')
        old = target
        count = _replace_references(project, old, out.name)
        record.current_filename = out.name
        project.media_backups.append(ProjectMediaBackup(id=uuid.uuid4().hex, filename=backup.name,
            current_filename=out.name, original_filename=old))
        if suffix == '.wav':
            project.audio_storage_mode = 'wav'
        storage.save_project(project, _skip_flac_conversion=True)
        _retire_old(pid, old)
        return {'project': project, 'filename': out.name, 'backup': backup.name, 'tracks_updated': count}
