"""Recoverable project music workflows on the existing global AI queue."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import uuid

from fastapi import HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal

from . import ai_arranger_runtime as queue
from .music_interchange import MusicPart,MusicResult,parse_result,no_notes
from .music_publication import revision

OPERATION='worker:studio-music'


def studio_policy():
    from .studio_catalog import root
    path=root()/'policy.json'
    if path.is_symlink():raise ValueError('Unsafe studio policy')
    data=json.loads(path.read_text()) if path.is_file() else {}
    return {'timeout_seconds':max(60,min(14400,int(data.get('timeout_seconds',3600)))),
            'retention_days':max(1,min(365,int(data.get('retention_days',7))))}


class StudioRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    operation:Literal['audio-to-midi','vocal-harmony','vocal-synthesis']
    track_ids:list[str]=Field(min_length=1,max_length=32)
    start_ms:int=Field(default=0,ge=0,le=86400000)
    end_ms:int=Field(gt=0,le=86400000)
    settings:dict=Field(default_factory=dict,max_length=20)
    # Optional per-source lyrics, keyed by actual selected MIDI track ID.
    singer_lyrics:dict[str,list[str]]=Field(default_factory=dict,max_length=32)
    singer_texts:dict[str,str]=Field(default_factory=dict,max_length=8)
    singer_melismas:dict[str,list[int]]=Field(default_factory=dict,max_length=8)
    programs:dict[str,int]=Field(default_factory=dict,max_length=32)
    mode:Literal['fast','accurate','maximum']='fast'
    transcriber:Literal['default','basic-pitch','yourmt3','mr-mt3','transkun']='default'
    specialist_asset:str=Field(default='',pattern=r'^$|^[a-z][a-z0-9-]{0,63}$')
    auto_import:bool=True
    retry_of:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')


def folder(job_id):
    if not re.fullmatch('[a-f0-9]{32}',job_id):raise ValueError('Invalid studio job identifier')
    root=queue._ROOT/'studio'
    if root.is_symlink():raise ValueError('Unsafe studio result directory')
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    result=root/job_id
    if result.is_symlink():raise ValueError('Unsafe studio job directory')
    return result


def purge(job_id):
    path=folder(job_id)
    if path.exists():shutil.rmtree(path)


def cleanup_expired(now=None):
    """Only completed private intermediates expire; committed project media stays."""
    now=time.time() if now is None else now
    cutoff=now-studio_policy()['retention_days']*86400
    parent=queue._ROOT/'studio'
    if not parent.is_dir() or parent.is_symlink():return 0
    removed=0
    for path in parent.iterdir():
        if path.is_symlink() or not path.is_dir() or not re.fullmatch('[a-f0-9]{32}',path.name):continue
        with queue._db() as con:
            row=con.execute('SELECT state,completed_at FROM jobs WHERE job_id=?',(path.name,)).fetchone()
        if row and row['state'] not in ('completed','failed','cancelled','interrupted'):continue
        # Unknown/orphan directories also get the full grace period.
        stamp=(row['completed_at'] if row else None) or path.stat().st_mtime
        if stamp<cutoff:
            purge(path.name);removed+=1
    return removed


def project_for_user(pid,user_id):
    from .storage import load_project,project_access
    from .auth import get_user
    project=load_project(pid)
    if user_id==0 and os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true':return project
    user=get_user(user_id)
    if not user or not user['active'] or not project_access(project,user_id,user['role']):
        raise ValueError('Project permission was revoked')
    return project


def result_file(job_id):return folder(job_id)/'result.json'


def load_result(job_id):
    path=result_file(job_id)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>16*1024*1024:
        raise ValueError('Studio result not available')
    return parse_result(path.read_bytes())


def update(progress,phase,message,done,total,**usage):
    from .storage import _atomic_json_write
    _atomic_json_write(progress,{'phase':phase,'message':message,'progress_source':'studio-sources',
         'steps_completed':done,'steps_total':total,'progress_percent':None,'progress_estimated':False,**usage})


def midi_region(track,start,end):
    from .audio_engine import ensure_clips
    ensure_clips(track);notes=[]
    for clip in track.clips:
        for note in track.midi_notes:
            a=max(note.start_ms,clip.source_start_ms);b=min(note.start_ms+note.duration_ms,clip.source_end_ms)
            at=clip.timeline_start_ms+track.delay_ms+a-clip.source_start_ms
            left=max(start,at);right=min(end,at+b-a)
            if b>a and right>left:
                notes.append(note.model_copy(update={'id':hashlib.sha256((clip.id+':'+note.id).encode()).hexdigest()[:24],
                                                     'start_ms':left-start,'duration_ms':right-left}))
    return notes


def executor(pid,payload,job_id,publish):
    request=StudioRequest.model_validate(payload['request']);owner=payload['actor_user_id']
    def run(progress,stop):
        from .storage import audio_path,_atomic_json_write
        from .studio_compute import compute
        from .ai_project_lock import project_publication_lock
        with project_publication_lock(pid):
            project=project_for_user(pid,owner)
            if revision(project)!=payload['expected_revision']:raise ValueError('Project changed before execution; submit the current source again')
        started=time.monotonic();timeout=int(payload['timeout_seconds']);directory=folder(job_id);directory.mkdir(mode=0o700,exist_ok=True)
        def cancelled():return stop.is_set() or time.monotonic()-started>timeout
        def check():
            if cancelled():raise RuntimeError('Studio job cancelled or exceeded its wall-clock budget')
        parts=[];alternatives=[];warnings=[];count=len(request.track_ids);local_cpu=0.;local_gpu=0.;has_gpu=False
        try:
            with tempfile.TemporaryDirectory(prefix='mta-studio-input-') as raw:
                for index,tid in enumerate(request.track_ids):
                    check();track=next(t for t in project.tracks if t.id==tid)
                    cache=directory/f'part-{index}.json'
                    cached=False;previous=None;old_request=None;new_request=None;recovery_allowed=False
                    if request.retry_of:
                        previous=queue.read_payload(request.retry_of)
                        if previous and previous.get('actor_user_id')==owner and previous.get('project')==pid:
                            old_request={**previous['request'],'retry_of':None};new_request={**request.model_dump(),'retry_of':None}
                            recovery_allowed=old_request==new_request and previous['expected_revision']==payload['expected_revision']
                            old=folder(request.retry_of)/f'part-{index}.json'
                            if request.operation=='vocal-harmony' and recovery_allowed and old.is_file() and not old.is_symlink() and old.stat().st_size<=16*1024*1024:
                                cache.write_bytes(old.read_bytes());cached=True
                    update(progress,'preparing-source',f'Preparing source {index+1}/{count}: {track.name}',index,count)
                    if cached:
                        result=parse_result(cache.read_bytes())
                    elif request.operation in ('vocal-harmony','vocal-synthesis'):
                        from .studio_score import Score
                        notes=midi_region(track,request.start_ms,request.end_ms)
                        score=Score(music=MusicResult(parts=[MusicPart(id='melody',name=track.name,notes=notes)]),
                            chords=[c.model_copy(update={'time_ms':max(0,c.time_ms-request.start_ms),
                             'end_ms':max(0,c.end_ms-request.start_ms) if c.end_ms is not None else None})
                             for c in project.chords if c.time_ms<request.end_ms and (c.end_ms is None or c.end_ms>request.start_ms)])
                        source_settings=dict(request.settings)
                        if request.operation=='vocal-synthesis' and source_settings.get('neural_banks'):
                            source_settings['neural_bank']=source_settings.pop('neural_banks')[index]
                        if request.operation=='vocal-synthesis' and source_settings.get('voice_banks'):
                            source_settings['voicebank']=source_settings.pop('voice_banks')[index]
                        if request.operation=='vocal-synthesis' and request.singer_texts:
                            source_settings['lyric_text']=request.singer_texts[tid]
                            source_settings['melisma_counts']=request.singer_melismas.get(tid,[])
                        if request.operation=='vocal-synthesis' and request.singer_lyrics:
                            source_settings['syllables']=request.singer_lyrics[tid]
                            source_settings.pop('voice_syllables',None)
                        result,meta=compute(owner,request.operation,{'kind':request.operation,'settings':source_settings},
                             score=score.model_dump_json().encode(),cancelled=cancelled,timeout=max(1,int(timeout-(time.monotonic()-started))),progress=progress)
                    else:
                        from .studio_audio import prepare
                        target=Path(raw)/f'source-{index}.wav'
                        if not prepare(track,audio_path(pid,track.filename),request.start_ms,request.end_ms,target,cancelled):
                            warnings.append('No audio in selected region: '+track.name);continue
                        options={**request.settings,'name':track.name}
                        if tid in request.programs:options['program']=request.programs[tid]
                        from .studio_stage_cache import StageCache
                        prior=folder(request.retry_of)/f'stages-{index}' if recovery_allowed else None
                        stages=StageCache(directory/f'stages-{index}',prior)
                        if request.mode=='fast':
                            backend=request.transcriber
                            kind='audio-to-midi' if backend=='default' else 'audio-to-midi-'+backend
                            selected_options=({'name':track.name,'asset_id':request.specialist_asset} if backend=='transkun'
                                              else {'name':track.name} if backend in ('yourmt3','mr-mt3') else options)
                            result,meta=stages.execute(compute,owner,kind,{'kind':kind,'options':selected_options},audio=target.read_bytes(),
                               cancelled=cancelled,timeout=max(1,int(timeout-(time.monotonic()-started))),progress=progress)
                        elif request.mode=='maximum':
                            from .studio_multitrack import transcribe_separated
                            result,meta=transcribe_separated(owner,target.read_bytes(),options,cancelled=cancelled,cache=stages,
                                timeout=max(1,int(timeout-(time.monotonic()-started))),progress=progress,specialist_asset=request.specialist_asset)
                            _atomic_json_write(directory/f'separation-{index}.json',meta['separation_report'])
                        else:
                            hypotheses=[];aggregate={};acknowledgements=[]
                            for backend in (['yourmt3','basic-pitch']+(['transkun'] if request.specialist_asset else [])):
                                check();kind='audio-to-midi-'+backend
                                update(progress,'transcribing-'+backend,f'{backend}: source {index+1}/{count}',index,count)
                                variant_options=({'name':track.name,'asset_id':request.specialist_asset} if backend=='transkun' else
                                                 {'name':track.name} if backend=='yourmt3' else options)
                                model_cache=directory/f'model-{index}-{backend}.json'
                                hypothesis,measurement=stages.execute(compute,owner,kind,{'kind':kind,'options':variant_options},audio=target.read_bytes(),
                                    cancelled=cancelled,timeout=max(1,int(timeout-(time.monotonic()-started))),progress=progress)
                                # Save each completed model before acknowledging a remote response.
                                _atomic_json_write(model_cache,hypothesis.model_dump(mode='json'))
                                if callable(measurement.get('acknowledge')):measurement['acknowledge']()
                                for metric,value in measurement.get('usage',{}).items():
                                    if metric in ('cpu_seconds','gpu_seconds'):aggregate[metric]=aggregate.get(metric,0)+value
                                hypotheses.append((backend,hypothesis))
                            from .music_reconciliation import reconcile
                            check();result,report=reconcile(hypotheses)
                            _atomic_json_write(directory/f'reconciliation-{index}.json',report)
                            for acknowledge in acknowledgements:acknowledge()
                            meta={'usage':aggregate}
                        target.unlink(missing_ok=True)
                    if not cached:
                        usage=meta.get('usage',{});local_cpu+=usage.get('cpu_seconds',0)
                        if usage.get('gpu_seconds') is not None:local_gpu+=usage['gpu_seconds'];has_gpu=True
                    check()
                    _atomic_json_write(cache,result.model_dump(mode='json'))
                    if request.operation=='vocal-synthesis':
                        mapping=json.loads((directory/'audio.json').read_text()) if (directory/'audio.json').is_file() else {}
                        for voice_index,(part_id,data) in enumerate(meta.get('audio_artifacts',{}).items()):
                            name=f'source-{index}-voice-{voice_index}.wav'
                            with (directory/name).open('wb') as output:
                                output.write(data);output.flush();os.fsync(output.fileno())
                            mapping[f'source-{index}-'+part_id[:40]]=name
                        _atomic_json_write(directory/'audio.json',mapping)
                        generation_path=directory/'singing.json'
                        generation=json.loads(generation_path.read_text()) if generation_path.is_file() else {
                            'schema':'mta-multi-singer-generation-1','backend':source_settings.get('backend','oddvoices'),'sources':{},'part_sources':{},'region_start_ms':request.start_ms}
                        generation['sources'][tid]=meta['singing_metadata']
                        for part in result.parts:generation['part_sources'][f'source-{index}-'+part.id[:40]]=tid
                        _atomic_json_write(generation_path,generation)
                    if not cached and callable(meta.get('acknowledge')):meta['acknowledge']()
                    for part in result.parts:
                        parts.append(part.model_copy(update={'id':f'source-{index}-'+part.id[:40],'name':part.name}))
                    for part in result.alternatives:
                        alternatives.append(part.model_copy(update={'id':f'source-{index}-'+part.id[:40]}))
                    warnings.extend(result.warnings)
                    update(progress,'source-complete',f'Completed {index+1}/{count} sources',index+1,count,**({'cpu_seconds':local_cpu,**({'gpu_seconds':local_gpu} if has_gpu else {})} if owner==0 else {}))
            check()
            result=(MusicResult(parts=parts,alternatives=alternatives,offset_ms=request.start_ms,warnings=warnings[:200])
                    if parts else no_notes(warnings[:200]).model_copy(update={'offset_ms':request.start_ms}))
            _atomic_json_write(result_file(job_id),result.model_dump(mode='json'))
            imported=False;reason='Review and import the available result'
            if not result.parts:reason='No notes detected; no project tracks were created'
            if request.auto_import and result.parts:
                with project_publication_lock(pid):
                    current=project_for_user(pid,owner)
                    if revision(current)==payload['expected_revision']:
                        # Cancellation can win before this claim. Once the atomic
                        # publication starts, cancellation is explicitly rejected.
                        with queue._db() as con:
                            con.execute('BEGIN IMMEDIATE')
                            row=con.execute('SELECT cancel_requested FROM jobs WHERE job_id=?',(job_id,)).fetchone()
                            if not row or row[0]:con.execute('ROLLBACK');raise RuntimeError('Job cancelled before publication')
                            con.execute("UPDATE jobs SET phase='studio-committing' WHERE job_id=?",(job_id,));con.execute('COMMIT')
                        if request.operation=='vocal-synthesis':publish(current,job_id,payload['expected_revision'],result,audio=load_audio(job_id),generation=json.loads((directory/'singing.json').read_text()))
                        else:publish(current,job_id,payload['expected_revision'],result)
                        imported=True;reason='Musical results saved in the project'
                    else:reason='Project changed; result retained for explicit review and import'
            _atomic_json_write(directory/'publication.json',{'imported':imported,'reason':reason,'created_at':time.time()})
            update(progress,'results-saved',reason,count,count,**({'cpu_seconds':local_cpu,**({'gpu_seconds':local_gpu} if has_gpu else {})} if owner==0 else {}))
        except BaseException:
            if stop.is_set():result_file(job_id).unlink(missing_ok=True)
            raise
    return run


def register_routes(app,project_for_actor,actor,publish):
    def authorized(pid,job_id,request):
        if not re.fullmatch('[a-f0-9]{32}',job_id):raise HTTPException(404,'Studio job not found')
        project_for_actor(request,pid);identity=actor(request);data=queue.read_payload(job_id)
        if not data or data.get('project')!=pid or (data.get('actor_user_id')!=identity['id'] and identity['role']!='admin'):
            raise HTTPException(404,'Studio job not found')
        return data

    @app.get('/api/ai/studio/capabilities')
    def capabilities(request:Request,operation:str=''):
        actor(request)
        from .studio_catalog import capabilities
        from .native_ai_routing import is_remote,_read
        if operation in ('vocal-synthesis','vocal-harmony','audio-to-midi') and os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true' and is_remote(operation):
            from .ai_remote_client import studio_capabilities,RemoteAIError
            cfg=_read()['workers'][operation]
            try:return {**studio_capabilities(cfg['url'],cfg['token']),'execution':'remote'}
            except (RemoteAIError,ValueError) as exc:raise HTTPException(503,str(exc)) from exc
        return capabilities()

    @app.post('/api/projects/{pid}/ai-studio/jobs')
    def start(pid:str,body:StudioRequest,request:Request):
        project=project_for_actor(request,pid);user=actor(request)
        from .project_kinds import require_kind
        require_kind(project, "midi")
        if body.operation == "vocal-synthesis":require_kind(project, "audio")
        if body.end_ms<=body.start_ms or body.end_ms-body.start_ms>600000:raise HTTPException(422,'Select a region of 1 ms to 10 minutes')
        if len(set(body.track_ids))!=len(body.track_ids):raise HTTPException(422,'Duplicate source tracks')
        tracks=[next((t for t in project.tracks if t.id==tid),None) for tid in body.track_ids]
        if any(t is None or t.kind!=('audio' if body.operation=='audio-to-midi' else 'midi') for t in tracks):raise HTTPException(422,'Select source tracks of the required type')
        if body.operation=='vocal-harmony' and len(tracks)!=1:raise HTTPException(422,'Select one melody MIDI track')
        if any(key not in body.track_ids or type(value) is not int or not 0<=value<=127 for key,value in body.programs.items()):raise HTTPException(422,'Invalid program assignment')
        from .ai_worker_registry import execution_available
        from .native_ai_routing import is_remote
        remote=os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true' and is_remote(body.operation)
        primary_kind=('audio-to-midi-basic-pitch' if body.operation=='audio-to-midi' and body.mode!='fast' else
                      'audio-to-midi-'+body.transcriber if body.operation=='audio-to-midi' and body.transcriber!='default' else body.operation)
        if not remote and not execution_available(primary_kind):raise HTTPException(503,'Model not installed or disabled; contact the administrator or install it from Studio models')
        if body.operation=='audio-to-midi' and body.mode=='fast' and (body.transcriber if body.transcriber!='default' else os.getenv('MTA_STUDIO_TRANSCRIBER','basic-pitch'))=='basic-pitch' and any(t.type in ('drums','click') for t in tracks):raise HTTPException(422,'Basic Pitch does not transcribe percussion; select pitched source tracks')
        from .vocal_harmony import HarmonySettings
        if body.operation=='vocal-synthesis':
            try:
                from .vocal_synthesis import Settings
                from .vocal_banks import bank
                cfg=Settings.model_validate(body.settings)
                if body.singer_melismas:
                    if set(body.singer_melismas)-set(body.singer_texts) or any(len(v)>10000 or any(type(n) is not int or not 1<=n<=100 for n in v) for v in body.singer_melismas.values()):raise ValueError('Invalid independent melisma counts')
                if body.singer_texts:
                    if set(body.singer_texts)!=set(body.track_ids) or any(not t.strip() or len(t)>5000 for t in body.singer_texts.values()):raise ValueError('Provide full lyric text for every selected singer')
                    if cfg.pronunciation!='espeak' or cfg.backend!='diffsinger' or cfg.language=='vocalise':raise ValueError('Full text alignment requires DiffSinger eSpeak')
                    if body.singer_lyrics or cfg.syllables:raise ValueError('Choose text or note-aligned syllables')
                if body.singer_lyrics:
                    if cfg.language=='vocalise':raise ValueError('Independent singer lyrics require a lyric language')
                    if set(body.singer_lyrics)!=set(body.track_ids):raise ValueError('Provide independent lyrics for each selected singer track')
                    if any(len(v)>20000 or any(not isinstance(x,str) or not x.strip() or len(x)>500 for x in v) for v in body.singer_lyrics.values()):
                        raise ValueError('Invalid independent singer lyrics')
                if cfg.neural_banks and len(cfg.neural_banks)!=len(tracks):raise ValueError('Provide one neural voicebank per selected singer')
                if cfg.voice_banks and len(cfg.voice_banks)!=len(tracks):raise ValueError('Provide one voicebank per selected singer')
                if not remote:
                    if cfg.backend in ('neural-external','diffsinger'):
                        from .neural_vocal_adapter import checked_assets
                        if cfg.backend=='neural-external': checked_assets()
                        elif cfg.neural_bank or cfg.neural_banks:
                            from .studio_asset_registry import manifest,policies
                            for asset_id in (cfg.neural_banks or [cfg.neural_bank]):
                                value=manifest(asset_id)
                                if value['kind']!='diffsinger' or cfg.language not in value['languages']:raise ValueError('Incompatible neural voicebank/language')
                                policies(asset_id)
                        else:
                            from .diffsinger_bridge import safe_file
                            safe_file(os.environ.get('MTA_NEURAL_SINGER_CHECKPOINT',''),os.environ.get('MTA_NEURAL_SINGER_SHA256',''))
                    else:
                        for voice in (cfg.voice_banks or [cfg.voicebank]):bank(voice)
                if len(project.tracks)+len(tracks)*2>64:raise ValueError('Audio plus editable MIDI would exceed the 64-track project limit')
                expected_bytes=0
                for track in tracks:
                    notes=sorted(midi_region(track,body.start_ms,body.end_ms),key=lambda n:n.start_ms)
                    if not notes:raise ValueError('Selected region contains empty vocal parts')
                    if any(n.duration_ms>30000 or not 16<=n.pitch<=111 for n in notes):raise ValueError('Singing requires pitches 16–111 and notes up to 30 seconds; split longer notes')
                    if any(b.start_ms<a.start_ms+a.duration_ms-.01 for a,b in zip(notes,notes[1:])):raise ValueError('Split polyphonic MIDI into monophonic singer parts')
                    if cfg.language!='vocalise' and not (cfg.lyric_text or body.singer_texts) and len(body.singer_lyrics.get(track.id,cfg.syllables))!=len(notes):raise ValueError('Assign one English syllable per note in each selected part')
                    expected_bytes+=int((max(n.start_ms+n.duration_ms for n in notes)+300)*48)*3+44
                if expected_bytes>queue.artifact_limit_mib()*1024*1024:
                    raise ValueError('Vocal audio exceeds the configured artifact budget; reduce the region/parts or ask the administrator to raise the maximum artifact size')
            except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        elif body.operation=='vocal-harmony':
            try:
                from .vocal_harmony import pitch_classes
                cfg=HarmonySettings.model_validate(body.settings);pitch_classes(cfg.key)
                if not midi_region(tracks[0],body.start_ms,body.end_ms):raise ValueError('Selected region contains no melody notes')
            except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        else:
            from .studio_parameters import TranscriptionSettings
            try:
                selected_transcriber=(body.transcriber if body.transcriber!='default' else os.getenv('MTA_STUDIO_TRANSCRIBER','basic-pitch')) if body.mode=='fast' else 'basic-pitch'
                if selected_transcriber in ('yourmt3','mr-mt3','transkun'):
                    if body.settings or body.programs:raise ValueError('Selected model uses its own instrument identity; Basic Pitch thresholds/program overrides do not apply')
                if selected_transcriber=='transkun' and not body.specialist_asset:raise ValueError('Select an installed Transkun piano asset')
                if body.specialist_asset and not remote:
                    from .studio_asset_registry import manifest,policies
                    if manifest(body.specialist_asset)['kind']!='transkun':raise ValueError('Select a Transkun piano asset')
                    policies(body.specialist_asset)
                if selected_transcriber=='basic-pitch':TranscriptionSettings.model_validate(body.settings)
            except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        if body.mode!='fast':
            if body.operation!='audio-to-midi':raise HTTPException(422,'Multi-model mode applies to transcription only')
            if not remote and any(not execution_available('audio-to-midi-'+backend) for backend in ('basic-pitch','yourmt3')):
                raise HTTPException(503,'Accurate mode requires both YourMT3 and Basic Pitch; install and enable both models')
            if body.mode=='maximum':
                if not (user['id']==0 and is_remote('demucs')) and not execution_available('demucs'):
                    raise HTTPException(503,'Maximum mode also requires the installed Demucs htdemucs separation worker')
        from .model_license_policy import evaluate,LicenseDenied,admission
        try:
            if remote:
                from .model_license_policy import authorize_remote_execution
                decision=authorize_remote_execution(body.operation, {'settings':body.settings})
            else:decision=(evaluate('audio-to-midi-yourmt3',{})
                      if body.operation=='audio-to-midi' and body.mode!='fast' else
                      evaluate('audio-to-midi-'+body.transcriber,{'options':{'asset_id':body.specialist_asset}})
                      if body.operation=='audio-to-midi' and body.transcriber!='default'
                      else evaluate(body.operation,{'settings':body.settings}))
            if not remote and body.operation=='audio-to-midi' and body.mode!='fast':
                component_decisions=[evaluate('audio-to-midi-'+backend,{}) for backend in ('yourmt3','basic-pitch')]
                if body.specialist_asset:component_decisions.append(evaluate('audio-to-midi-transkun',{'options':{'asset_id':body.specialist_asset}}))
                if body.mode=='maximum':component_decisions.append(evaluate('demucs',{'model':'htdemucs'}))
                if any(not item.billable for item in component_decisions):
                    decision=next(item for item in component_decisions if not item.billable)
            if user['id']>0 and not decision.billable and body.auto_import:raise ValueError('Free-only model results must be downloaded without project storage charges; disable automatic import')
        except (LicenseDenied,ValueError) as exc:raise HTTPException(422,str(exc)) from exc
        policy=studio_policy()
        payload={'schema_version':1,'actor_user_id':user['id'],'project':pid,'request':body.model_dump(),
                 'expected_revision':revision(project),'timeout_seconds':policy['timeout_seconds'],'license_mode':decision.mode}
        if body.retry_of:authorized(pid,body.retry_of,request)
        job_id=uuid.uuid4().hex
        from .resource_access import CreditAdmissionError
        try:
            with admission(decision):
                accepted,job=queue.start(pid,OPERATION,executor(pid,payload,job_id,publish),job_id=job_id,cancellable=True,payload=payload)
        except CreditAdmissionError as exc:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=402,content={'code':exc.code,'detail':str(exc),
                'action':'Review your subscription and credits in your profile, or contact the administrator',
                'url':'/account#subscriptions'})
        return {'accepted':accepted,'job':job,'job_id':job_id}

    @app.get('/api/projects/{pid}/ai-studio/jobs/{job_id}')
    def status(pid:str,job_id:str,request:Request):
        authorized(pid,job_id,request)
        result={'job':queue.get(job_id),'result_available':result_file(job_id).is_file()}
        path=folder(job_id)/'publication.json'
        if path.is_file() and not path.is_symlink():result.update(json.loads(path.read_text()))
        return result

    @app.post('/api/projects/{pid}/ai-studio/jobs/{job_id}/cancel')
    def cancel(pid:str,job_id:str,request:Request):
        authorized(pid,job_id,request)
        try:return queue.cancel(job_id)
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc

    @app.get('/api/projects/{pid}/ai-studio/jobs/{job_id}/result')
    def result(pid:str,job_id:str,request:Request):
        authorized(pid,job_id,request)
        try:return load_result(job_id)
        except ValueError as exc:raise HTTPException(404,str(exc)) from exc

    @app.post('/api/projects/{pid}/ai-studio/jobs/{job_id}/import')
    def import_result(pid:str,job_id:str,body:dict,request:Request):
        original=authorized(pid,job_id,request)
        if not load_result(job_id).parts:raise HTTPException(422,'No notes detected; there are no tracks to import')
        if original.get('actor_user_id',0)>0 and original.get('license_mode')=='free_only':
            raise HTTPException(422,'Free-only results are downloadable without project storage charges; server project import is disabled')
        if set(body)!={'expected_revision'}:raise HTTPException(422,'Current reviewed project revision required')
        from .ai_project_lock import project_publication_lock
        with project_publication_lock(pid):
            options={'audio':load_audio(job_id),'generation':json.loads((folder(job_id)/'singing.json').read_text())} if (folder(job_id)/'audio.json').is_file() else {}
            published=publish(project_for_actor(request,pid),job_id,body['expected_revision'],load_result(job_id),**options)
            from .storage import _atomic_json_write
            _atomic_json_write(folder(job_id)/'publication.json',{'imported':True,'reason':'Musical results saved in the project','created_at':time.time()})
            return published

    @app.get('/api/projects/{pid}/ai-studio/jobs/{job_id}/artifacts.zip')
    def download_artifacts(pid:str,job_id:str,request:Request):
        authorized(pid,job_id,request)
        import io,zipfile
        from fastapi.responses import Response
        result=load_result(job_id)
        audio=load_audio(job_id) if (folder(job_id)/'audio.json').is_file() else {}
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('music.json',result.model_dump_json())
            metadata=folder(job_id)/'singing.json'
            if metadata.is_file():
                from .ai_worker_artifacts import _read_private_file
                archive.writestr('singing.json',_read_private_file(metadata,32*1024*1024))
            for index,part in enumerate(result.parts):
                if part.id in audio:archive.writestr(f'voice-{index+1}.wav',audio[part.id])
        return Response(output.getvalue(),media_type='application/zip',headers={
            'Content-Disposition':f'attachment; filename="mta-studio-{job_id}.zip"','Cache-Control':'private, no-store'})

    @app.get('/api/projects/{pid}/ai-studio/jobs/{job_id}/diagnostics.zip')
    def diagnostics_zip(pid:str,job_id:str,request:Request):
        authorized(pid,job_id,request)
        import io,zipfile
        from fastapi.responses import Response
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('job.json',json.dumps(queue.get(job_id),indent=2,ensure_ascii=False))
            archive.writestr('README.txt','MTA 0.3.0-r210 Studio diagnostics. Job state and resource counters; no credentials or source audio. Worker exit details are in the server journal.\n')
            path=folder(job_id)/'publication.json'
            if path.is_file() and not path.is_symlink():archive.writestr('publication.json',path.read_bytes())
        return Response(output.getvalue(),media_type='application/zip',headers={'Content-Disposition':f'attachment; filename="mta-studio-{job_id}.zip"'})

    @app.get('/api/projects/{pid}/ai-studio/jobs/{job_id}/diagnostics')
    def diagnostics(pid:str,job_id:str,request:Request):
        authorized(pid,job_id,request)
        return {'job':queue.get(job_id),'protocol':'mta-music-1','result_available':result_file(job_id).is_file()}

    queue.register_restorer(OPERATION,lambda pid,payload,jid:executor(pid,payload,jid,publish))


def load_audio(job_id):
    directory=folder(job_id);path=directory/'audio.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size>32768:raise ValueError('Vocal artifact index unavailable')
    mapping=json.loads(path.read_text())
    if not isinstance(mapping,dict) or not 1<=len(mapping)<=32:raise ValueError('Invalid vocal artifact index')
    from .ai_worker_artifacts import _read_private_file
    from .ai_payload_limits import MAX_ARTIFACT_BYTES,worker_artifact_bytes
    limit=worker_artifact_bytes(MAX_ARTIFACT_BYTES);total=0;result={}
    for key,name in mapping.items():
        if not isinstance(key,str) or not isinstance(name,str) or not re.fullmatch(r'source-[0-9]+-voice-[0-9]+\.wav',name):raise ValueError('Unsafe vocal artifact name')
        data=_read_private_file(directory/name,limit);total+=len(data)
        if total>limit:raise ValueError('Vocal artifact result exceeds configured limit')
        result[key]=data
    return result
