from pathlib import Path


def test_context_split_always_opens_parameter_wizard():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "closeTrackContextMenu();openTrackStemWorkflow('${id}')" in js
    assert "La separazione partirà solo dopo la conferma dei parametri" in js
    assert 'id="trackStemModel"' in js
    assert 'id="trackStemCount"' in js
    assert 'id="trackSplitBackingVocals"' in js
    assert "if(!model||!stemCount)return toast('Seleziona modello AI e numero di stem prima di procedere')" in js


def test_track_split_parameters_are_sent_and_used_by_worker():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    main = (root / "app/main.py").read_text(encoding="utf-8")
    assert "split_backing_vocals:String(splitBackingVocals)" in js
    assert "backing_vocal_model:backingVocalModel" in js
    assert "stem_count = int(job.get(\"stem_count\") or 0)" in main
    assert "stem_count=stem_count," in main
    assert '"split_backing_vocals": bool(split_backing_vocals)' in main


def test_dynamic_playback_does_not_seek_buffering_tracks_repeatedly():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "if(audio.readyState<3||audio.seeking){audio.playbackRate=1;item.needsRelock=true;continue}" in js
    assert "setInterval(()=>alignDynamicTracks(false),120)" in js
    assert "Math.max(.997,Math.min(1.003" in js
    assert "audio.buffered.end(i)-pos>=Math.min(.08" in js


def test_stop_invalidates_pending_playback_and_render_requests():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    start = js.index("function stopPlayback(){")
    block = js[start:start + 500]
    assert "++playbackToken;" in block
    assert "playbackBuffering=false;" in block
    assert "removeAttribute('src')" in js
    assert "if(token!==playbackToken)return null" in js
