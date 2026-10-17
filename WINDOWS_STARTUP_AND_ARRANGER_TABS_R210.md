# Windows startup and Arranger tabs — 0.3.0-r210

This cumulative package preserves the full preceding global AI / GPU billing package.
VERSION remains 0.3.0 and REVISION remains 210. No commit, push, tag, release or live-server change was performed.

## Failure identified

The supplied native-startup log identifies `ai_publish_outbox.recover()` raising
`Cross-process publication recovery requires POSIX flock` during the FastAPI
lifespan startup. Uvicorn then exits with SystemExit(3), before native HTTP readiness.
The unconditional platform gate also failed with an empty publication outbox.
The log does not identify CPU or RAM capacity as the cause.

## Changes

- A shared OS lock facade uses flock on POSIX and byte-range msvcrt locking on Windows.
  Contended blocking locks retry; nonblocking locks report contention. The fixed byte
  offset and retained lock files preserve exclusion across processes. Unsupported
  backends fail closed. Publication recovery is retained rather than bypassed.
- Project publication, shared media, billing settlement and result-cache locks use
  the facade. Unix-only private-file mode and cache directory flags are adapted
  for Windows while preserving POSIX fsync and validation. Windows files inherit
  directory ACLs; this does not claim that POSIX mode bits configure Windows ACLs.
- Windows job recovery queries process exit status and creation time using Win32
  APIs. It never uses os.kill(pid, 0) to probe a Windows process. Inaccessible
  process identities are treated as unknown instead of proof of process death.
- Arranger Source / Arrangement / Execution tabs have explicit text and background
  colors in both selection states, explicit WebView text fill, and visible keyboard
  focus. Both text/background pairs exceed a 4.5:1 contrast ratio. The tabs remain
  selectable; nonselected does not mean disabled.
- The native Windows CI job runs publication/locking/lifespan regressions before
  packaging. It retains the existing built-executable --native-smoke startup check.

## Validation

See `validation/r210-windows-tabs-report.json` and the accompanying pytest JUnit,
coverage and log files for the final executed counts and checks. The targeted
suite covers actual cross-process exclusion/release, mocked msvcrt retry offsets,
unsupported-backend rejection, real startup lifespan and health, WAV publication
and reopening without duplicate replay, nested project locks, Windows liveness,
private native settings and cache without Unix flags, and tab contrast/focus.

This Linux environment cannot execute the real Win32 process API test or run the
Windows installer/WebView. That test is skipped here and enabled in Windows CI.
The initial full run found CMake missing from the restored test environment; it
was installed before the final run. Ten existing Unix-socket agent cases are deselected: this runner rejects AF_UNIX
socket creation with PermissionError (operation not permitted). Existing optional
SDK skips are recorded in the logs. No hardware GPU inference or calibration was
performed as part of these Windows fixes; existing billing evidence requirements
and GPU certification limitations remain in effect.

## User verification after building

1. Commit the cumulative changes and run CI / native Windows packaging.
2. Install the new Windows build; confirm startup and local /api/health readiness.
3. Create/open/save/reopen a project and check Source, Arrangement and Execution
   labels in selected and unselected states, including keyboard focus.
4. Run a short AI job with the chosen local/remote engine; check completion, track
   playback and persistence after reopening. No publication should be duplicated.

Suggested cumulative commit message (since the last user commit):

`Fix Windows startup and Arranger tabs; unify queued AI engines, native setup, accounting, notifications, GPU billing and media workflows`
