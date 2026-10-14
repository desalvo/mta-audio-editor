# MTA 0.3.0-r208 — Cgroup cancellation and settlement barriers

The real Linux cgroup v2 execution path now rejects a cancellation before cgroup allocation, again immediately before spawning, once after process exit, and once after measurement collection before producing the trusted metering result. This prevents an already-cancelled or late-cancelled request from being reported as a successfully settled, billable worker execution. Errors continue to fail closed and trigger existing group cleanup.

Tests: `PYTHONPATH=. pytest -q tests/test_r208_cgroup_cancellation_settlement.py tests/test_r208_cgroup_worker_handoff.py tests/test_r208_worker_preflight_and_cgroup_environment.py tests/test_r208_real_worker_cancellation.py tests/test_r208_worker_pcm_complete.py tests/test_r208_worker_snapshot_handoff.py tests/test_r180_worker_protocol_and_pdc.py tests/test_r183_worker_capabilities_meter.py tests/test_r207_authenticated_worker_e2e.py tests/test_r208_native_ace_worker_bridge.py` (34 passed).

This does not certify hardware-backed cgroup delegation, GPU accounting, native-app interaction, or the complete AI lifecycle. No Git or live-server changes.
