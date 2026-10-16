# r210 Windows startup validation

12 targeted cases pass (native readiness, real Uvicorn lifespan failure with
missing console streams, diagnostic directory defaults/override, diagnostics API).
Changed Python files pass Ruff F/S checks.
Actual app.main native HTTP startup and clean shutdown pass in a separate process
with a temporary user directory and stdout/stderr=None.

Broad regression: 3171 passed, 1 failed, 4 skipped, 10 deselected, 4 warnings
in 137.37s. Failure: test_r207_authenticated_worker_e2e.py::
test_authenticated_worker_records_once_and_rejects_duplicate expected resource
source worker but observed unmetered. All 5 cases in that file pass when rerun
(1.18s). This is an observed nonreproduced accounting test failure, not a claim
of an entirely green broad run. No accounting safety check was changed.
AF_UNIX cases remain excluded due to environment restrictions; four optional
Steinberg SDK cases skip.

Environment: Linux, Python 3.12, Uvicorn 0.54.0, FastAPI 0.142.2, Pydantic
2.12.5, pytest 9.1.1. No Windows executable or user's hardware available here.
The user-supplied log lacks the original lifespan exception; machine-specific
root cause and Windows fix acceptance remain unverified.

Version remains 0.3.0-r210; no commit, push, tag, release or server operation.
