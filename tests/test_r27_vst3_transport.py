"""r27 deterministic musical transport and revision contract."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_transport_context_is_sample_accurate():
    source = (ROOT / "native/vst3_probe/main.cpp").read_text()
    assert "data.processContext = &transport" in source
    assert "transport.projectTimeSamples = projectSample" in source
    assert "transport.projectTimeMusic = double(projectSample) * 120.0 / (60.0 * pcmSampleRate)" in source
    assert "offlineTransportContinuous" in source
    assert "offline_last_project_sample" in source

def test_transport_results_are_bounded():
    adapter = (ROOT / "native/vst3_probe/probe.py").read_text()
    assert "offline_transport_continuous" in adapter
    assert "65024 else None" in adapter

def test_mobile_build_versions_follow_revision():
    rev = int((ROOT / "REVISION").read_text())
    gradle = (ROOT / "mobile/android/app/build.gradle.kts").read_text()
    plist = (ROOT / "mobile/ios/MTAEditorMobile/Info.plist").read_text()
    assert f"versionCode = {30000 + rev}" in gradle
    assert f"MTA_REVISION\", \"\\\"{rev}\\\"\"" in gradle
    assert f"<string>{rev}</string>" in plist
