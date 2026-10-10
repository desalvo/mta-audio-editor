"""r17: prevent accidental removal of VST3 hostile-metadata bounds."""
from pathlib import Path


def test_cpp_class_strings_are_bounded():
    source = (Path(__file__).resolve().parents[1] / 'native/vst3_probe/main.cpp').read_text()
    assert 'bounded_class_string(info.name)' in source
    assert 'bounded_class_string(info.category)' in source
    assert 'info.channelCount < 0 || info.channelCount > 1024' in source
    assert 'native_host_ready' in source and 'false' in source
