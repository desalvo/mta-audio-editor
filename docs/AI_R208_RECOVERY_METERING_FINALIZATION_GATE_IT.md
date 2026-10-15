# MTA 0.3.0-r208 — attestation gate for remote cache recovery

`recover_completed_job_id()` is permitted to finalize an otherwise admitted request after a crash only if the cached artifact is structurally sound, unexpired and hash-verified. When optional signed metering evidence is present, recovery now also verifies the rotating-key signature and binds it to the request key, worker job ID and worker identity. An invalid or revoked signature makes recovery fail closed instead of marking the request completed. Legacy cache records without a metering envelope retain backward compatibility.

The direct download route already validates signed envelopes; this change gives the crash-recovery completion path equivalent verification. It does **not** certify physical GPU metering, cross-database ACID transactions or live worker execution.

Tests: `PYTHONPATH=. pytest -q tests/test_r208_remote* tests/test_r208_recovery_metering_attestation_gate.py tests/test_r208_durable_remote*` — 504 passed.
