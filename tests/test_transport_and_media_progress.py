from pathlib import Path
import shutil
import subprocess

import pytest

from app.audio_engine import estimate_bpm


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_bpm_estimator_on_click_track(tmp_path):
    wav = tmp_path / "click.wav"
    # 120 BPM click track: one 30 ms tone every 0.5 s.
    subprocess.run(
        [
            "ffmpeg","-y","-v","error","-f","lavfi",
            "-i","aevalsrc=if(lt(mod(t\\,0.5)\\,0.03)\\,0.8*sin(2*PI*1000*t)\\,0):s=4000:d=20",
            "-ac","1",str(wav)
        ], check=True
    )
    values=[]
    bpm=estimate_bpm(wav, lambda pct,msg: values.append(pct))
    assert 115 <= bpm <= 125
    assert values and max(values) >= 90


def test_ui_has_working_transport_progress_and_persistent_tracks():
    root=Path(__file__).resolve().parents[1]
    js=(root/"app/static/app.js").read_text()
    html=(root/"app/templates/index.html").read_text()
    assert 'onclick="stopPlayback()"' in html
    assert "function setPlayCursor(" in js
    assert "playCursorMs" in js
    assert "function showMediaProgress(" in js
    assert "track-import-jobs" in js
    assert "track-export-jobs" in js
    assert "function openProjectSelector()" in js
    assert "projectPickerRows" in js
    assert "audibly-muted" in js
    # Mute/Solo must not filter the visual track arrays out.
    # Playback may filter inaudible tracks, but visual rendering must always map
    # the complete project track list.
    assert "current.tracks.map((t,i)=>trackHead" in js
    assert "current.tracks.map((t,i)=>lane" in js
    assert "updateMuteSoloVisuals" in js
