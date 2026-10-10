#!/usr/bin/env python3
"""Real ADelay acceptance for interactive IPC worker, outside realtime audio threads."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import wave


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: test_vst3_adelay_stream.py <native-probe> <adelay.vst3>')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from native.vst3_probe.probe import resolve_module_binary
    from native.vst3_probe.offline_session import render_native_session
    from native.vst3_probe.stream_worker import NativeVST3Worker, render_stream_wav
    probe, plugin = sys.argv[1:]
    metadata = json.loads(subprocess.check_output([probe, str(resolve_module_binary(Path(plugin)))], text=True, timeout=25))
    cid = next(info['cid'] for info in metadata['classes']
               if info['name'] == 'ADelay' and info['category'] == 'Audio Module Class')
    for rate in (44100, 48000, 96000):
        for channels in (1, 2):
            frames = 120001 if rate == 96000 else 70001
            signal = [0.125 * math.sin(2 * math.pi * 440 * (i + ch * 3) / rate)
                      for i in range(frames) for ch in range(channels)]
            output = []
            with NativeVST3Worker((plugin, cid), probe, channels=channels, sample_rate=rate, timeout=25) as worker:
                for index in range(0, frames, 512):
                    output.extend(worker.process(signal[index * channels:(index + 512) * channels]))
            assert len(output) == len(signal)
            assert all(math.isfinite(sample) for sample in output)
            assert sum(x*x for x in output) > 0.01
            reference = render_native_session([signal], (plugin, cid), probe,
                                              channels=channels, sample_rate=rate, timeout=40)[0]
            assert max(abs(a - b) for a, b in zip(output, reference)) < 1e-5
            print(f'Persistent ADelay IPC {rate} Hz, {channels}ch, {frames} frames: OK')
    from native.vst3_probe.native_chain import NativeChainError
    # A plug-in crash must stay within its subprocess and permit a fresh session.
    with NativeVST3Worker((plugin, cid), probe, channels=1, sample_rate=48000, timeout=15) as worker:
        worker._proc.kill()
        worker._proc.wait(timeout=5)
        try:
            worker.process([0.0] * 512)
        except NativeChainError:
            pass
        else:
            raise AssertionError('Killed VST3 worker was not rejected')
    with NativeVST3Worker((plugin, cid), probe, channels=1, sample_rate=48000, timeout=15) as worker:
        assert len(worker.process([0.0] * 512)) == 512
    print('VST3 subprocess crash containment and fresh start: OK')
    with tempfile.TemporaryDirectory() as root:
        source, destination = Path(root) / 'in.wav', Path(root) / 'out.wav'
        with wave.open(str(source), 'wb') as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(48000)
            writer.writeframes((b'\0\0' * 2) * 70001)
        render_stream_wav(source, destination, [(plugin, cid)], probe, timeout=25)
        with wave.open(str(destination), 'rb') as reader:
            assert (reader.getnframes(), reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) == (70001, 2, 2, 48000)
        print('Persistent IPC WAV streaming: OK')


if __name__ == '__main__':
    main()
