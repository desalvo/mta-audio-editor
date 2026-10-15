# MTA Audio Editor 0.3.0-r208 — Replay integrity for pending AI audio publications

- `app/ai_publish_outbox.py`: idempotent `stage()` replay now checks the pending WAV is still a regular, non-symlink file whose SHA-256 matches the registered digest before acknowledging it.
- Published jobs can still be safely replayed without their already-cleaned WAV.
- Failures preserve the pending record for diagnosis and do not silently re-create or overwrite the missing or tampered WAV.
- Added four regression tests for missing, tampered, symlinked pending WAV and successfully published replay.
- Selected regression: 34 passed (publication, queue reconciliation, durable planning, billing delivery, remote billing).
- Not a certification of GPU execution, operating-system installers, distributed ACID semantics or the entire native/server inference lifecycle.
