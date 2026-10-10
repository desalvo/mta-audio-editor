"""r22: reject SDK archives missing Steinberg Git submodules."""
from pathlib import Path
import subprocess


def test_sdk_cmake_rejects_incomplete_checkout(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sdk = tmp_path / "sdk"
    sdk.mkdir()
    (sdk / "LICENSE.txt").write_text("MIT\n", encoding="utf-8")
    result = subprocess.run(
        ["cmake", "-S", str(root / "native/vst3_probe"),
         "-B", str(tmp_path / "build"), f"-DMTA_VST3_SDK_ROOT={sdk}"],
        capture_output=True, text=True, check=False, timeout=40,
    )
    assert result.returncode != 0
    assert "Incomplete Steinberg VST3 SDK" in (result.stdout + result.stderr)
    assert "git clone --recursive" in (result.stdout + result.stderr)


def test_sdk_detection_lists_core_headers():
    source = (Path(__file__).resolve().parents[1] / "native/vst3_probe/CMakeLists.txt").read_text()
    assert "pluginterfaces/vst/ivstaudioprocessor.h" in source
    assert "public.sdk/source/vst/vstcomponent.h" in source
    assert "MTA_HAS_VST3_SDK=1" in source
