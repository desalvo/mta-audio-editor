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
