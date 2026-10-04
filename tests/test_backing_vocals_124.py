from pathlib import Path
from app import main

def test_ai_catalog_default_and_choices():
    cat=main._lead_backing_catalog()
    assert cat["default_model"] == "uvr_mdxnet_kara_2"
    ids={m["id"] for m in cat["models"]}
    assert {"uvr_mdxnet_kara_2","mel_roformer_karaoke_aufr33","mel_roformer_karaoke_gabox_v2"} <= ids
    assert cat["on_demand"] is True

def test_native_catalog_marks_local(monkeypatch):
    monkeypatch.setattr(main,"NATIVE_SINGLE_USER",True)
    assert main._lead_backing_catalog()["storage"] == "local"

def test_ui_sends_selected_backing_model():
    js=(Path(main.BASE)/"static"/"app.js").read_text()
    assert "stemBackingVocalModel" in js
    assert "backing_vocal_model=${encodeURIComponent(backingVocalModel)}" in js
    assert "downloadSelectedBackingModel" in js

def test_requirements_include_audio_separator():
    req=(main.BASE.parent/"requirements-stems.txt").read_text()
    assert "audio-separator[cpu]==0.47.0" in req
