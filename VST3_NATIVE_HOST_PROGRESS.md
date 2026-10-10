## 0.3.0-r152 — safe event/audio dispatch

Reject exact-sequence event packets with mismatched audio frame counts and fail closed on bounded stale-event scan exhaustion. Preserve the r121–r151 cumulative work. `native_host_ready=false`; live SDK and playback integration still pending.

## r151 — Experimental PCM/event worker synchronization

Worker-side `Vst3EventAudioPump` pairs native PCM blocks and bounded MIDI/automation event packets using epoch, sequence and frame count. Empty event blocks remain playable, failed delivery fails closed, and non-finite processor output is rejected. This is a test-only bridge: no Steinberg SDK MIDI queue or production playback connection is claimed; `native_host_ready=false`.

## r141–r150 — Bounded worker event dispatch (experimental)

Added `native/audio_core/vst3_event_dispatch.hpp`: epoch/sequence gating, bounded MIDI and parameter dispatch, atomic prevalidation, preserved sample offsets, failure counters, lifecycle reset, and deterministic sequence consumption. The worker adapter is not yet wired to Steinberg SDK processing or production playback. `native_host_ready=false`.

## 0.3.0-r140 — five native functional cycles (r136–r140)

- r136: worker processor exceptions contained; no worker-thread termination from plugin adapter exceptions.
- r137: reject non-finite worker PCM before returning a processed block.
- r138: add allocation-free bounded SPSC transport for prepared MIDI and automation event packets.
- r139: detect and discard stale transport epochs; preserve future events with bounded scans.
- r140: stress test 20,000 event packets across producer and consumer threads and dry fallback.

**Experimental only:** events are NOT yet mapped to Steinberg SDK VST3 event/parameter queues; playback integration and multiplaform stress are pending; `native_host_ready=false`.

## 0.3.0-r129 — Native PCM latency alignment reference (experimental)

- Implement preallocated C++ frame-accurate PCM delay-line supporting mono/stereo, irregular block sizes, in-place processing and reset on seek.
- Add C++20 regression tests for delay alignment and invalid sample rejection.
- This is an isolated reference component: it is not yet wired into live playback and does not account for reported VST3 plugin latency dynamically.
- `native_host_ready=false` remains mandatory until end-to-end playback, MIDI/automation and all platform tests pass.

## 0.3.0-r128 — worker stability hardening (experimental)

- Clear worker output buffers before every processing call to avoid stale PCM leaking from incomplete writers.
- Add deterministic native stress tests for failure, restart isolation, underruns and repeated lifecycle.
- native_host_ready remains false; production host integration and platform validation are still required.


## 0.3.0-r127 — Native public C ABI and exact-quantum enforcement

- Added `native/audio_core/vst3_runtime_api.h`, a usable C/C++ v2 ABI including thread-affinity and lifetime contracts.
- Native playout rejects mismatched negotiated frame/channel quantum, zeroing the caller-sized output when safe.
- Regression coverage for C clients, C++ ABI, mismatch and lifecycle.
- VST3 playback in the production engine and full native host readiness remain disabled.

## r126 native ABI v2

Expose immutable C ABI quantum/lookahead negotiation and callback-affine performance counters. The telemetry method is not safe for concurrent UI/control polling. Production playback remains disconnected; native_host_ready=false.

## 0.3.0-r125 — Native PCM input validation and stopped-runtime isolation

- Reject non-finite PCM on native callback before queuing; clear output deterministically.
- Do not playout stale queued results from faulted/stopped/unstarted runtime; return explicit native API error and silence.
- Compiled C++20 regression tests for input validation and native API lifecycle.
- Experimental only: `native_host_ready=false`; full playback integration, latency compensation, MIDI automation, and multiplatform stress tests remain unverified.

## 0.3.0-r124 — Bounded callback result polling

- Hard limit of eight result-queue pops per callback to protect the deadline from stale IPC responses.
- Expose poll-budget exhaustion in native playout diagnostics; compiled C++ regression.
- Experimental only: `native_host_ready=false`, no production callback integration.

## r122: C ABI → persistent Steinberg VST3 IPC acceptance

The experimental native PCM ABI now has a Python control/test harness connecting the C worker thread to the actual isolated VST3 subprocess. CI exercises ADelay mono/stereo via this chain. This is not integrated with the DAW audio callback, and MIDI/automation/latency recovery are not production qualified. `native_host_ready=false`.

## r121: Experimental native runtime C ABI (not ready)

`native/audio_core/vst3_runtime_api.cpp` provides a control-plane create/start/stop/destroy API and a callback-side no-wait PCM exchange. A native shared-library integration test exercises lifecycle and frame safety. This API has **not** been bound to the Steinberg VST3 IPC subprocess or the production playback callback. `native_host_ready=false` remains enforced.

