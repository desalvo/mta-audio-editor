"""r23: VST3 SDK interface definitions must be linked when SDK is present."""
from pathlib import Path


def test_official_sdk_interface_id_sources_present_in_cmake():
    cmake = (Path(__file__).resolve().parents[1] / 'native/vst3_probe/CMakeLists.txt').read_text()
    assert 'pluginterfaces/base/coreiids.cpp' in cmake
    assert 'public.sdk/source/vst/vstinitiids.cpp' in cmake
    assert 'target_sources(mta_vst3_probe' in cmake
    assert 'MTA_HAS_VST3_SDK=1' in cmake
