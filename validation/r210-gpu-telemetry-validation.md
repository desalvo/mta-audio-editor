# GPU telemetry r210 validation

Targeted suite: 27 passed, 1 warning in 4.60s. Includes DRM and AMD-SMI
process deltas, safe collection failures, source/reset/PID identity guards,
zero-counter handling, scheduler terminal persistence, actual JS renderer,
ZIP estimate/status export, and standalone HTTP worker submit/poll/download.
Final targeted run also covers malformed/nonfinite process IDs.

Broad suite: 3182 passed, 4 skipped, 10 deselected, 4 warnings in 166.20s.
Four skips require optional Steinberg SDK/ADelay. Ten existing AF_UNIX cases
are deselected because this environment denies Unix socket creation. These
are not claimed as successful validations. Ruff F/S checks and Node syntax
checks pass for changed Python/JavaScript.

No ROCm hardware, live server or Windows executable tested here. Sources
may be unavailable in the user's LXC; sample availability and attribution
remain to be validated after the updated RPM is installed. New GPU values
remain diagnostic estimates, never verified per-job usage or billing.

User-confirmed on the preceding r210 build: real ACE-Step generation,
automatic progress-dialog close, added playable track, playback after
closing/reopening, diagnostics enablement and ZIP browser download.
New metrology behavior is not yet confirmed on that server.

Version 0.3.0-r210 preserved. No Git or live-server mutation.
