from pathlib import Path
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

WRITE={"X-MTA-Request":"1"}


def test_sample_editor_ui_is_available_from_timeline_and_context_menu():
    root=Path(__file__).resolve().parents[1]
    js=(root/"app/static/app.js").read_text(encoding="utf-8")
    css=(root/"app/static/app.css").read_text(encoding="utf-8")
    for token in ("Editor waveform / campioni","seEdit('cut')","seEdit('copy')","seEdit('paste')","seEdit('delete')","Pitch correction","Auto-Tune","Normalizer","Maximizer","EQ grafico 32 bande","function seEnvelope","spp>=e.block*.75"):
        assert token in js
    assert "ondblclick=\"event.stopPropagation();openSampleEditor" in js
    assert ".sample-editor-wave" in css and ".sample-eq32" in css


def test_sample_editor_requests_and_filter_presets():
    import app.sample_editor as engine
    from app.models import SampleEditRequest, SampleEffectRequest
    assert SampleEditRequest(action="cut",start_sample=10,end_sample=20,cursor_sample=10).end_sample==20
    pitch=engine.effect_filter(SampleEffectRequest(effect="pitch",start_sample=0,end_sample=100,params={"semitones":1,"cents":25}),44100)
    assert "asetrate=44100" in pitch and "atempo=" in pitch
    assert "loudnorm=I=-14.00" in engine.effect_filter(SampleEffectRequest(effect="normalizer",start_sample=0,end_sample=100,preset="streaming"),44100)
    assert "alimiter=" in engine.effect_filter(SampleEffectRequest(effect="maximizer",start_sample=0,end_sample=100,preset="balanced"),44100)
    assert "equalizer=f=" in engine.effect_filter(SampleEffectRequest(effect="eq32",start_sample=0,end_sample=100,preset="vocals"),44100)


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,reason="FFmpeg required")
def test_sample_editor_endpoints_copy_delete_paste_preview_apply(tmp_path,monkeypatch):
    import app.main as main
    import app.storage as storage
    from app.models import Clip,Track
    monkeypatch.setattr(storage,"ROOT",tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH","true")
    project=storage.create_project("Sample editor")
    source=storage.audio_path(project.id,"tone.wav")
    subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","sine=frequency=440:duration=1.0","-ar","44100","-ac","1",str(source)],check=True)
    project.tracks=[Track(id="t1",name="Tone",filename="tone.wav",duration_ms=1000,channels=1,channel_layout="mono",clips=[Clip(id="c1",source_start_ms=0,source_end_ms=1000,timeline_start_ms=0)])]
    storage.save_project(project);client=TestClient(main.app,headers=WRITE)
    info=client.get(f"/api/projects/{project.id}/tracks/t1/sample-editor");assert info.status_code==200,info.text;assert info.json()["sample_rate"]==44100
    copy=client.post(f"/api/projects/{project.id}/tracks/t1/sample-editor/edit",json={"action":"copy","start_sample":1000,"end_sample":5000,"cursor_sample":1000});assert copy.status_code==200,copy.text
    delete=client.post(f"/api/projects/{project.id}/tracks/t1/sample-editor/edit",json={"action":"delete","start_sample":1000,"end_sample":5000,"cursor_sample":1000});assert delete.status_code==200,delete.text
    deleted_ms=delete.json()["track"]["duration_ms"]
    paste=client.post(f"/api/projects/{project.id}/tracks/t1/sample-editor/edit",json={"action":"paste","start_sample":0,"end_sample":0,"cursor_sample":2000});assert paste.status_code==200,paste.text;assert paste.json()["track"]["duration_ms"]>deleted_ms
    preview=client.post(f"/api/projects/{project.id}/tracks/t1/sample-editor/effect-preview",json={"effect":"normalizer","start_sample":0,"end_sample":5000,"preset":"streaming","params":{}});assert preview.status_code==200,preview.text;assert preview.headers["content-type"].startswith("audio/mpeg")
    apply=client.post(f"/api/projects/{project.id}/tracks/t1/sample-editor/effect-apply",json={"effect":"pitch","start_sample":0,"end_sample":5000,"preset":"subtle","params":{"semitones":0.1,"cents":5}});assert apply.status_code==200,apply.text;assert apply.json()["track"]["waveform_peaks"]


@pytest.mark.skipif(shutil.which("ffmpeg") is None,reason="FFmpeg required")
def test_autotune_regions_and_graph(tmp_path):
    import app.sample_editor as engine
    from app.models import SampleEffectRequest
    src=tmp_path/"voice.wav";subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","sine=frequency=445:duration=0.8","-ar","44100","-ac","1",str(src)],check=True)
    regions=engine.autotune_regions(src,0,0.8,{"key":"A","scale":"major","strength":1});assert regions and regions[-1][1]==pytest.approx(.8,abs=.01);assert all(-2<=r[2]<=2 for r in regions)
    req=SampleEffectRequest(effect="autotune",start_sample=100,end_sample=20000,preset="hard",params={"key":"A","scale":"major","strength":1})
    graph=engine.effect_graph(src,req,44100,.8,False);assert "concat=n=" in graph and "atrim=start=" in graph


def test_sample_editor_fallbacks(monkeypatch,tmp_path):
    import app.sample_editor as engine
    from app.models import SampleEffectRequest
    class P:returncode=0;stdout="not-a-rate";stderr=""
    monkeypatch.setattr(engine.subprocess,"run",lambda *a,**k:P())
    assert engine.sample_rate(tmp_path/"x.wav")==44100
    assert engine.effect_filter(SampleEffectRequest(effect="eq32",start_sample=0,end_sample=1,params={"gains":"1,2"}),44100)=="anull"
