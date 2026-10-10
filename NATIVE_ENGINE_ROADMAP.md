## 0.3.0-r120 — cumulative r101–r120 native readiness gate

This release includes every uncommitted change from r65 through r100. Twenty distinct control-plane validations (quantum, channel shape, sample rate, queue sizing, lookahead, worker scheduling, quiescence, IPC handshake/version, plugin lifecycle, processing, latency, crash recovery, MIDI, automation, platforms and realtime stress) are explicitly checked in native C++ and exercised by parameterized compiled tests. Existing worker runtime now refuses an unsafe restart that could replay stale queue data. **These are acceptance checks, not proof they are all satisfied by MTA's production engine.** The actual realtime host remains disabled: `native_host_ready=false`. End-to-end IPC binding to the native callback, measured latency compensation and multi-platform tests remain open. No claim of production readiness.

## 0.3.0-r100 — native worker runtime (r88–r100)

Cumulative changes since r65 including r87. Thirteen native worker engineering increments: bounded worker configuration, lifecycle states, processor ownership, control-thread start/join, callback/IPC separation, fault latch, scheduling fairness, worker-thread backoff, fault diagnostics, immutable quantum, watchdog integration point, stop statistics and disabled readiness gate. This is an experimental control-plane worker runtime, NOT an end-to-end VST3 realtime host. `native_host_ready` remains `false`.

## r76 experimental native VST3 playout

Implemented a bounded SPSC native playout bridge header and compiled regression tests. The callback-facing API does not perform worker IO. Still require integrating native worker processing with application engine, handling adaptive block sizes and plugin latency, automation/MIDI, fault-restart/bypass and cross-platform real-time stress tests before readiness.

### r70 — Experimental interactive VST3 offline worker

`native/vst3_probe/stream_worker.py` implements `NativeVST3Worker` (persistent IPC
per plugin) and `render_stream_wav()` (bounded-memory PCM16/24/32 WAV export).
The C++ probe's `--stream-pcm <CID> <channels> <rate>` protocol exchanges
little-endian uint32 frame counts plus interleaved Float32 PCM on stdin/stdout,
1–512 frames at a time; zero frames signals graceful shutdown. This is not a
realtime callback-safe integration. A Python watchdog kills stalled workers,
rejects malformed/nonfinite replies, and leaves preexisting WAV outputs intact
on export errors. Supported sample rates: 44100, 48000, 96000; mono/stereo.
The real ADelay streaming and session acceptance tests run in Linux VST3 SDK CI.
Read `native/vst3_probe/READINESS_GATES.md` before enabling the native host.
**`native_host_ready=false` remains intentional.**

## r33 variable-length stereo offline rendering
The opt-in isolated native adapter accepts 1–1,048,576 mono or stereo frames, 48 kHz interleaved float32, retaining VST3 processor state across all 512-sample blocks and processing the final partial block. Each insert executes in a separate subprocess. This is not a realtime playback interface; MIDI and automation routing, plugin latency alignment and extended format negotiation are not yet integrated with this chain.

# Native host status / Stato host nativo

The r300 audio_core is a separate tested C++20 PCM meter, **not a VST3 host**.
The existing Pedalboard VST3 path still renders offline. No original plug-in GUI, realtime MIDI, latency compensation or VST3 Master support is claimed.

Linux CI targets Debian/Ubuntu `.deb` and RedHat/Fedora `.rpm`, x86_64 and arm64, using native runners. Dependencies and package installation must be validated on supported target distros; CI packaging alone is not certification.

For a full host: isolate untrusted plug-in processes; design the audio callback scheduler and IPC; implement Steinberg VST3 processor/controller/state/event interfaces; bridge original native editor windows; add PDC, parameter automation and track/Master integration; prove crash recovery; run native integration tests with real VST3s.

No bulk Python-to-C++ rewrite has been performed: prioritize profiling before moving hot paths, and keep FastAPI/web/mobile behavior stable.

---

Il modulo C++20 implementa solamente il calcolo peak/RMS PCM con fallback Python. Non è ancora un host VST3 nativo. Il rendering VST3 resta su Pedalboard e l'audio in tempo reale richiede una fase successiva. I pacchetti Linux sono configurati in CI ma da convalidare su distribuzioni reali.

### r87: Native control-plane contracts (not yet realtime-ready)

The native worker contracts now cover negotiated block shape, session epochs,
frame deadlines, latency budgets, dry fallback ramps, bounded MIDI/automation
packets, worker fault gating and output validation. These have C++20 tests,
but must still be wired to native engine transport and a realtime-safe
VST3 worker scheduler, including real plugin automation/state validation and
Windows/macOS/Linux stress and failure recovery. Keep `native_host_ready=false`.
