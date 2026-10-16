# r210 — AMD-SMI installer tests on non-root CI runners

## Failure and correction

GitHub Actions run [38961516755, job 117177480357](https://github.com/desalvo/mta-audio-editor/actions/runs/38961516755/job/117177480357)
tested commit `5a262e79ee045e8e52663806fd25d644df3ff0b5` on Python 3.14.
Three installer transaction tests failed before reaching the source-pin or
library-verification checks: the runner owns pytest's temporary directory,
while the production installer correctly requires a root-owned parent without
group/other write permission. The previous development environment ran as root,
so that accidental test dependency was missed. CI coverage was already above
the required threshold (74.55% versus 70%).

Only `tests/test_r210_amdsmi_sidecar.py` changes in executable project code.
Transaction tests now explicitly model trusted parent-directory metadata for
their own temporary directory. Other paths retain their real metadata; pytest
restores the patch after each test. No chmod/chown, sudo, root-only skips,
production bypass or CI workflow changes are introduced.

Five additional cases verify rejection of non-root-owned or group/other-writable
installation parents before any clone or staging work. Another case verifies
that a non-root `--install` invocation is rejected before calling the installer.
The production script, service configuration, source pins and billing gates are
byte-for-byte unchanged from the failed commit.

## Reproduction and validation

- Replayed the original tests with the temporary parent's UID reported as 1001:
  all three original failures reproduced. `r210-amdsmi-ci-before.log` records
  this **expected failing baseline**, not the corrected result.
- Corrected targeted suite: **29 passed**.
- Corrected suite with CI-style temporary-parent ownership metadata: **29 passed**.
  These are simulated ownership tests, not an actual non-root process: the local
  sandbox maps only UID 0. Metadata simulation is limited to the pytest parent.
- Ruff across `app`, `native`, `tests`, `scripts/k8s-wizard.py` and the installer:
  **passed**.
- Full local regression: **3278 passed, 4 skipped, 10 deselected, 4 warnings**
  in 121.01 seconds. Coverage **74.46%**, above the required 70%. The four skips
  require optional Steinberg SDK/ADelay binaries; the ten excluded cases need
  AF_UNIX integrations unavailable in this execution environment. Results are
  recorded in `r210-amdsmi-ci-full.log`, JUnit XML and coverage XML.
- Local Python is 3.12; the next GitHub Actions run must confirm Python 3.14.
  No remote workflow was rerun against unchanged code.
- All existing files from `MTA-r210-amdsmi.zip` are retained. Full GitHub tree
  comparison with the failed commit found only the intended test-file change
  before adding this cycle's validation evidence.
- Version remains **0.3.0-r210**. No Git commit, push, tag, release or live-server
  operation was performed. ROCm profiler acceptance and GPU billing validation
  remain pending on the user's hardware.

## Next action

Apply this cumulative archive, commit and push through the normal workflow.
The new commit must pass CI before proceeding with Publish/server installation
and the ACE profiler test documented in `ACE_TASK_GPU_PROFILER_R210.md`.
Retrying the failed job on the old commit would exercise the same broken tests.
