# r210 three-area closure release notes (uncommitted)

- GM WAV render: stage the PCM in a temporary file; replace the requested destination only after successful output; remove partial output on errors.
- Audio-to-MIDI CLI: reject `--min-instruments` values outside 1–128.
- Test results: 101 passed, 0 failed, 5 skipped (offline subset); pending live model and hardware acceptance.
- No revision/version bump; no Git, release, or server changes.
