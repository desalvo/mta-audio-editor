"""Cancellable source-region preparation with the same non-destructive clips."""
import subprocess
import tempfile
import time


def prepare(track, source, start, end, target, cancelled):
    if track.kind != 'audio' or not 0 <= start < end <= 86400000 or end-start > 600000:
        raise ValueError('Choose an audio region of at most 10 minutes')
    from .audio_engine import ensure_clips
    ensure_clips(track)
    filters=[];labels=[]
    for clip in track.clips:
        left=clip.timeline_start_ms+track.delay_ms
        a=max(start,left);b=min(end,left+clip.duration_ms)
        if b<=a:continue
        if len(labels)>=256:raise ValueError('Source region exceeds 256 clip intersections')
        source_a=clip.source_start_ms+a-left;source_b=source_a+b-a
        label='part'+str(len(labels));labels.append('['+label+']')
        filters.append(f'[0:a]atrim=start={source_a/1000:.6f}:end={source_b/1000:.6f},asetpts=PTS-STARTPTS,adelay={a-start}:all=1[{label}]')
    if not labels:return False
    filters.append(''.join(labels)+f'amix=inputs={len(labels)}:normalize=0,volume={track.gain_db:.4f}dB,apad[out]')
    command=['ffmpeg','-nostdin','-y','-v','error','-i',str(source),'-filter_complex',';'.join(filters),
             '-map','[out]','-t',f'{(end-start)/1000:.6f}','-ac','2','-ar','44100','-c:a','pcm_s16le',str(target)]
    with tempfile.TemporaryFile() as errors:
        proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=errors)
        deadline=time.monotonic()+60
        try:
            while proc.poll() is None:
                if cancelled():raise RuntimeError('Job cancelled during source preparation')
                if time.monotonic()>deadline:raise RuntimeError('Source preparation exceeded 60 seconds')
                time.sleep(.05)
            if proc.returncode:raise RuntimeError('Audio source preparation failed; inspect the source media')
        finally:
            if proc.poll() is None:proc.kill()
            proc.wait()
    return True
