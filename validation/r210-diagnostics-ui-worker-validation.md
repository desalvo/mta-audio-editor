# r210 diagnostics UI / ACE-Step startup validation

## Scope

Source: MTA-0.3.0-r210-ai-worker-exit-diagnostics-cumulative(1).zip.
VERSION=0.3.0, REVISION=210, RELEASE=0.3.0-r210 unchanged.
All original archive files retained. Seven original source/test files changed;
new regression test and documentation added. No Git commit/push/tag/release.
No production server or RPM changed by this run.

The original standalone worker was independently reproduced exiting 1 with
`ImportError: attempted relative import with no known parent package` before
processing --capabilities. The repaired file passes this invocation.

## Targeted validation

70 passed, 1 warning (3.81 s). Ruff F/S checks pass on all changed Python files.

Coverage includes:
- shipped admin JavaScript: activate diagnostics, load settings, show API errors,
  return to another tab and hide diagnostics;
- unauthenticated/non-admin denial for every diagnostics API, mutation integrity
  header, strict boolean settings, enable/create/download/disable;
- real ZIP bytes and no-store response;
- standalone installed-file startup from a temporary cwd with no PYTHONPATH,
  plus module invocation;
- loopback HTTP multipart/poll/WAV round trip in-process and in a real standalone
  worker subprocess, including completion progress=100;
- safe worker failure event captured in ZIP, without prompt/credential messages;
- unavailable diagnostic directory cannot mask a worker log record;
- cgroup CPU/I/O, recursive population, cancellation, environment handoff;
- authenticated worker accounting, failed/non-billable jobs and diagnostic-only GPU.

## Environment and limits

Python 3.12; pytest 9.1.1, pytest-asyncio 1.4.0, FastAPI 0.143.2,
Pydantic 2.13.5, NumPy 2.3.5, httpx 0.28.1. This is a local compatibility
run, not the pinned CI matrix or a Rocky Linux 10 RPM/ROCm run.

Ten existing AF_UNIX integration cases cannot bind sockets here (PermissionError,
Operation not permitted). They are explicitly deselected in the broad rerun:
- test_agent_rejects_untrusted_snapshot (7 parametrized cases)
- test_valid_agent_snapshot_is_diagnostic_only
- test_live_diagnostic_redacts_secrets_and_pid
- test_malformed_agent_reply_fail_closed

Four optional compiled Steinberg SDK/ADelay tests skip. The first broad run also
lacked cmake and pytest-asyncio; after installing test prerequisites, the affected
16-case file group passes. The new API fixture was corrected to supply the
same simulated session to middleware and route authorization; its final tests
pass. A broad process started before plugin installation still had three missing
async-plugin failures; the final broad run starts with all prerequisites present.

Real server acceptance remains open: ROCm generation, 100% and auto-close in the
browser, CPU/GPU attribution and presentation, generated-track playback and
persistence after reopening, and the deployed browser's diagnostics ZIP download.

## Final broad result

3170 passed, 4 skipped, 10 deselected, 4 warnings in 94.98 seconds.
No failures among the runnable cases. Ten deselections are environment-blocked
AF_UNIX cases, not successful validations. No full matrix/CI claim.
