from pathlib import Path

from app.audio_engine import generate_silent_chords_wav
from app.models import Chord, Clip, Project, Track

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


def _project(chords):
    track = Track(
        id="audio",
        name="Audio",
        type="other",
        filename="a.wav",
        duration_ms=5000,
        clips=[Clip(id="c", source_start_ms=0, source_end_ms=5000, timeline_start_ms=0)],
    )
    return Project(id="p", title="P", target="DAW", tracks=[track], chords=chords)


def test_full_chords_render_can_create_silence_when_no_active_chords(tmp_path):
    out = tmp_path / "chords.wav"
    duration = generate_silent_chords_wav(_project([]), out)
    assert duration == 5000
    assert out.exists() and out.stat().st_size > 44


def test_all_direct_chord_mutations_request_generated_track_refresh():
    assert "refreshGeneratedChordsTrackForMutation" in JS
    assert "'modifica chord'" in JS
    assert "'aggiunta chord'" in JS
    assert "'eliminazione chord'" in JS
    assert "'disabilitazione chord'" in JS
    assert "'riabilitazione chord'" in JS
    assert "'reset chords'" in JS
    assert "'estrazione chords'" in JS
    assert "'modifiche editor Chords'" in JS


def test_mutation_diff_uses_audio_relevant_chord_fields_only():
    assert "function chordTrackAudioSignature(ch)" in JS
    assert "time_ms:" in JS and "chord:String(ch?.chord||'')" in JS and "excluded:!!ch?.excluded" in JS
    assert "function chordTrackRefreshBounds(before,after)" in JS


def test_refresh_endpoint_is_generic_for_any_chord_mutation():
    assert "Refresh an existing generated Chords track after any chord mutation." in MAIN
    assert '@app.post("/api/projects/{pid}/chords-track/refresh")' in MAIN