## 0.3.0-r120 — cumulative r101–r120 native readiness gate

This release includes every uncommitted change from r65 through r100. Twenty distinct control-plane validations (quantum, channel shape, sample rate, queue sizing, lookahead, worker scheduling, quiescence, IPC handshake/version, plugin lifecycle, processing, latency, crash recovery, MIDI, automation, platforms and realtime stress) are explicitly checked in native C++ and exercised by parameterized compiled tests. Existing worker runtime now refuses an unsafe restart that could replay stale queue data. **These are acceptance checks, not proof they are all satisfied by MTA's production engine.** The actual realtime host remains disabled: `native_host_ready=false`. End-to-end IPC binding to the native callback, measured latency compensation and multi-platform tests remain open. No claim of production readiness.

## 0.3.0-r100 — native worker runtime (r88–r100)

Cumulative changes since r65 including r87. Thirteen native worker engineering increments: bounded worker configuration, lifecycle states, processor ownership, control-thread start/join, callback/IPC separation, fault latch, scheduling fairness, worker-thread backoff, fault diagnostics, immutable quantum, watchdog integration point, stop statistics and disabled readiness gate. This is an experimental control-plane worker runtime, NOT an end-to-end VST3 realtime host. `native_host_ready` remains `false`.

## 0.3.0-r87 — native VST3 realtime readiness contracts (r78–r87)

Ten cumulative engineering iterations: negotiated playback quantum, transport epoch tokens, frame deadlines, latency budgets, bounded bypass ramps, parameter automation packets, MIDI event packets, worker fault circuit breaker, PCM sanitization, and readiness guard. All are experimental worker/control-plane building blocks; none enable the realtime host. `native_host_ready` stays `false`.

## 0.3.0-r77 — native worker pump and playout shape safety

- Introduced a bounded worker-only processor adapter with finite-output validation and dry bypass on failure.
- Fixed native callback handling of irregular frame counts: delayed output is accepted only for matching shapes; shape mismatch becomes silence instead of a buffer overflow.
- Preserved all cumulative changes through r76; native_host_ready remains false.

## r76 — native playout boundary (not activated)

`native/audio_core/vst3_playout_bridge.hpp` provides an allocation-free callback-side API backed by two SPSC queues and a fixed dry lookahead. Native worker loop and full DAW playback integration, variable block-size transitions, MIDI, state persistence, latency compensation and platform stress testing remain open. No readiness flag activation.

## r75 — bounded native audio block exchange

`native/audio_core/block_spsc.hpp` implements preallocated SPSC blocks with sequence IDs and exact frame/channel metadata. No wiring to audio callback, no claim of hard realtime readiness.

## 0.3.0-r74 — bounded VST3 IPC playout scheduling

Experimental application-thread playout coordinator with explicit block-period lookahead, deterministic dry bypass, late-result discard, bounded backpressure and metrics, seek/stop dry flush. Not suitable for hard realtime callbacks; native_host_ready remains false. Includes all uncommitted r65–r73 revisions.

## 0.3.0-r73 — latency planning and dry-path reference alignment

Adds explicit sample-rate-aware IPC lookahead + plugin delay accounting, bounded PCM delay-line reference, and tests for stereo/mono alignment across irregular blocks. This is an offline reference only; realtime safety and native_host_ready=true remain blocked. Includes r65–r72 cumulatively.

## 0.3.0-r72 — experimental ordered asynchronous VST3 delivery

Adds bounded, application-thread-only block coordinator with ordered processed results, stale-result discard, deterministic dry bypass on late/error output, and regression tests. This is NOT an audio callback integration and native_host_ready remains false. Includes all changes since r65.

## 0.3.0-r71 (includes unpublished r65–r70)

- Experimental bounded asynchronous VST3 IPC bridge (`native/vst3_probe/async_bridge.py`): nonwaiting enqueue/poll, ordered results, backpressure, fault latching and explicit shutdown.
- Python bridge is NOT hard realtime safe: Python locks, allocations, queue operations and scheduling are forbidden in the audio callback.
- Realtime host readiness remains false; latency alignment, bypass recovery, MIDI/state and multiplatform validation still missing.

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

## r66: offline session WAV bridge

The new `render_native_session_wav` API processes a bounded WAV in multiple continuous plugin requests within one session per insert. It is not interactive IPC, and `native_host_ready` remains false.

## 0.3.0-r65 — Offline VST3 session transport hardening (r61–r65 cumulative)

