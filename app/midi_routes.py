"""Project-authorized MIDI editing. Plugins still execute only in workers."""
import math
from pathlib import Path
import uuid
import wave

from fastapi import HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .models import Track, Clip, MidiNote, MidiControl, MidiSysEx, MidiUmp, InsertPlugin


class Edit(BaseModel):
    name: str = Field(default='MIDI',min_length=1,max_length=200)
    notes: list[MidiNote] = Field(default_factory=list,max_length=50000)
    controls: list[MidiControl] = Field(default_factory=list,max_length=100000)
    ump: list[MidiUmp] = Field(default_factory=list,max_length=100000)
    mpe_zone: str = Field(default='off',pattern=r'^(off|lower|upper)$')
    mpe_members: int = Field(default=15,ge=1,le=15)
    mpe_pitch_bend: int = Field(default=48,ge=1,le=96)
    sysex: list[MidiSysEx] = Field(default_factory=list,max_length=1024)
    instrument: InsertPlugin | None = None
    midi_route: str = Field(default='instrument',pattern=r'^(instrument|hardware|both)$')
    duration_ms: int = Field(default=8000,ge=1,le=86400000)


def register_routes(app,project_for_actor,mutation,quota):
    from .storage import audio_path,save_project
    from .midi import read_smf,write_smf

    def apply(track,body):
        from .vst3_host import validate_plugin_path
        if body.instrument:
            if body.instrument.plugin!='vst3':raise HTTPException(422,'Select a VST3 instrument')
            try:validate_plugin_path(str(body.instrument.params.get('path','')))
            except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc
            body.instrument.id='instrument'
        last=max((n.start_ms+n.duration_ms for n in body.notes),default=0)
        end=math.ceil(max(body.duration_ms,last+2000,max((c.time_ms for c in body.controls),default=0),max((c.time_ms for c in body.sysex),default=0),max((c.time_ms+2000 for c in body.ump),default=0)))
        if end>86400000:raise HTTPException(422,'MIDI duration exceeds 24 hours')
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

    def add(project,body):
        if len(project.tracks)>=64:raise HTTPException(422,'Maximum 64 tracks for live playback')
        track=Track(id=uuid.uuid4().hex[:12],name=body.name,filename='midi-'+uuid.uuid4().hex+'.wav',kind='midi',channels=2,sample_rate=project.sample_rate,duration_ms=body.duration_ms)
        apply(track,body);track.clips=[Clip(id=uuid.uuid4().hex[:12],source_end_ms=track.duration_ms)];track.clips_initialized=True
        previous_size=len(project.model_dump_json(indent=2).encode())
        project.tracks.append(track)
        quota(project.owner_user_id,4096+len(project.model_dump_json(indent=2).encode())-previous_size)
        # Tiny, real silent media anchor keeps legacy project/archive/file lifetimes
        # compatible. It is NEVER used to synthesize a MIDI track.
        path=audio_path(project.id,track.filename)
        with wave.open(str(path),'wb') as writer:
            writer.setnchannels(2);writer.setsampwidth(2);writer.setframerate(project.sample_rate);writer.writeframes(b'\0'*192)
        try:save_project(project)
        except BaseException:path.unlink(missing_ok=True);raise
        return project

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
        try:notes,controls,duration,sysex=await run_in_threadpool(read_smf,bytes(data),extended=True)
        except (ValueError,EOFError,OSError,KeyError) as exc:raise HTTPException(422,'Invalid MIDI file: '+str(exc)) from exc
        # Parsing does not hold a publication lock; reload under the same lock
        # used for all editor/AI mutations before publishing the track.
        @mutation
        def commit(pid,request):
            project=project_for_actor(request,pid)
            return add(project,Edit(name=Path(request.query_params.get('name','MIDI')).stem[:200] or 'MIDI',notes=notes,controls=controls,sysex=sysex,duration_ms=duration))
        return await run_in_threadpool(commit,pid,request)

    @app.put('/api/projects/{pid}/midi/{tid}')
    @mutation
    def edit(pid:str,tid:str,body:Edit,request:Request):
        project=project_for_actor(request,pid);track=next((t for t in project.tracks if t.id==tid and t.kind=='midi'),None)
        if not track:raise HTTPException(404,'MIDI track not found')
        previous_size=len(project.model_dump_json(indent=2).encode())
        apply(track,body)
        quota(project.owner_user_id,max(0,len(project.model_dump_json(indent=2).encode())-previous_size))
        save_project(project);return project

    @app.get('/api/projects/{pid}/midi/{tid}/export')
    def export(pid:str,tid:str,request:Request,format:str='smf'):
        project=project_for_actor(request,pid);track=next((t for t in project.tracks if t.id==tid and t.kind=='midi'),None)
        if not track:raise HTTPException(404,'MIDI track not found')
        if format=='ump':
            import json
            payload={'format':'mta-ump-1','units':'milliseconds','events':[e.model_dump() for e in track.midi_ump]}
            return Response(json.dumps(payload),media_type='application/json',headers={'Content-Disposition':'attachment; filename="track.ump.json"','Cache-Control':'no-store'})
        if track.midi_ump:raise HTTPException(422,'Use lossless UMP JSON export for MIDI 2 events')
        return Response(write_smf(track,project.bpm,project.time_signature),media_type='audio/midi',headers={'Content-Disposition':'attachment; filename="track.mid"','Cache-Control':'no-store'})
