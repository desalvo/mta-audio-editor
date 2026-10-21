# r210 Accelerated offline hardening / Rafforzamento offline accelerato

- Audio-to-MIDI: max 2,000,000 augmenting-path edge traversals per benchmark invocation; exceeding it returns an error rather than a partial metric. Existing 1,000,000 candidate-graph edge cap retained.
- General MIDI: refuse portable synth reconfiguration after its native handle has been closed; avoid a null-handle library call.
- Vocal Studio: existing contracts rerun, no new neural inference claimed.
- Targeted regression: 123 passed, 0 failed, 10 skipped (external GM core/FluidR3 and happy-dom).
- The full regression was not rerun. Previous GitHub outbound review blocker remains unbypassed.
- To complete acceptance: reviewed and authorized model/voice/vocoder/SoundFont assets, actual neural inference, instrument-labeled multi-track benchmarking and UI/hardware testing. No server or Git operations.
