from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWIFT = (ROOT / "mobile/ios/MTAEditorMobile/LocalStemEngine.swift").read_text(encoding="utf-8")
CONTROLLER = (ROOT / "mobile/ios/MTAEditorMobile/MobileWebViewController.swift").read_text(encoding="utf-8")
PROJECT = (ROOT / "mobile/ios/MTAEditorMobile.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")


def test_coreml_local_engine_is_part_of_ios_target():
    assert "LocalStemEngine.swift in Sources" in PROJECT
    assert "import CoreML" in SWIFT
    assert "configuration.computeUnits = .all" in SWIFT


def test_local_engine_supports_requested_counts_and_chunking():
    assert "supportedStemCounts = [2, 4, 6, 8]" in SWIFT
    assert "chunkFrames" in SWIFT
    assert "overlap-add" in SWIFT
    assert "12 minutes" in SWIFT


def test_mobile_bridge_exposes_local_stem_runtime():
    assert "localStemCapabilities" in CONTROLLER
    assert "startLocalStemSeparation" in CONTROLLER
    assert "cancelLocalStemSeparation" in CONTROLLER
    assert "mtaLocalStemProgress" in CONTROLLER


def test_web_workflow_exposes_auto_local_server():
    assert "Auto · locale se possibile" in JS
    assert "Locale · Core ML" in JS
    assert "Server cloud" in JS
    assert "startIosLocalStemWorkflow" in JS


def test_backend_provisions_authenticated_coreml_models():
    assert "MTA_DEMUCS_COREML_MODEL_DIR" in MAIN
    assert '/api/mobile/demucs-coreml/models/{stem_count}' in MAIN
    assert "_actor(request)" in MAIN


def test_export_utility_documents_contract():
    script = (ROOT / "scripts/export_demucs_coreml.py").read_text(encoding="utf-8")
    for marker in ("stem_count", "stem_labels", "chunk_frames", 'name="audio"', 'name="stems"'):
        assert marker in script


def test_coreml_model_repository_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")
    from fastapi.testclient import TestClient
    import app.main as main

    (tmp_path / "demucs-4.mlmodel").write_bytes(b"coreml-four")
    (tmp_path / "demucs-6.mlmodel").write_bytes(b"coreml-six")
    monkeypatch.setattr(main, "COREML_DEMUCS_MODEL_DIR", tmp_path)
    client = TestClient(main.app)

    status = client.get("/api/mobile/demucs-coreml/status")
    assert status.status_code == 200
    assert status.json()["available_stem_counts"] == [4, 6]
    model = client.get("/api/mobile/demucs-coreml/models/4")
    assert model.status_code == 200
    assert model.content == b"coreml-four"
    assert client.get("/api/mobile/demucs-coreml/models/3").status_code == 404
    assert client.get("/api/mobile/demucs-coreml/models/8").status_code == 404

    monkeypatch.setattr(main, "COREML_DEMUCS_MODEL_DIR", None)
    assert client.get("/api/mobile/demucs-coreml/models/4").status_code == 404
