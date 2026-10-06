from pathlib import Path

JS = Path("app/static/app.js").read_text(encoding="utf-8")


def test_webaudio_transport_uses_shared_audio_context_clock():
    assert "startWebAudioProjectPlayback" in JS
    assert "audioCtx.createBufferSource()" in JS
    assert "const startAt=audioCtx.currentTime+.035" in JS
    assert "waStartCtxTime=startAt" in JS
    assert "waProjectCursorMs" in JS


def test_webaudio_live_controls_and_real_analysers():
    assert "waTrackGain(track)" in JS
    assert "item.gainNode?.gain.setTargetAtTime" in JS
    assert "item.panner.pan.setValueAtTime" in JS
    assert "waMasterBus.connect(masterPlaybackGainNode)" in JS
    assert "masterMeterAnalysers=[l,r]" in JS
    assert "getFloatTimeDomainData" in JS


def test_web_audio_replaces_track_fx_without_transport_restart():
    block = JS[JS.rfind("async function refreshDynamicTrackPlayback"):]
    assert "waDecodeTrack(track,true,true)" in block
    assert "linearRampToValueAtTime" in block
    assert "trackPlaybacks.splice(idx,1,replacement)" in block


def test_editor_auto_syllabifies_without_changing_saved_text_model():
    assert "function editorAutoSyllableParts" in JS
    assert "function editorWordUnits(word)" in JS
    assert "auto:true" in JS
    assert "word.syllables=editorWordUnits(word).map" in JS


def test_revision_metadata_consistency():
    rev = int(Path("REVISION").read_text().strip())
    assert f"versionCode = {20000 + rev}" in Path("mobile/android/app/build.gradle.kts").read_text()
    assert f"<string>{20000 + rev}</string>" in Path("mobile/ios/MTAEditorMobile/Info.plist").read_text()
