from __future__ import annotations

import hashlib, json, shutil, subprocess, uuid
from pathlib import Path
import numpy as np

from . import storage
from .audio_engine import media_duration_ms, render_track, waveform_peaks
from .models import Clip, Project, SampleEditRequest, SampleEffectRequest, Track

EQ_BANDS=[20,25,31,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250,1600,2000,2500,3150,4000,5000,6300,8000,10000,12500,16000,18000,20000]
EQ_PRESETS={
 "flat":[0]*32,
 "vocals":[-4,-3,-2,-1,0,0,0,-1,-1,-1,-1,0,0,0,0,.5,1,1.5,2,2.5,2.5,2,1.5,1,1,1,1.5,1.5,1,.5,0,-1],
 "clarity":[-3,-2,-1,0,0,0,-1,-1,-1,-1,0,0,0,0,0,.5,1,1.5,2,2,2,2,1.5,1,1,1.5,2,2,1.5,1,0,-1],
 "warm":[0,.5,1,1.5,2,2,2,1.5,1,.5,0,-.5,-1,-1,-.5,0,0,0,0,0,0,0,0,0,.5,.5,0,0,-.5,-1,-1,-2],
 "smile":[2,2,2,1.5,1.5,1,.5,0,-.5,-1,-1,-1,-1,-1,-.5,0,0,0,0,0,0,0,0,.5,1,1.5,2,2.5,2.5,2,1.5,1],
}
PRESETS={"pitch":["subtle","up-semitone","down-semitone","up-octave","down-octave"],"autotune":["gentle","balanced","hard"],"normalizer":["streaming","broadcast","music","gentle"],"maximizer":["gentle","balanced","loud","live"],"eq32":list(EQ_PRESETS)}


def run(cmd:list[str])->None:
 p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 if p.returncode: raise RuntimeError(p.stderr[-1200:] or "audio processing failed")

