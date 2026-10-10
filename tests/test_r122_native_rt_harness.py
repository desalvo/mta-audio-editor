"""r122: native SPSC -> Python worker thread -> isolated VST3 IPC smoke checks."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_rt_harness_import_and_validation(tmp_path):
    from native.vst3_probe.native_rt_harness import NativeRTTestHarness
    with pytest.raises(ValueError):
        NativeRTTestHarness("missing.so", ("missing.vst3", "0" * 32), "missing", frames=0)
    with pytest.raises(ValueError):
        NativeRTTestHarness("missing.so", ("missing.vst3", "0" * 32), "missing", channels=3)
    with pytest.raises(ValueError):
        NativeRTTestHarness("missing.so", ("missing.vst3", "0" * 32), "missing", lookahead=0)


def test_native_rt_harness_abi_stays_disabled():
    source = (ROOT / "native/vst3_probe/native_rt_harness.py").read_text()
    assert "self._worker.process(samples)" in source
    assert "self.lib.mta_vst3_rt_stop(self._handle)" in source
    assert "Test driver only" in source
    assert "native_host_ready" not in source
