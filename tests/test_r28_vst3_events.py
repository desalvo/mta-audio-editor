"""r28 VST3 diagnostic feature guards."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def test_event_queues_are_preallocated_and_reused():
    source = (ROOT / "native/vst3_probe/main.cpp").read_text()
    assert "Steinberg::Vst::EventList events(16)" in source
    assert "Steinberg::Vst::ParameterChanges parameterChanges(1)" in source
    assert "events.clear();" in source
    assert "data.inputParameterChanges = &parameterChanges" in source
    assert "kNoteOnEvent" in source and "kNoteOffEvent" in source
def test_sdk_queues_are_linked_only_with_sdk():
    text = (ROOT / "native/vst3_probe/CMakeLists.txt").read_text()
    assert "hosting/eventlist.cpp" in text and "hosting/parameterchanges.cpp" in text
def test_realtime_switch_remains_disabled():
    text = (ROOT / "native/vst3_probe/probe.py").read_text()
    assert "native_host_ready" in text
