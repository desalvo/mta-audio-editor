from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_tls_uses_os_trust_store_without_disabling_verification():
    text = (ROOT / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    assert "truststore.inject_into_ssl()" in text
    assert "CERT_NONE" not in text
    assert "check_hostname = False" not in text
    req = (ROOT / "requirements-native.txt").read_text(encoding="utf-8")
    assert "truststore==" in req
    assert "certifi==" in req


def test_native_bundle_collects_tls_and_ai_packages():
    spec = (ROOT / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    for package in ("whisper", "madmom_infer", "truststore", "certifi"):
        assert f'"{package}"' in spec


def test_chords_dependency_contains_chord_capable_madmom_infer_commit():
    req = (ROOT / "requirements-chords.txt").read_text(encoding="utf-8")
    assert "bffead9be61857fd44b2e0d3a2510d9d94c8f2d2" in req
    assert "madmom-infer==0.2.0" not in req


def test_native_model_chooser_download_buttons_are_explicitly_readable():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert js.count("model-download-btn") >= 2
    assert "-webkit-text-fill-color:#eff8ff" in css
    assert ".form-actions button" in css


def test_model_download_endpoints_translate_unexpected_failures():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert 'Download modello lyrics fallito:' in main
    assert 'Download modello chords fallito:' in main
    assert 'HTTPException(502' in main


def test_chord_direct_dependency_is_audited_as_installed_environment():
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "/tmp/mta-chords-audit/bin/python -m pip install -r requirements-chords.txt" in workflow
    assert "/tmp/mta-chords-audit/bin/pip-audit --strict" in workflow
    assert "pip-audit -r requirements-chords.txt --strict" not in workflow
