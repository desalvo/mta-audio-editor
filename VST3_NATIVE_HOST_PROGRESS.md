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