def sample_rate(path:Path)->int:
 p=subprocess.run(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=sample_rate","-of","default=nw=1:nk=1",str(path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:return max(8000,min(384000,int(p.stdout.strip())))
 except (ValueError,TypeError):return 44100

def rendered_source(pid:str,track:Track)->Path:
 src=storage.audio_path(pid,track.filename)
 cache=storage.pdir(pid)/f".sample-editor-{track.id}.wav"; stamp=cache.with_suffix(".json")
 sig=hashlib.sha256(json.dumps({"f":track.filename,"d":track.duration_ms,"c":[x.model_dump() for x in track.clips],"m":src.stat().st_mtime_ns},sort_keys=True).encode()).hexdigest()
 try:
  if cache.exists() and stamp.exists() and json.loads(stamp.read_text()).get("signature")==sig:return cache
 except (OSError,ValueError,json.JSONDecodeError):pass
 render_track(track,src,cache,apply_inserts=False);stamp.write_text(json.dumps({"signature":sig}))
 return cache

def pitch_filter(sr:int,semitones:float)->str:
 s=max(-12,min(12,float(semitones)));r=2**(s/12);return f"asetrate={sr}*{r:.10f},aresample={sr},atempo={1/r:.10f}"

def effect_filter(req:SampleEffectRequest,sr:int)->str:
 p=req.params or {}
 if req.effect=="pitch":
  defaults={"up-semitone":1,"down-semitone":-1,"up-octave":12,"down-octave":-12};return pitch_filter(sr,float(p.get("semitones",defaults.get(req.preset,0)))+float(p.get("cents",0))/100)
 if req.effect=="normalizer":
  d={"streaming":(-14,-1),"broadcast":(-23,-2),"music":(-12,-1),"gentle":(-16,-1.5)}.get(req.preset,(-14,-1));return f"loudnorm=I={float(p.get('target_lufs',d[0])):.2f}:LRA=11:TP={float(p.get('true_peak_db',d[1])):.2f}"
 if req.effect=="maximizer":
  d={"gentle":(1.5,-1),"balanced":(3,-1),"loud":(6,-.8),"live":(2,-1.5)}.get(req.preset,(3,-1));drive=max(0,min(12,float(p.get("drive_db",d[0]))));ceil=max(-6,min(-.1,float(p.get("ceiling_db",d[1]))));return f"volume={drive:.2f}dB,alimiter=limit={10**(ceil/20):.8f}:attack=5:release=70:level=disabled"
 if req.effect=="eq32":
  gains=p.get("gains",EQ_PRESETS.get(req.preset,EQ_PRESETS["flat"]));
  if isinstance(gains,str):gains=[float(x) for x in gains.split(',')]
  gains=gains if isinstance(gains,list) and len(gains)==32 else EQ_PRESETS.get(req.preset,EQ_PRESETS["flat"])
  parts=[f"equalizer=f={f}:t=q:w=1:g={max(-18,min(18,float(g))):.2f}" for f,g in zip(EQ_BANDS,gains) if abs(float(g))>=.05];return ','.join(parts) or 'anull'
 return 'anull'

def autotune_regions(src:Path,start:float,end:float,params:dict)->list[tuple[float,float,float]]:
 dur=max(.001,end-start);rate=8000
 p=subprocess.run(["ffmpeg","-v","error","-ss",f"{start:.6f}","-to",f"{end:.6f}","-i",str(src),"-ac","1","-ar",str(rate),"-f","f32le","pipe:1"],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if p.returncode or not p.stdout:return [(0,dur,0)]
 data=np.frombuffer(p.stdout,dtype=np.float32);frame=640;hop=640
 roots={"C":0,"C#":1,"DB":1,"D":2,"D#":3,"EB":3,"E":4,"F":5,"F#":6,"GB":6,"G":7,"G#":8,"AB":8,"A":9,"A#":10,"BB":10,"B":11};root=roots.get(str(params.get('key','C')).upper(),0);minor=str(params.get('scale','major')).lower()=='minor';allowed={(root+x)%12 for x in ([0,2,3,5,7,8,10] if minor else [0,2,4,5,7,9,11])};strength=max(0,min(1,float(params.get('strength',.75))))
 raw=[]
 for pos in range(0,max(1,len(data)-frame+1),hop):
  x=data[pos:pos+frame];corr=0.0
  if len(x)>320 and float(np.sqrt(np.mean(x*x)))>.006:
   x=(x-float(np.mean(x)))*np.hanning(len(x));n=1<<((len(x)*2-1).bit_length());sp=np.fft.rfft(x,n);ac=np.fft.irfft(sp*np.conj(sp),n)[:len(x)];lo,hi=8,min(len(ac)-1,123)
   if hi>lo:
    lag=lo+int(np.argmax(ac[lo:hi+1]))
    if ac[lag]>max(1e-9,ac[0])*.18:
     midi=69+12*np.log2((rate/lag)/440);cand=[m for m in range(int(midi)-7,int(midi)+8) if m%12 in allowed]
     if cand:corr=max(-2,min(2,(min(cand,key=lambda m:abs(m-midi))-midi)*strength))
  raw.append([pos/rate,min(dur,(pos+hop)/rate),round(corr*20)/20])
 if not raw:return[(0,dur,0)]
 out=[]
 for a,b,c in raw:
  if out and abs(out[-1][2]-c)<=.1:out[-1][1]=b;out[-1][2]=(out[-1][2]+c)/2
  else:out.append([a,b,c])
 out[-1][1]=dur
 if len(out)>256:
  step=int(np.ceil(len(out)/256));out=[[g[0][0],g[-1][1],float(np.median([x[2] for x in g]))] for i in range(0,len(out),step) if (g:=out[i:i+step])]
 return [tuple(x) for x in out]

def effect_graph(src:Path,req:SampleEffectRequest,sr:int,dur:float,preview:bool)->str:
 total=max(1,round(dur*sr));a=min(max(0,req.start_sample),total);b=min(max(a+1,req.end_sample or total),total);start=a/sr;end=b/sr;parts=[];labels=[]
 def add(x,y,f='anull'):
  if y-x<=1e-5:return
  n=len(labels);parts.append(f"[0:a]atrim=start={x:.9f}:end={y:.9f},asetpts=PTS-STARTPTS,{f}[p{n}]");labels.append(f"[p{n}]")
 if not preview:add(0,start)
 if req.effect=='autotune':
  for x,y,c in autotune_regions(src,start,end,req.params or {}):add(start+x,start+y,pitch_filter(sr,c) if abs(c)>=.01 else 'anull')
 else:add(start,end,effect_filter(req,sr))
 if not preview:add(end,dur)
 return ';'.join(parts)+';'+''.join(labels)+f"concat=n={len(labels)}:v=0:a=1[out]"

def commit(project:Project,track:Track,tmp:Path)->Track:
 duration=media_duration_ms(tmp);name=f"sampleedit-{uuid.uuid4().hex[:12]}.wav";dst=storage.audio_path(project.id,name);shutil.move(str(tmp),dst);offset=min((c.timeline_start_ms for c in track.clips),default=0);track.filename=name;track.source_clip_id=None;track.duration_ms=duration;track.clips=[Clip(id=uuid.uuid4().hex[:10],source_start_ms=0,source_end_ms=duration,timeline_start_ms=offset)];track.waveform_peaks=waveform_peaks(dst,4096);track.waveform_revision="";storage.save_project(project);return track

def edit(project:Project,track:Track,req:SampleEditRequest)->dict:
 src=rendered_source(project.id,track);sr=sample_rate(src);dur=media_duration_ms(src)/1000;total=round(dur*sr);a=min(req.start_sample,total);b=min(max(a,req.end_sample),total);cursor=min(req.cursor_sample,total);clip=storage.pdir(project.id)/f".sample-clipboard-{track.id}.wav"
 if req.action in {'copy','cut'}:
  if b<=a:raise ValueError('seleziona prima un intervallo')
  run(["ffmpeg","-y","-v","error","-i",str(src),"-ss",f"{a/sr:.9f}","-to",f"{b/sr:.9f}","-c:a","pcm_s24le",str(clip)])
  if req.action=='copy':return {'clipboard_samples':b-a}
 if req.action in {'cut','delete'}:
  if b<=a:raise ValueError('seleziona prima un intervallo')
  pieces=[];labels=[]
  if a>0:pieces.append(f"[0:a]atrim=start=0:end={a/sr:.9f},asetpts=PTS-STARTPTS[p0]");labels.append('[p0]')
  if b<total:pieces.append(f"[0:a]atrim=start={b/sr:.9f}:end={dur:.9f},asetpts=PTS-STARTPTS[p1]");labels.append('[p1]')
  if not labels:raise ValueError("non è possibile rimuovere l'intera traccia")
  graph=';'.join(pieces)+';'+''.join(labels)+f"concat=n={len(labels)}:v=0:a=1[out]";tmp=storage.pdir(project.id)/f".sample-edit-{uuid.uuid4().hex}.wav";run(["ffmpeg","-y","-v","error","-i",str(src),"-filter_complex",graph,"-map","[out]","-c:a","pcm_s24le",str(tmp)]);return {'track':commit(project,track,tmp)}
 if req.action=='paste':
  if not clip.exists():raise ValueError('clipboard audio vuota')
  t=cursor/sr;pieces=[];labels=[]
  if t>0:pieces.append(f"[0:a]atrim=start=0:end={t:.9f},asetpts=PTS-STARTPTS[p0]");labels.append('[p0]')
  pieces.append('[1:a]asetpts=PTS-STARTPTS[pc]');labels.append('[pc]')
  if t<dur:pieces.append(f"[0:a]atrim=start={t:.9f}:end={dur:.9f},asetpts=PTS-STARTPTS[p1]");labels.append('[p1]')
  graph=';'.join(pieces)+';'+''.join(labels)+f"concat=n={len(labels)}:v=0:a=1[out]";tmp=storage.pdir(project.id)/f".sample-edit-{uuid.uuid4().hex}.wav";run(["ffmpeg","-y","-v","error","-i",str(src),"-i",str(clip),"-filter_complex",graph,"-map","[out]","-c:a","pcm_s24le",str(tmp)]);return {'track':commit(project,track,tmp)}
 raise ValueError('operazione non valida')

def apply_effect(project:Project,track:Track,req:SampleEffectRequest,preview:bool)->Path:
 src=rendered_source(project.id,track);sr=sample_rate(src);dur=media_duration_ms(src)/1000;graph=effect_graph(src,req,sr,dur,preview);suffix='.mp3' if preview else '.wav';out=storage.pdir(project.id)/f".sample-fx-{uuid.uuid4().hex}{suffix}";cmd=["ffmpeg","-y","-v","error","-i",str(src),"-filter_complex",graph,"-map","[out]"]+(["-c:a","libmp3lame","-b:a","192k"] if preview else ["-c:a","pcm_s24le"])+[str(out)];run(cmd);return out
