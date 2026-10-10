## 0.3.0-r26 — extended offline signal validation

Expanded the isolated VST3 diagnostic to 128 consecutive 512-sample blocks at 48 kHz to exercise the one-second default Steinberg ADelay effect. Reports output energy and a derived non-silent flag. No realtime readiness claim: MIDI, parameter automation, latency alignment, bounded RT callbacks and platform validation remain outstanding.

# VST3 Native Host Development — 0.3.0-r25

The isolated native probe now passes an end-to-end smoke test using the official Steinberg ADelay sample plugin: 16 consecutive 512-sample offline blocks at 48 kHz, deterministic 440 Hz audio input, successful lifecycle and clean teardown, with no nonfinite output. The sample is built by CI from an external MIT-licensed SDK checkout and is not distributed with the application.

This is **not** the threshold for realtime integration yet. Outstanding gate items: nonzero expected output verification with controlled plugin parameters; MIDI/event-list and parameter-change queues; dynamic bus topology and channel mapping, transport/process context, latency and tail compensation, sustained performance and RT allocation audits, plugin crash recovery, and Windows/macOS/ARM64 end-to-end tests. `native_host_ready=false`; existing audio playback remains unchanged.
