from pathlib import Path
import wave

from app.audio_engine import generate_chords_piano_wav, refresh_chords_piano_wav_region
from app.models import Chord, Clip, Project, Track

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")

def project():
    tr=Track(id="a",name="Audio",type="other",filename="a.wav",duration_ms=60000,clips=[Clip(id="c",source_start_ms=0,source_end_ms=60000,timeline_start_ms=0)])
    return Project(id="p",title="P",target="DAW",tracks=[tr],chords=[Chord(time_ms=0,chord="C"),Chord(time_ms=10000,chord="F"),Chord(time_ms=20000,chord="G"),Chord(time_ms=40000,chord="Am"),Chord(time_ms=50000,chord="C")])

def test_fast_region_refresh_patches_only_local_window(tmp_path):
    pr=project(); out=tmp_path/"chords.wav"; generate_chords_piano_wav(pr,out)
    before=out.read_bytes(); pr.chords[2].time_ms=23000
    start,end=refresh_chords_piano_wav_region(pr,out,20000,23000)
    after=out.read_bytes()
    assert start <= 10000
    assert 23000 < end <= 40000
    assert len(after)==len(before) and after != before
    with wave.open(str(out),"rb") as w:
        assert w.getnchannels()==2 and w.getframerate()==44100

def test_timeline_move_warns_and_refreshes_existing_chords_track():
    assert "function hasGeneratedChordsTrack()" in JS
    assert "Attendere: aggiornamento della traccia Chords in corso" in JS
    assert "async function refreshGeneratedChordsTrack(oldTimeMs,newTimeMs,reason='modifica')" in JS
    assert "refreshTrack?{oldTimeMs:oldTime,newTimeMs:newTime}:null" in JS
    assert "await enqueueChordsRefresh(" in JS
    assert '@app.post("/api/projects/{pid}/chords-track/refresh")' in MAIN
    assert 'mode = "fast"' in MAIN and 'mode = "full"' in MAIN
