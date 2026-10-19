"""Non-destructive audio bounces with snapshot isolation and durable publication."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid
from . import storage
from .vst3_transport import settings as vst_host_settings
from .audio_engine import render_mix, render_track_export,media_duration_ms,waveform_peaks
from .ai_project_lock import project_publication_lock
from .models import Track,Clip,ProjectClip
from .timeline_editing import unique_track_name


def _signature(project,track_id):
    keys={'id','filename','channels','sample_rate','gain_db','volume_db','pan','mute','solo','delay_ms','clips','inserts','master_bypass','kind','instrument','midi_notes','midi_controls','midi_sysex','midi_ump','mpe_zone','mpe_members','mpe_pitch_bend','midi_route'}
    from .vst3_sidechain import enabled
    tracks=[t.model_dump(mode='json',include=keys) for t in project.tracks if track_id is None or t.id==track_id or enabled(project)]
    if not tracks:raise ValueError('Track not found')
    # Ignore editorial/UI changes; audio-affecting concurrent edits reject publication.
    return json.dumps({'tracks':tracks,'rate':project.sample_rate,
        'transport':vst_host_settings(project),
        'master':None if track_id else [i.model_dump(mode='json') for i in project.master_inserts],
        'volume':None if track_id else project.master_volume_db,
        'end':None if track_id else project.timeline_end_ms,
        'fades':None if track_id else [project.master_fade_enabled,project.master_fade_in_ms,project.master_fade_out_ms]},sort_keys=True)


def bounce(pid,track_id=None,*,capacity_check=lambda owner,size:None):
    with tempfile.TemporaryDirectory(prefix='mta-bounce-') as scratch:
        folder=Path(scratch);identities={}
        with project_publication_lock(pid):
            snapshot=storage.load_project(pid).model_copy(deep=True)
            signature=_signature(snapshot,track_id)
            selected=[t for t in snapshot.tracks if track_id is None or t.id==track_id]
            from .vst3_sidechain import enabled
            for t in (snapshot.tracks if enabled(snapshot) else selected):
                source=storage.audio_path(pid,t.filename)
                if source.is_symlink() or not source.is_file():raise ValueError('Source audio unavailable')
                stat=source.stat()
                identities[t.filename]=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)
                destination=folder/t.filename
                if not destination.exists():shutil.copyfile(source,destination)
        output=folder/('bounce-'+uuid.uuid4().hex+'.wav')
        host_transport=vst_host_settings(snapshot)
        if track_id:
            original=selected[0].model_copy(deep=True)
            original.mute=False;original.solo=False
            from .vst3_sidechain import enabled,render as sidechain_render
            if enabled(snapshot):
                # Bake only the target track output, with its sidechain sources.
                snapshot.base_bpm=snapshot.bpm;snapshot.pitch_semitones=0
                sidechain_render(snapshot,lambda _pid,name:folder/name,output,track_id=track_id,host_transport=host_transport)
            else:render_track_export(original,folder/original.filename,output,fmt='wav',
                sample_rate=snapshot.sample_rate,wav_bit_depth=32,host_transport=vst_host_settings(snapshot))
            label=original.name+' Bounce'
        else:
            # Project tempo/pitch is applied by playback once, not baked twice.
            snapshot.base_bpm=snapshot.bpm;snapshot.pitch_semitones=0
            render_mix(snapshot,lambda _pid,name:folder/name,output,fmt='wav',
                       sample_rate=snapshot.sample_rate,wav_bit_depth=32,host_transport=host_transport)
            label='Project Bounce'
        duration=media_duration_ms(output);peaks=waveform_peaks(output)
        with project_publication_lock(pid):
            project=storage.load_project(pid)
            if _signature(project,track_id)!=signature:raise ValueError('Audio changed during bounce; retry')
            for name,identity in identities.items():
                stat=storage.audio_path(pid,name).stat()
                if (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)!=identity:
                    raise ValueError('Source audio changed during bounce; retry')
            capacity_check(project.owner_user_id,output.stat().st_size)
            from . import ai_upload_transaction,ai_media_identity
            filename=uuid.uuid4().hex[:10]+'.wav';destination=storage.audio_path(pid,filename)
            ai_upload_transaction.begin(pid)
            try:
                with output.open('rb') as source,destination.open('xb') as target:
                    ai_media_identity.record_upload(pid,destination)
                    shutil.copyfileobj(source,target);target.flush();os.fsync(target.fileno())
                track=Track(id=uuid.uuid4().hex[:12],name=unique_track_name(project,label),
                    filename=filename,channels=2,sample_rate=project.sample_rate,duration_ms=duration,
                    mute=True,master_bypass=track_id is None or selected[0].master_bypass,clips=[Clip(id=uuid.uuid4().hex[:12],source_end_ms=duration)],
                    waveform_peaks=peaks)
                if track_id:
                    index=next(i for i,t in enumerate(project.tracks) if t.id==track_id)
                    project.tracks.insert(index+1,track)
                else:project.tracks.append(track)
                asset=ProjectClip(id=uuid.uuid4().hex[:12],name=track.name,filename=filename,
                    duration_ms=duration,channels=2,channel_layout='stereo',provenance='Bounce',
                    current_location='audio/'+filename)
                project.clip_library.append(asset);track.source_clip_id=asset.id
                storage.save_project(project)
            except BaseException:
                # Journal reconciliation checks persisted references, preserving
                # a save that reached atomic replace before a late error.
                ai_upload_transaction.reconcile(pid)
                raise
            ai_upload_transaction.finish(pid)
            return {'project_id':pid,'track_id':track.id,'muted':True}