- r61: transport sample positions use the actual processed frames rather than fixed 512-frame strides.
- r62: compare consecutive blocks using previous actual frame length; PPQ follows the real sample clock.
- r63: proactively refuse session requests larger than the remaining frame budget before materializing them.
- r64: reject non-sequence and bytes/string PCM containers; keep native process isolation.
- r65: add odd-sized mono/stereo and input-security regressions, package/revision updates.

Limitations: This is still a bounded offline multi-request subprocess. Interactive IPC and hard realtime guarantees are not implemented; native_host_ready remains false. Existing startup/process-per-session limitation persists.

## 0.3.0-r60 — Native VST3 multi-request offline session (r51–r60 cumulative)

- R51–R52: bounded binary MTASPCM1 session envelope and C++ parser, with up to 128 PCM requests.
- R53–R54: one native VST3 initialization and activation processes successive requests in order, maintaining processing state and continuous musical transport within a session.
- R55: reject truncated payloads, invalid frame counts, unsupported channel counts and sample rates, oversized input, invalid or non-finite PCM.
- R56: separate per-request output frames while keeping the original single-request rendering interface.
- R57: Python adapter handles timeout, exit failures, missing output, invalid envelopes, mismatched dimensions and NaN/Inf.
- R58: optional serial session chain supports up to eight inserts, with per-plugin process isolation.
- R59: protocol, bounds, stereo, malformed responses, and chain regression tests.
- R60: version, cross-platform build metadata and bilingual documentation updated. One release package for all ten increments.

**Scope and limitations:** This implements **multi-request processing in a single offline subprocess session**. It does not yet implement a long-lived interactive daemon or shared-memory realtime IPC, and it does not enable the VST3 host on the realtime audio thread (`native_host_ready=false`). Sessions still have a cumulative limit of 1,048,576 frames, not unlimited WAV streaming. MIDI/event timing and per-job automation are diagnostic-only, not a production sequencer. All external third-party plugins run in an isolated subprocess.

Example API: `render_native_session([[0.0] * 512, [0.25] * 256], (plugin_path, cid), probe_binary)`.

## r50: multi-rate CI regression tests

Two tests from r21 and r27 now assert `pcmSampleRate` in the actual C++ processing setup and musical transport math instead of the obsolete hardcoded 48000 Hz. The runtime is unchanged, and native realtime readiness remains false.

## 0.3.0-r44 (three integrated internal iterations: r42–r44)

- r42: Consolidated batch input/output preflight for atomic publishing.
- r43: Experimental `--atomic-batch` stages every WAV before touching destinations, with same-filesystem backups and best-effort rollback of replaced files.
- r44: Added regression tests for staging failures and rollback. Real-time playback remains unchanged; native persistent worker remains pending.

## 0.3.0-r41 — configurable VST3 offline sample rates
- Add 44.1 kHz, 48 kHz, and 96 kHz support to the isolated native PCM renderer and WAV export.
- Propagate the requested rate to VST3 setupProcessing and ProcessContext, including musical transport timestamps and test stimulus.
- Preserve source sample rate and PCM bit depth in the output WAV; validate unsupported rates before launching the probe.
- Keep the plugin isolated and the realtime engine disabled; a persistent C++ worker is not yet implemented.

## 0.3.0-r40 — VST3 batch WAV preflight
- Add `--dry-run` to the isolated VST3 WAV batch CLI, validating all source WAV formats, sizes, directory targets and collisions before launching plugins.
- Produce machine-readable `ready` reports with bit depth, channel count and frame count; do not create or overwrite outputs during preflight.
- Add functional tests for normal batch rendering, invalid sample rates, missing output directories and CLI behavior.
- Native VST3 worker persistence and realtime audio activation remain explicitly unsupported.


## 0.3.0-r39 — GitHub Actions regressions and VST3 host tests
- Replace obsolete 128-block-only source assertions with checks for the variable-length PCM path and fixed 128-block diagnostic fallback.
- Add functional, mocked tests of VST3 discovery, parameter validation, CLI error handling, and optional dependency failure to increase real application coverage without relaxing the 70% gate.
- Keep the experimental VST3 host isolated from the realtime playback engine.

## 0.3.0-r38 — Safe batch VST3 offline WAV rendering
- Added experimental manifest-driven batch CLI (`python -m native.vst3_probe.batch_wav_cli`) for up to 128 WAV exports.
- Validates all outputs, collisions, CIDs and limits before executing any plugin.
- Reports per-job outcomes in JSON and optionally stops at first error; each output remains atomically published.
- Does not claim a persistent native VST3 process; realtime remains disabled.

## r37 — Standalone WAV command-line interface
Run `python -m native.vst3_probe.render_wav_cli SOURCE DEST --probe EXE --insert VST3_PATH CID`. Repeat `--insert` for chains. Outputs a JSON summary, exits nonzero on errors. Supports 48 kHz mono/stereo integer PCM16/24/32 within 1,048,576 frames. No realtime integration.

