"""Project-authorized MIDI editing. Plugins still execute only in workers."""
import math
from pathlib import Path
import uuid
import wave

from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .models import Track, Clip, MidiNote, MidiControl, MidiSysEx, MidiUmp, InsertPlugin, MidiMeta, MidiMetronome


class Edit(BaseModel):
    name: str = Field(default='MIDI',min_length=1,max_length=200)
    notes: list[MidiNote] = Field(default_factory=list,max_length=50000)
    controls: list[MidiControl] = Field(default_factory=list,max_length=100000)
    ump: list[MidiUmp] = Field(default_factory=list,max_length=100000)
    mpe_zone: str = Field(default='off',pattern=r'^(off|lower|upper)$')
    mpe_members: int = Field(default=15,ge=1,le=15)
    mpe_pitch_bend: int = Field(default=48,ge=1,le=96)
    sysex: list[MidiSysEx] = Field(default_factory=list,max_length=1024)
    midi_metronome: MidiMetronome | None = None
    metronome_insertion_ms: int | None = Field(default=None, ge=0, le=86400000)
    metronome_pre_roll_bars: int | None = Field(default=None, ge=0, le=64)
    midi_smf_type: int = Field(default=1, ge=0, le=2)
    midi_division: int = Field(default=960, ge=-32768, le=32767)
    midi_meta: list[MidiMeta] = Field(default_factory=list, max_length=10000)
    instrument: InsertPlugin | None = None
    midi_route: str = Field(default='instrument',pattern=r'^(instrument|hardware|both|none)$')
    duration_ms: int = Field(default=8000,ge=1,le=86400000)


