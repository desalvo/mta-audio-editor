"""MTA container adapter with non-destructive DAW rendering."""
import json, subprocess, uuid, tempfile
from pathlib import Path
from .models import Project, Track, Clip
from .storage import attachment_path, audio_path, pdir, save_project
from .audio_engine import media_duration_ms, render_track

MTA8_TYPES = ["drums","bass","guitars","keyboards","orchestra","winds","melody","click"]

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode: raise RuntimeError(p.stderr.strip() or "command failed")
    return p.stdout

def ffprobe(path: Path):
    return json.loads(run(["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)]))

def import_mta(path: Path, project: Project) -> Project:
    d=pdir(project.id); audio=d/"audio"; att=d/"attachments"; info=ffprobe(path)
    audio_streams=[s for s in info.get("streams",[]) if s.get("codec_type")=="audio"]
    tracks=[]
    for i,s in enumerate(audio_streams):
        name=(s.get("tags") or {}).get("title") or f"Track {i+1}"
        typ=(s.get("tags") or {}).get("MTA_TYPE") or (MTA8_TYPES[i] if i < len(MTA8_TYPES) else "other")
        out=audio/f"track-{i+1:02d}.mp3"
        try: run(["ffmpeg","-y","-v","error","-i",str(path),"-map",f"0:a:{i}","-c:a","copy",str(out)])
        except Exception: run(["ffmpeg","-y","-v","error","-i",str(path),"-map",f"0:a:{i}","-c:a","libmp3lame","-q:a","2",str(out)])
        dur=media_duration_ms(out)
        tracks.append(Track(id=uuid.uuid4().hex[:10],name=name,type=typ if typ in Track.model_fields['type'].annotation.__args__ else 'other',
                            filename=out.name,duration_ms=dur,
                            clips=[Clip(id=uuid.uuid4().hex[:10],source_start_ms=0,source_end_ms=dur,timeline_start_ms=0)]))
    preserved=[]
    attachment_streams=[s for s in info.get("streams",[]) if s.get("codec_type")=="attachment"]
    for aidx,s in enumerate(attachment_streams):
        idx=s.get("index"); tags=s.get("tags") or {}; fname=tags.get("filename") or f"attachment-{idx}.bin"
        safe="".join(c for c in fname if c.isalnum() or c in "._-") or f"attachment-{idx}.bin"; out=att/safe
        try:
            run(["ffmpeg","-y","-v","error",f"-dump_attachment:t:{aidx}",str(out),"-i",str(path),"-f","null","-"])
            if out.exists(): preserved.append(out.name)
        except Exception: pass
    project.tracks=tracks; project.preserved_attachments=preserved; project.target="MTA16" if len(tracks)>8 else "MTA8"
    save_project(project); return project

def _metadata_attachment(project: Project) -> Path:
    out=pdir(project.id)/"attachments"/"mta-editor.json"
    out.write_text(json.dumps({
        "schema":"mta-audio-editor/v2","title":project.title,"artist":project.artist,"bpm":project.bpm,"key":project.key,
        "tracks":[{"id":t.id,"name":t.name,"type":t.type,"pan":t.pan,"clips":[c.model_dump() for c in t.clips],"inserts":[x.model_dump() for x in t.inserts]} for t in project.tracks],
        "master":{"volume_db":project.master_volume_db,"inserts":[x.model_dump() for x in project.master_inserts]},
        "lyrics":[x.model_dump() for x in project.lyrics],"chords":[x.model_dump() for x in project.chords],"markers":[x.model_dump() for x in project.markers],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

def export_mta(project: Project, out: Path) -> Path:
    max_tracks=8 if project.target=="MTA8" else 16; tracks=project.tracks[:max_tracks]
    if not tracks: raise ValueError("project has no audio tracks")
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); rendered=[]
        for i,t in enumerate(tracks):
            rw=td/f"track-{i:02d}.wav"; render_track(t,audio_path(project.id, t.filename),rw); rendered.append(rw)
        cmd=["ffmpeg","-y","-v","error"]
        for r in rendered: cmd += ["-i",str(r)]
        any_solo=any(t.solo for t in tracks); filters=[]
        for i,t in enumerate(tracks):
            muted=t.mute or (any_solo and not t.solo); gain="-120dB" if muted else f"{t.volume_db}dB"
            filters.append(f"[{i}:a:0]aformat=channel_layouts=stereo,volume={gain},stereotools=balance_out={t.pan:.4f}[a{i}]")
        cmd += ["-filter_complex",";".join(filters)]
        for i in range(len(tracks)): cmd += ["-map",f"[a{i}]"]
        cmd += ["-c:a","libmp3lame","-q:a","2"]
        for i,t in enumerate(tracks):
            cmd += [f"-metadata:s:a:{i}",f"title={t.name}",f"-metadata:s:a:{i}",f"MTA_TYPE={t.type}"]
        attachments=[]
        for name in project.preserved_attachments:
            try:
                f = attachment_path(project.id, name)
            except ValueError:
                continue
            if f.exists():
                attachments.append(f)
        meta=_metadata_attachment(project)
        if meta not in attachments: attachments.append(meta)
        for a in attachments:
            cmd += ["-attach",str(a),"-metadata:s:t",f"filename={a.name}","-metadata:s:t","mimetype=application/octet-stream"]
        cmd += ["-metadata",f"TITLE={project.title}","-metadata",f"ARTIST={project.artist}","-metadata",f"BPM={project.bpm}","-f","matroska",str(out)]
        run(cmd)
    return out
