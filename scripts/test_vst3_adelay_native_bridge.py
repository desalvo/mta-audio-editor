#!/usr/bin/env python3
"""Real-SDK acceptance of experimental C ABI -> VST3 subprocess bridge."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: test_vst3_adelay_native_bridge.py <probe> <adelay.vst3>")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from native.vst3_probe.native_rt_harness import NativeRTTestHarness
    from native.vst3_probe.probe import resolve_module_binary
    probe, plugin = sys.argv[1:]
    meta = json.loads(subprocess.check_output(
        [probe, str(resolve_module_binary(Path(plugin)))], text=True, timeout=25))
    cid = next(x["cid"] for x in meta["classes"]
               if x["name"] == "ADelay" and x["category"] == "Audio Module Class")
    with tempfile.TemporaryDirectory() as temp:
        library = Path(temp) / "libmta_rt.so"
        subprocess.run(["c++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                        "-fPIC", "-shared", "-I", str(root / "native/audio_core"),
                        str(root / "native/audio_core/vst3_runtime_api.cpp"),
                        "-o", str(library)], check=True, timeout=60)
        for channels in (1, 2):
            energy = 0.0
            with NativeRTTestHarness(str(library), (plugin, cid), probe,
                                     frames=512, channels=channels) as harness:
                for block in range(180):
                    pcm = [0.1 * math.sin(2 * math.pi * 440 * (block * 512 + i) / 48000)
                           for i in range(512) for _ in range(channels)]
                    result = harness.process(pcm)
                    assert len(result) == len(pcm)
                    assert all(math.isfinite(v) for v in result)
                    energy += sum(v * v for v in result)
                    time.sleep(0.003)
            assert energy > 0.001, "VST3 bridge did not produce delayed audio"
            print(f"Native C ABI to ADelay IPC {channels} channels: passed")


if __name__ == "__main__":
    main()
