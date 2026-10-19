"""Use seekable original media in the block graph; render only incompatible formats."""
from pathlib import Path
import soundfile as sf


def prepare(project,sources,scratch,progress=lambda *_:None):
    from .audio_engine import render_track,ensure_clips
    paths=[];raw=[]
    for index,(track,source) in enumerate(zip(project.tracks,sources,strict=True)):
        progress(index,len(project.tracks),track.name)
        if track.kind=='midi':paths.append(Path(source));continue
        ensure_clips(track)
        try:
            info=sf.info(str(source))
            compatible=info.samplerate==project.sample_rate and info.channels in (1,2)
        except (OSError,RuntimeError):compatible=False
        if compatible:
            paths.append(Path(source));raw.append(track.id)
        else:
            dry=track.model_copy(deep=True);dry.gain_db=0;dry.inserts=[]
            target=Path(scratch)/f'dry-{index}.wav'
            render_track(dry,Path(source),target,apply_inserts=False,sample_rate=project.sample_rate)
            paths.append(target)
    progress(len(project.tracks),len(project.tracks),'')
    return paths,raw