def register_routes(app,project_for_actor,mutation,quota):
    from .storage import audio_path,save_project
    from .midi_smf import read_parts, write_parts, division_rate

    def apply(track,body):
        from .vst3_host import validate_plugin_path
        if body.instrument:
            try:
                if body.instrument.plugin=='gm_soundfont':
                    from .gm_instruments import validate,bank_path
                    body.instrument.params=validate(body.instrument.params);bank_path(body.instrument.params['bank_id'])
                elif body.instrument.plugin=='vst3':validate_plugin_path(str(body.instrument.params.get('path','')))
                else:raise ValueError('Select a VST3 or General MIDI instrument')
            except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc
            body.instrument.id='instrument'
        last=max((n.start_ms+n.duration_ms for n in body.notes),default=0)
        end=math.ceil(max(body.duration_ms,last+2000,max((c.time_ms for c in body.controls),default=0),max((c.time_ms for c in body.sysex),default=0),max((c.time_ms+2000 for c in body.ump),default=0)))
        if end>86400000:raise HTTPException(422,'MIDI duration exceeds 24 hours')
        try:division_rate(body.midi_division)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        track.midi_metronome=body.midi_metronome;track.midi_metronome_revision=""
        track.midi_smf_type=body.midi_smf_type;track.midi_division=body.midi_division;track.midi_meta=body.midi_meta
        track.name=body.name;track.midi_notes=body.notes;track.midi_controls=body.controls;track.instrument=body.instrument
        track.midi_route=body.midi_route;track.midi_sysex=body.sysex;track.midi_ump=body.ump
        track.mpe_zone=body.mpe_zone;track.mpe_members=body.mpe_members;track.mpe_pitch_bend=body.mpe_pitch_bend
        if len({n.id for n in track.midi_notes})!=len(track.midi_notes):raise HTTPException(422,'Duplicate MIDI note id')
        from .midi import events
        try:events(track,timeline=False)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        old_duration=track.duration_ms;track.duration_ms=end
        # Extend the default source clip without destroying intentional clip edits.
        if len(track.clips)==1 and track.clips[0].source_start_ms==0 and track.clips[0].source_end_ms==old_duration:
            track.clips[0].source_end_ms=end
        track.waveform_peaks=[];track.waveform_revision=''

    def apply_metronome_origin(project, body):
        if body.metronome_insertion_ms is None and body.metronome_pre_roll_bars is None:
            return
        if body.midi_metronome is None:
            raise HTTPException(422, 'Metronome origin requires a linked MIDI metronome')
        from .timeline_editing import prepare_metronome_insert
        try:
            prepared, _ = prepare_metronome_insert(project,
                body.metronome_insertion_ms if body.metronome_insertion_ms is not None else project.metronome_insertion_ms,
                body.metronome_pre_roll_bars if body.metronome_pre_roll_bars is not None else project.metronome_pre_roll_bars)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        for name in type(project).model_fields:
            setattr(project, name, getattr(prepared, name))

    def add(project,body,*,publish=True,track_id=None):
        apply_metronome_origin(project,body)
        from .project_kinds import require_kind
        require_kind(project, "midi")
        if len(project.tracks)>=64:raise HTTPException(422,'Maximum 64 tracks for live playback')
        track_id=track_id or uuid.uuid4().hex[:12]
        track=Track(id=track_id,name=body.name,filename='midi-'+track_id+'.wav',kind='midi',channels=2,sample_rate=project.sample_rate,duration_ms=body.duration_ms)
        apply(track,body);track.clips=[Clip(id=uuid.uuid4().hex[:12],source_end_ms=track.duration_ms)];track.clips_initialized=True
        previous_size=len(project.model_dump_json(indent=2).encode())
        project.tracks.append(track)
        from .midi_metronome import refresh
        refresh(project)
        if publish:quota(project.owner_user_id,4096+len(project.model_dump_json(indent=2).encode())-previous_size)
        # Tiny, real silent media anchor keeps legacy project/archive/file lifetimes
        # compatible. It is NEVER used to synthesize a MIDI track.
        path=audio_path(project.id,track.filename)
        with wave.open(str(path),'wb') as writer:
            writer.setnchannels(2);writer.setsampwidth(2);writer.setframerate(project.sample_rate);writer.writeframes(b'\0'*192)
        try:
            if publish:save_project(project)
        except BaseException:
            cleanup_unpublished(project.id, [track])
            raise
        return project

    def cleanup_unpublished(pid, tracks):
        # A storage fault can happen after the atomic JSON replacement. Never
        # remove media already referenced by the committed project.
        from .storage import load_project
        try:
            from .storage import referenced_audio_files
            keep=referenced_audio_files(load_project(pid))
        except (OSError,ValueError):return
        for track in tracks:
            if track.filename not in keep:audio_path(pid,track.filename).unlink(missing_ok=True)

    @app.get('/api/projects/{pid}/midi/revision')
    def musical_revision(pid:str,request:Request):
        from .music_publication import revision
        return {'revision':revision(project_for_actor(request,pid))}

    @app.post('/api/projects/{pid}/midi/music')
    async def import_music(pid:str,request:Request):
        """Typed shared result import; worker metrics are never accepted here."""
        project_for_actor(request,pid)
        data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>16*1024*1024:raise HTTPException(413,'Musical result exceeds 16 MiB')
        from .music_publication import parse_import
        from starlette.concurrency import run_in_threadpool
        try:publication,expected,result=await run_in_threadpool(parse_import,bytes(data))
        except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc
        @mutation
        def commit(pid,request):
            return publish_music(project_for_actor(request,pid),publication,expected,result)
        return await run_in_threadpool(commit,pid,request)

    def publish_music(project,publication,expected,result,audio=None,generation=None):
        from .project_kinds import require_kind
        require_kind(project, "midi")
        if audio:require_kind(project, "audio")
        from .music_publication import revision,result_digest
        digest=result_digest(result)
        audio=audio or {}
        if audio:
            import hashlib
            import json
            digest=hashlib.sha256((digest+json.dumps(generation or {},sort_keys=True)+''.join(key+hashlib.sha256(value).hexdigest() for key,value in sorted(audio.items()))).encode()).hexdigest()
            if set(audio)!={part.id for part in result.parts}:raise HTTPException(422,'Incomplete vocal audio/MIDI result')
        pid=project.id
        previous=project.music_imports.get(publication)
        if previous:
            if previous!=digest:raise HTTPException(409,'Publication identifier already used for different results')
            return {'project':project,'replayed':True}
        if revision(project)!=expected:raise HTTPException(409,'Project changed during processing; review the result before importing against the current revision')
        if len(project.music_imports)>=1024:raise HTTPException(422,'Musical publication history is full')
        if len(project.tracks)+len(result.parts)*(2 if audio else 1)>64:raise HTTPException(422,'Maximum 64 tracks for live playback')
        if len(project.music_alternatives)+len(result.alternatives)>128:raise HTTPException(422,'Maximum 128 alternative musical parts')
        from .gm_instruments import status as gm_status
        gm_available=bool(gm_status()['available']) if not audio else False
        original=len(project.tracks);size=len(project.model_dump_json(indent=2).encode());names={t.name for t in project.tracks}
        try:
            for part in result.parts:
                from .music_publication import generation_for_part
                part_generation=generation_for_part(generation,part.id)
                name=part.name;suffix=2
                while name in names:name=part.name[:190]+f' {suffix}';suffix+=1
                names.add(name)
                notes=[n.model_copy(update={'start_ms':n.start_ms+result.offset_ms}) for n in part.notes]
                controls=[c.model_copy(update={'time_ms':c.time_ms+result.offset_ms}) for c in part.controls]
                if part.program is not None:
                    channels={n.channel for n in notes} or {9 if part.percussion else 0}
                    controls=[MidiControl(time_ms=result.offset_ms,data=[0xC0|channel,part.program]) for channel in sorted(channels)]+controls
                tid=uuid.uuid5(uuid.UUID(publication),part.id).hex[:12]
                if any(t.id==tid for t in project.tracks):raise HTTPException(409,'Musical track identifier collision')
                instrument=InsertPlugin(id='instrument',plugin='gm_soundfont',params={'program':part.program if part.program is not None else 0}) if gm_available else None
                add(project,Edit(name=name,notes=notes,controls=controls,duration_ms=1000,instrument=instrument,midi_route='instrument' if instrument else 'none'),publish=False,track_id=tid)
                track=project.tracks[-1];track.music_result_id=publication;track.music_part_id=part.id;track.music_source_model=part.source_model
                if part_generation:track.music_generation=part_generation
                if audio:
                    import io
                    import soundfile as sf
                    data=audio[part.id]
                    info=sf.info(io.BytesIO(data))
                    if info.format!='WAV' or info.channels not in (1,2) or info.samplerate!=48000 or not 0<info.duration<=610:
                        raise HTTPException(422,'Invalid rendered singing audio')
                    audio_id=uuid.uuid5(uuid.UUID(publication),'audio:'+part.id).hex[:12]
                    if any(t.id==audio_id for t in project.tracks):raise HTTPException(409,'Vocal audio identifier collision')
                    audio_name=part.name+' · Voice';suffix=2
                    while audio_name in names:audio_name=part.name[:180]+f' · Voice {suffix}';suffix+=1
                    names.add(audio_name)
                    vocal=Track(id=audio_id,name=audio_name,filename='voice-'+audio_id+'.wav',kind='audio',
                        channels=info.channels,sample_rate=info.samplerate,duration_ms=math.ceil(info.duration*1000),
                        music_result_id=publication,music_part_id=part.id,music_source_model=part.source_model or (generation or {}).get('backend','oddvoices-cc0'))
                    if part_generation:vocal.music_generation=part_generation
                    vocal.clips=[Clip(id=uuid.uuid4().hex[:12],timeline_start_ms=round(result.offset_ms),source_end_ms=vocal.duration_ms)];vocal.clips_initialized=True
                    project.tracks.append(vocal)
                    media=audio_path(pid,vocal.filename)
                    if media.exists() or media.is_symlink():
                        from .ai_worker_artifacts import _read_private_file
                        if _read_private_file(media,len(data))!=data:raise HTTPException(409,'Existing vocal artifact differs; inspect recovery media before importing')
                    else:
                        with media.open('xb') as output:
                            output.write(data);output.flush()
                            import os
                            os.fsync(output.fileno())
            for part in result.alternatives:
                project.music_alternatives.append(part.model_copy(update={
                    'id':uuid.uuid5(uuid.UUID(publication),'alternative:'+part.id).hex,
                    'source_result_id':publication,
                    'notes':[n.model_copy(update={'start_ms':n.start_ms+result.offset_ms}) for n in part.notes],
                    'controls':[c.model_copy(update={'time_ms':c.time_ms+result.offset_ms}) for c in part.controls]}))
            project.music_imports[publication]=digest
            project.ai_publication_token=publication
            quota(project.owner_user_id,sum(len(v) for v in audio.values())+4096*len(result.parts)+len(project.model_dump_json(indent=2).encode())-size)
            save_project(project)
        except BaseException:
            cleanup_unpublished(pid,project.tracks[original:])
            raise
        return {'project':project,'replayed':False}

    @app.get('/api/projects/{pid}/midi/alternatives')
    def alternatives(pid:str,request:Request):
        project=project_for_actor(request,pid)
        from .music_publication import revision
        return {'parts':project.music_alternatives,'revision':revision(project)}

    @app.post('/api/projects/{pid}/midi/alternatives/{part_id}/import')
    @mutation
    def import_alternative(pid:str,part_id:str,body:dict,request:Request):
        project=project_for_actor(request,pid)
        if set(body)!={'expected_revision'}:raise HTTPException(422,'Current project revision required')
        part=next((p for p in project.music_alternatives if p.id==part_id),None)
        if part is None:raise HTTPException(404,'Alternative not found')
        from .music_interchange import MusicResult
        publication=uuid.uuid5(uuid.NAMESPACE_URL,pid+':alternative:'+part_id).hex
        return publish_music(project,publication,body['expected_revision'],MusicResult(parts=[part]))

    @app.post('/api/projects/{pid}/midi')
    @mutation
    def create(pid:str,body:Edit,request:Request):
        return add(project_for_actor(request,pid),body)

    @app.post('/api/projects/{pid}/midi/import')
    async def import_file(pid:str,request:Request):
        # Bound actual bytes, even when Content-Length is missing or false.
        project_for_actor(request,pid);data=bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data)>8*1024*1024:raise HTTPException(413,'MIDI file exceeds 8 MiB')
        from starlette.concurrency import run_in_threadpool
        try:parts=await run_in_threadpool(read_parts,bytes(data))
        except (ValueError,EOFError,OSError,KeyError) as exc:raise HTTPException(422,'Invalid MIDI file: '+str(exc)) from exc
        # Parsing does not hold a publication lock; reload under the same lock
        # used for all editor/AI mutations before publishing the track.
        @mutation
        def commit(pid,request):
            project=project_for_actor(request,pid)
            if len(project.tracks)+len(parts)>64:raise HTTPException(422,'Maximum 64 tracks for live playback')
            bodies=[Edit(**part) for part in parts]
            if len(bodies)==1 and bodies[0].name.startswith('MIDI '):bodies[0].name=Path(request.query_params.get('name','MIDI')).stem[:200] or 'MIDI'
            previous_size=len(project.model_dump_json(indent=2).encode());original=len(project.tracks)
            try:
                from .musical_clock import MusicalClock
                own_origin = any(meta.message.get('type') == 'marker' and str(meta.message.get('text', '')).startswith('MTA-MUSICAL-ORIGIN:') for body in bodies for meta in body.midi_meta)
                align = request.query_params.get('align_origin', 'true').lower() != 'false' and not own_origin
                offset = max(0, round(MusicalClock(project).origin)) if align else 0
                for body in bodies:
                    add(project,body,publish=False)
                    for clip in project.tracks[-1].clips:
                        clip.timeline_start_ms += offset
                quota(project.owner_user_id,4096*len(bodies)+len(project.model_dump_json(indent=2).encode())-previous_size)
                save_project(project)
            except BaseException:
                cleanup_unpublished(project.id,project.tracks[original:])
                raise
            return project
        return await run_in_threadpool(commit,pid,request)

    @app.put('/api/projects/{pid}/midi/{tid}')
    @mutation
    def edit(pid:str,tid:str,body:Edit,request:Request):
        project=project_for_actor(request,pid)
        apply_metronome_origin(project,body)
        track=next((t for t in project.tracks if t.id==tid and t.kind=='midi'),None)
        if not track:raise HTTPException(404,'MIDI track not found')
        previous_size=len(project.model_dump_json(indent=2).encode())
        apply(track,body)
        quota(project.owner_user_id,max(0,len(project.model_dump_json(indent=2).encode())-previous_size))
        save_project(project);return project

    @app.get('/api/projects/{pid}/midi/{tid}/export')
    def export(pid:str,tid:str,request:Request,format:str='smf',smf_type:int=0,division:int=960,time_domain:str='audible'):
        project=project_for_actor(request,pid);track=next((t for t in project.tracks if t.id==tid and t.kind=='midi'),None)
        if not track:raise HTTPException(404,'MIDI track not found')
        if format=='ump':
            import json
            payload={'format':'mta-ump-1','units':'milliseconds','events':[e.model_dump() for e in track.midi_ump]}
            return Response(json.dumps(payload),media_type='application/json',headers={'Content-Disposition':'attachment; filename="track.ump.json"','Cache-Control':'no-store'})
        if track.midi_ump:raise HTTPException(422,'Use lossless UMP JSON export for MIDI 2 events')
        try:data=write_parts([track],file_type=smf_type,division=division,bpm=project.bpm,time_signature=project.time_signature,project=project,time_domain=time_domain)
        except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc
        return Response(data,media_type='audio/midi',headers={'Content-Disposition':'attachment; filename="track.mid"','Cache-Control':'no-store'})

    @app.get('/api/projects/{pid}/midi/export')
    def export_project(pid:str,request:Request,smf_type:int=1,division:int=960,time_domain:str='audible'):
        project=project_for_actor(request,pid)
        tracks=[track for track in project.tracks if track.kind=='midi']
        try:data=write_parts(tracks,file_type=smf_type,division=division,bpm=project.bpm,time_signature=project.time_signature,project=project,time_domain=time_domain)
        except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc)) from exc
        return Response(data,media_type='audio/midi',headers={'Content-Disposition':'attachment; filename="project.mid"','Cache-Control':'no-store'})

    @app.get('/api/midi/instruments')
    def instruments(request:Request):
        from .auth import require_user
        require_user(request)
        from .gm_instruments import status
        from .gm_banks import catalog
        return {'instruments':[status(),*[status(bank['id']) for bank in catalog()]]}

    return publish_music
