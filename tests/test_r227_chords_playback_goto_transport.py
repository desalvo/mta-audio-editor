from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text()
CSS = (ROOT / 'app/static/app.css').read_text()
HTML = (ROOT / 'app/templates/index.html').read_text()
AUDIO = (ROOT / 'app/audio_engine.py').read_text()


def test_chords_refresh_invalidates_webaudio_cache_and_versions_key():
    assert 'invalidateTrackAudioCache(refreshedTrack.id)' in JS
    assert "revision=String(track?.waveform_revision||'0')" in JS
    assert '${revision}:${info.url}' in JS


def test_fast_refresh_patches_wav_in_place():
    assert 'out.open("r+b", buffering=0)' in AUDIO
    assert 'WAV data chunk not found' in AUDIO
    assert '.refresh.tmp' not in AUDIO[AUDIO.index('def refresh_chords_piano_wav_region'):AUDIO.index('def generate_silent_chords_wav')]


def test_chords_refresh_progress_is_compact_and_paints_before_api():
    assert "classList.add('chords-refresh-progress-modal')" in JS
    assert 'await new Promise(requestAnimationFrame)' in JS
    assert '.utility-modal.chords-refresh-progress-modal' in CSS


def test_context_menus_have_goto_for_timed_items():
    assert "[['goto','Go-To']" in JS
    assert "if(action==='goto'){const ev=lyricsChordsEditorArrays(kind)" in JS
    assert 'data-meta-action="goto">Go-To</button>' in JS
    assert "if(action==='goto'){goToTimestamp(item.time_ms);return}" in JS


def test_transport_clock_is_editable_and_seeks():
    assert 'id="transportTime"' in HTML
    assert 'onchange="setTransportTime(this.value)"' in HTML
    assert 'onkeydown="transportTimeKeydown(event)"' in HTML
    assert 'function setTransportTime(value)' in JS
    assert 'function goToTimestamp(ms)' in JS
    assert '.transport-time-input' in CSS
