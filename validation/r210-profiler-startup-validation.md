# r210 — source-checkout ACE profiler startup and terminal UI

## Evidence and correction

The supplied service journal shows repeated `ModuleNotFoundError: No module
named 'acestep'` from the external MTA profiler launcher, before ACE can listen
on port 8001. The user confirmed that disabling the profiler restores both the
service and generation. The normal unit runs `python -m acestep.api_server`
from `WorkingDirectory=/opt/mta/ace-step`. Running an external script instead
changes Python's initial module search path and loses the source checkout.

The corrected launcher restores the working directory to the module search
path when Python safe-path mode is not enabled, matching the original `-m`
startup semantics. The canonical ACE module, existing service working directory,
ACE virtualenv, models, credentials and upstream source remain in use. No new
dependencies or changes to billing authorization are introduced.

The Arranger now renders progress and hints from the current job state. Failed,
interrupted and cancelled jobs hide the indeterminate bar, clear the running
instruction, release the Generate button and stop the elapsed timer. A rejected
submission also releases the button and stops the local timer. Retrying restores
active feedback; completion retains 100% and existing automatic modal closure.
Terminal elapsed time uses the server's final duration instead of continuing to
count from the start timestamp. The web script cache key is updated within r210.

## Validation

- Added an external-launcher subprocess case with PYTHONPATH absent and the
  working directory containing an ACE source stub. Before the fix, it fails
  with the exact `No module named 'acestep'` from the supplied journal, while
  the previous explicit-PYTHONPATH case passes. See the intentionally failing
  baseline in `r210-profiler-startup-before.log`.
- Corrected targeted regression: **72 passed, 1 warning**. Includes both
  launcher import layouts, authenticated telemetry, task identity, optional
  profiler failures without losing audio, interval validation, standalone worker
  HTTP round trips, the prior non-root CI fix, and web progress regressions.
- New Node VM tests execute the production watcher and submission handler:
  running → failed/cancelled/interrupted, no subsequent poll, stopped elapsed
  timer, frozen server duration, hidden bar, released button, retry and completion.
  These are JavaScript behavior tests, not screenshots from a real browser.
- Ruff over app/native/tests and relevant scripts passed. Node syntax check
  passed.
- Full regression: **3281 passed, 4 skipped, 10 deselected, 4 warnings** in
  162.28 seconds. Coverage **74.52%**, above the required 70%. Four skips require
  optional Steinberg SDK/ADelay binaries; ten AF_UNIX integration cases are
  excluded because this execution environment cannot run them. JUnit, coverage
  XML and exact output are adjacent to this report.
- Local runtime is Python 3.12. Real AMD GPU profiling and Python 3.14 CI must
  still be validated in their respective environments. No GPU billing or server
  certification is claimed.
- Baseline: full cumulative `MTA-r210-ci-fix.zip`. Compared against repository
  commit `1f7629fd703dbe8fddda3bf681e54fd594e7a258`; only the intended launcher,
  web script/template, profiler tests and guide differed before adding new tests
  and validation evidence. All baseline archive paths are preserved.
- Version remains **0.3.0-r210**. No Git commit/push/tag/release or live-server
  operation was performed.

## Hardware acceptance

Keep the profiler disabled until the corrected server RPM has been installed.
Then, while ACE is idle, use the activation commands in
`ACE_TASK_GPU_PROFILER_R210.md` inside the Rocky LXC. Verify service startup and
run a 10-second orchestral inference. Download diagnostics immediately after
completion. Positive task-scoped kernel activity remains diagnostic and
nonbillable; unsupported collection must preserve successful audio generation.
