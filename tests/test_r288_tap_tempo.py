from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tap_tempo_icon_and_debounced_metronome_regeneration():
    html = (ROOT / 'app/templates/index.html').read_text()
    js = (ROOT / 'app/static/app.js').read_text()
    assert 'onclick="tapProjectTempo()"' in html
    assert 'class="tap-tempo-icon"' in html
    assert 'function tapProjectTempo()' in js
    assert 'performance.now()' in js
    assert 'scheduleMetronomeTempoRegeneration();' in js
    assert "t.type==='click'&&!t.mute" in js
    assert 'metronomeTempoRegenerationTimer=setTimeout' in js


def test_metronome_track_name_has_no_bpm():
    main = (ROOT / 'app/main.py').read_text()
    assert 'f"Metronomo {project.bpm:g} BPM"' not in main
    assert 'else "Metronomo"' in main
