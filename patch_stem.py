from pathlib import Path
p=Path('/mnt/data/r208_import_cycle/app/main.py')
s=p.read_text()
needle="@app.post('/api/native/ai-workers/settings')"
assert needle in s
new='''@app.post('/api/native/ai-workers/pending/{request_id}/import-stems/{pid}')
def native_ai_workers_import_recovered_stems(request: Request, request_id: str, pid: str):
    """Import a verified multi-WAV worker archive as one durable project update.

    The original pending record is retained: no POST to the remote inference
    endpoint occurs here. Project locking serializes cross-process retries.
    """
    import io, zipfile, hashlib
    from .ai_project_lock import project_publication_lock
    from .ai_native_remote_journal import read_owned_pending
    from .ai_worker_artifacts import _verify_wav_bytes, SAFE_NAME, MAX_ARTIFACT_BYTES
    _ace_native_only(request)
    _project_for_actor(request, pid)
    if not re.fullmatch(r'[0-9a-f]{32}', request_id):
        raise HTTPException(400, 'Invalid pending request identifier')
    try:
        owned = read_owned_pending(request_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    kind = owned.get('kind')
    if kind not in ('demucs', 'drumsep', 'sam-audio', 'singer-separation', 'backing-vocals'):
        raise HTTPException(415, 'This adapter does not produce importable audio stems')
    with project_publication_lock(pid):
        project = _project_for_actor(request, pid)
        receipt = f'stems:{kind}:{request_id}'
        if receipt in project.recovered_ai_imports:
            raise HTTPException(409, 'These recovered stems were already imported')
        recovered = native_ai_workers_pending_artifact(request, request_id)
        if recovered.media_type != 'application/zip' or len(recovered.body) > MAX_ARTIFACT_BYTES:
            raise HTTPException(415, 'Recovered result must be a bounded artifact ZIP')
        try:
            with zipfile.ZipFile(io.BytesIO(recovered.body)) as archive:
                entries = archive.infolist()
                if not entries or len(entries) > 17:
                    raise ValueError('Invalid artifact count')
                if len({entry.filename for entry in entries}) != len(entries):
                    raise ValueError('Duplicate archive entry')
                if any(not SAFE_NAME.fullmatch(entry.filename) or entry.is_dir() or
                       (entry.external_attr >> 16) & 0o170000 == 0o120000 for entry in entries):
                    raise ValueError('Unsafe archive entry')
                manifest_entries = [entry for entry in entries if entry.filename == 'manifest.json']
                if len(manifest_entries) != 1 or manifest_entries[0].file_size > 256000:
                    raise ValueError('Missing output manifest')
                manifest = json.loads(archive.read('manifest.json'))
                if not isinstance(manifest, dict) or manifest.get('version') != 1 or not isinstance(manifest.get('files'), list):
                    raise ValueError('Unsupported output manifest')
                specs = manifest['files']
                if not specs or len(specs) > 16 or len(specs) != len(entries) - 1:
                    raise ValueError('Manifest does not describe archive')
                if {entry.get('name') for entry in specs if isinstance(entry, dict)} != {entry.filename for entry in entries if entry.filename != 'manifest.json'}:
                    raise ValueError('Manifest entry mismatch')
                audio = []
                total = 0
                for spec in specs:
                    name, media = spec.get('name'), spec.get('type')
                    if media not in ('audio/wav', 'application/json', 'text/plain'):
                        raise ValueError('Unsupported manifest media type')
                    info = archive.getinfo(name)
                    total += info.file_size
                    if info.file_size > MAX_ARTIFACT_BYTES or total > MAX_ARTIFACT_BYTES:
                        raise ValueError('Expanded archive exceeds limit')
                    if media == 'audio/wav':
                        if not name.endswith('.wav'):
                            raise ValueError('Expected WAV extension')
                        payload = archive.read(name)
                        _verify_wav_bytes(payload)
                        digest = spec.get('sha256')
                        if digest is not None and (not isinstance(digest, str) or
                              hashlib.sha256(payload).hexdigest() != digest):
                            raise ValueError('Artifact digest mismatch')
                        audio.append((name, payload))
                if not audio or len(audio) > 16:
                    raise ValueError('No WAV stems in recovered archive')
        except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
            raise HTTPException(422, 'Invalid recovered stem archive') from exc
        created = []
        try:
            for name, payload in audio:
                uploaded = UploadFile(filename=name, file=io.BytesIO(payload))
                filename, dst, duration = _save_upload(pid, uploaded, int(project.sample_rate))
                created.append(dst)
                stem = Path(name).stem.replace('_', ' ').title()
                track = Track(id=uuid.uuid4().hex[:10], name=f'Recovered {stem}'[:200],
                              filename=filename, duration_ms=duration,
                              sample_rate=int(project.sample_rate),
                              clips=[Clip(id=uuid.uuid4().hex[:10], source_start_ms=0,
                                          source_end_ms=duration, timeline_start_ms=0)])
                project.tracks.append(track)
                _register_track_source_in_library(project, track, f'Recovered AI stem: {name}')
            project.recovered_ai_imports.append(receipt)
            save_project(project)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            raise
        return {'ok': True, 'kind': kind, 'count': len(audio), 'request_id': request_id,
                'project_id': pid, 'journal_preserved': True}


'''
s=s.replace(needle,new+needle)
p.write_text(s)
js=Path('/mnt/data/r208_import_cycle/app/static/app.js')
t=js.read_text()
t=t.replace("${['whisper','chords-ml'].includes(item.kind)?", "${['demucs','drumsep','sam-audio','singer-separation','backing-vocals'].includes(item.kind)?`<button type=\"button\" onclick=\"importNativePendingStems('${id}')\">Import recovered stems / Importa stem</button>`:''}${['whisper','chords-ml'].includes(item.kind)?")
needle='async function saveNativeRemoteWorker(kind){'
assert needle in t
t=t.replace(needle,'''async function importNativePendingStems(id){
 const target=document.getElementById(`nativePendingStatus-${id}`);
 if(!/^[0-9a-f]{32}$/.test(id)||!current?.id){if(target)target.textContent='Open a project / Apri un progetto';return;}
 if(nativePendingImportsInFlight.has(id))return;
 const projectId=current.id;
 nativePendingImportsInFlight.add(id);
 try{
  const result=await api(`/api/native/ai-workers/pending/${encodeURIComponent(id)}/import-stems/${encodeURIComponent(projectId)}`,{method:'POST'});
  if(current?.id!==projectId)throw Error('Active project changed during import');
  await refresh();
  if(target?.isConnected)target.textContent=`${result.count} recovered stems imported. Journal preserved.`;
 }catch(e){if(target?.isConnected)target.textContent=e.message;}
 finally{nativePendingImportsInFlight.delete(id);}
}
'''+needle)
js.write_text(t)
