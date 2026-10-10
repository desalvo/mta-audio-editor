## 0.3.0-r155 — bounded supervised VST3 IPC recovery (`native_host_ready=false`)

Added control-thread-only supervisor for persistent event-enabled VST3 IPC sessions. No automatic replay after partial DSP failure, bounded restarts, epoch tracking, dry fallback, strict PCM/event preflight and test coverage. This does not integrate with the production playback callback; plugin state after a crash is lost, and host activation remains disabled.

## r154 event-batch status

All event-bearing quanta are validated before starting bounded IPC batch execution. No atomic rollback of VST3 plugin state on runtime failure is possible. The API MUST NOT be invoked from realtime audio callbacks. Production playback integration and cross-platform realtime stress tests remain incomplete. `native_host_ready=false`.

# Native VST3 host activation gate (r67)

`native_host_ready=false` remains mandatory. The new real-SDK ADelay CI acceptance
checks real processing for irregular session boundaries at 44.1/48/96 kHz, mono
and stereo, a two-insert serial chain, and sample-equivalence to unsplit input.

Before enabling native hosting in playback, implement and verify ALL of:

- **Interactive IPC worker:** implemented experimentally as `--stream-pcm` over
  persistent stdin/stdout pipes with at most 512 frames per request, external
  watchdog and one plugin instance per process. Needs wider platform validation.
- **Audio callback isolation:** callback must never block on plugin, IPC, file I/O,
  allocation, launch, mutex, disk, logging or timeout handling; deterministic
  fallback/bypass if completed buffers are unavailable.
- **Queue and scheduling:** bounded nonblocking SPSC rings, backpressure, event
  sequencing, accurate timestamps, track/insert enable/mute semantics.
- **Host completeness:** bus negotiation, stereo/mono compatibility, parameter
  automation, MIDI, transport/tempo, plugin state persistence and restoration.
- **Latency/tails:** dynamic latency reporting, project-wide compensation, tails,
  buffer sizes and sample-rate changes without audio glitches.
- **Fault isolation:** crashes, stalls, malformed output, timeout, restart,
  hot-reload, project close and app shutdown; never lose original project state.
- **Real-world acceptance:** real licensed plugin matrix on Windows/macOS/Linux,
  AMD64 and ARM64 as applicable; sustained playback, CPU benchmarks and
  perceptual/capture tests, plus UI insert enable/disable and save/reopen.

MTASPCM1 file sessions are **NOT** interactive workers; `--stream-pcm` adds
an experimental interactive worker but is not realtime-ready.
Passing its tests, or compiling with the SDK, must not flip readiness.

## r127 experimental C ABI gate

`native/audio_core/vst3_runtime_api.h` provides an installable C/C++ API with
explicit control-thread and audio-thread affinity. The ABI v2 supports a single
fixed callback quantum. A mismatched frame count or channel count is rejected;
it must be renegotiated while playback is quiescent by constructing a NEW runtime.

Passing this gate does **not** establish real-time safety of an integrated DAW.
The production playback engine has not been connected to this interface;
plugin latency, MIDI automation, restart supervision and cross-platform
callback stress testing remain outstanding. `native_host_ready=false` is mandatory.
