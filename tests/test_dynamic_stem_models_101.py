import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_custom_registry_exposes_12_16_and_24_stem_models(monkeypatch):
    from app.plugins import DemucsStemSplitter
    monkeypatch.setenv("MTA_DEMUCS_MODEL_REGISTRY", json.dumps({"models":[
        {"id":"roformer-12","model":"custom_12","stem_count":12,"stem_labels":[f"s{i}" for i in range(12)]},
        {"id":"custom-16","model":"custom_16","stem_count":16,"stem_labels":[f"s{i}" for i in range(16)]},
        {"id":"future-24","model":"future_24","stem_count":24,"stem_labels":[f"s{i}" for i in range(24)]},
    ]}))
    status=DemucsStemSplitter.status()
    assert {12,16,24}.issubset(set(status["supported_stem_counts"]))
    assert status["model_driven"] is True
    assert status["max_supported_stem_count"] >= 24

def test_mobile_inventory_discovers_arbitrary_counts(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH","true")
    from fastapi.testclient import TestClient
    import app.main as main
    for n in (4,10,16,24):
        (tmp_path/f"demucs-{n}.mlmodel").write_bytes(f"m{n}".encode())
    monkeypatch.setattr(main,"COREML_DEMUCS_MODEL_DIR",tmp_path)
    data=TestClient(main.app).get("/api/mobile/demucs-coreml/status").json()
    assert data["available_stem_counts"] == [4,10,16,24]
    assert data["model_driven"] is True

def test_model_updater_allows_more_than_8_stems():
    text=(ROOT/"app/model_updater.py").read_text()
    assert 'count < 2 or count > 64' in text
    assert 'stem_labels' in text

def test_ios_engine_discovers_installed_models_dynamically():
    text=(ROOT/"mobile/ios/MTAEditorMobile/LocalStemEngine.swift").read_text()
    assert 'contentsOfDirectory' in text
    assert 'maximumStemCount = 64' in text
    assert 'supportedStemCounts = [2, 4, 6, 8]' not in text