## r33 — variable length mono/stereo PCM
The native `--render-pcm CID input output channels` supports 1 or 2 channel interleaved float32 at 48 kHz, 1..1048576 frames. The isolated Python adapter accepts flat mono or stereo tuples. No realtime use or latency correction.

## r32 — isolated native PCM chain
The C++ probe supports `--render-pcm <CID> <input.f32le> <output.f32le>` with exactly 65536 mono float32 frames. `native_chain.render_native_chain` serializes plugin processing in distinct subprocesses. No realtime use; no generalized MIDI, stereo or latency compensation.

## r31 — offline graph executor
Deterministic Python offline insert pipeline with block sample offsets, chain latency compensation, tail flush and fail-closed processing. It does **not** invoke plugins directly: real VST3 subprocess adapter, cross-platform runtime isolation and realtime audits are outstanding.

## r30: Offline graph timing helpers
Implemented native/vst3_probe/offline_graph.py for bounded offline render latency compensation, parallel stem alignment, mixing and tail budgeting and sample-offset MIDI/parameter event batching with regression tests. This is not a plugin host or a realtime-safe callback implementation; no bypass of native_host_ready=false.

## 0.3.0-r28 — offline VST3 event/parameter queues and latency metadata

- Allocated Steinberg SDK event and parameter queues outside the offline processing loop.
- Added opt-in note-on/note-off smoke events only when an event input bus exists, and one bounded parameter point when a writable controller parameter is available.
- Captured processor-reported latency and tail in the offline diagnostic result; **latency compensation is not yet implemented**.
- SDK helper implementations are compiled only when a complete external MIT-licensed SDK is configured.
- The diagnostic path remains separate from production playback. **Not realtime-ready**: callbacks, event queue allocation audit, compensation, plugin crash isolation, full cross-platform CI and audio fixture testing remain.

## 0.3.0-r27 — isolated VST3 musical transport context

- Added a valid Steinberg ProcessContext during all 128 offline audio blocks, with 48 kHz, 120 BPM, 4/4, sample-accurate project position and continuous musical time. The context is confined to the diagnostic process and does not modify playback.
- Added bounded Python validation of reported transport continuity and last project sample.
- Added regressions for monotonic transport and mobile revision consistency.
- **NOT realtime ready:** MIDI event queues, sample-accurate parameter automation, delay compensation, fault isolation and realtime allocation audits are still required. No production host switch has been enabled.

## 0.3.0-r26 — extended offline signal validation

Expanded the isolated VST3 diagnostic to 128 consecutive 512-sample blocks at 48 kHz to exercise the one-second default Steinberg ADelay effect. Reports output energy and a derived non-silent flag. No realtime readiness claim: MIDI, parameter automation, latency alignment, bounded RT callbacks and platform validation remain outstanding.

# VST3 Native Host Development — 0.3.0-r25

The isolated native probe now passes an end-to-end smoke test using the official Steinberg ADelay sample plugin: 16 consecutive 512-sample offline blocks at 48 kHz, deterministic 440 Hz audio input, successful lifecycle and clean teardown, with no nonfinite output. The sample is built by CI from an external MIT-licensed SDK checkout and is not distributed with the application.

This is **not** the threshold for realtime integration yet. Outstanding gate items: nonzero expected output verification with controlled plugin parameters; MIDI/event-list and parameter-change queues; dynamic bus topology and channel mapping, transport/process context, latency and tail compensation, sustained performance and RT allocation audits, plugin crash recovery, and Windows/macOS/ARM64 end-to-end tests. `native_host_ready=false`; existing audio playback remains unchanged.


### 0.3.0-r130: experimental native parallel dry/wet latency alignment
New native/audio_core/vst3_parallel_mix.hpp aligns dry PCM to plugin-declared latency, supports wet/dry mix and fault-driven latency-aligned dry output; tested in C++20. Experimental isolated primitive, NOT connected to production playback. native_host_ready remains false.


### 0.3.0-r131–r135: five native functional preparation cycles
- r131: optional strict negotiated PCM quantum/channel validation on experimental SPSC playout callback.
- r132: coverage for deterministic latency-aligned dry fallback during wet timeout.
- r133: composed IPC lookahead + plugin algorithmic latency budget and per-path alignment decisions.
- r134: bounded sample-offset MIDI and automation packets with epoch/sequence validation (worker preparation only).
- r135: bounded exponential restart policy for control thread, with long-run dry callback regression.
All remain experimental isolated prerequisites; production playback, actual VST3 MIDI/automation forwarding, full fault restart orchestration and platform acceptance are not implemented. native_host_ready=false.
