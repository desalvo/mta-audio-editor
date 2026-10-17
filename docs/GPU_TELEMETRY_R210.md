# r210 GPU process telemetry and diagnostic reasons

The user confirmed on the updated Rocky Linux 10 LXC/ROCm server: a 10-second
ACE-Step orchestral generation completed, elapsed and CPU appeared, the dialog
closed automatically, and the added track plays after closing/reopening. The
downloaded support ZIP confirms completion at 100% and cpu_seconds=2.25995, but
gpu_seconds=null. That historical ZIP did not include estimates or error reasons;
it cannot establish the exact cause of missing hardware counters.

## Changes

- Sample the local ACE service process before submitting inference, rather than
  only after the HTTP submission response.
- Try per-process DRM fdinfo engine counters, using the existing collector with
  duplicate-descriptor handling. If unavailable or zero, try the AMD-SMI process
  GFX nanosecond counter. Never use global device utilization or wall time.
- Validate Linux process start identity before and after reads; reject PID reuse
  or restarted processes. Reset GPU baseline after a source change or counter
  regression. Never carry a last displayed GPU estimate across a failed read.
- Persistent zero counters are explicitly unverified; do not silently present
  unsupported zero as a verified GPU measurement.
- Emit allowlisted status/source strings (no arbitrary stderr, PID, paths or
  prompts) and persist them transactionally in the scheduler before sidecar
  deletion. Existing databases receive nullable TEXT columns without rewriting
  historical job values.
- Client and administrator views display a diagnostic process estimate marked
  non-billable, or the reason for its absence. Browser script cache URLs change
  while VERSION/REVISION remain 0.3.0-r210.
- Support ZIP now includes cpu_seconds_estimated, gpu_seconds_estimated,
  gpu_metrics_status and gpu_metrics_source alongside verified fields.

## Accounting boundary

All new GPU values use gpu_seconds_estimated; they never become gpu_seconds or
a verified Measurement. CPU measurements of the HTTP adapter do not certify
CPU used by the separate ACE service. Service-process samples may include other
requests and omit subprocesses or work between samples. Engine sums can include
parallel engine time and are not exclusive device occupancy. Estimates remain
non-billable. No cgroup, cancellation, delegation or settlement check is relaxed.
No host/LXC PID guessing or automatic privilege/service configuration change.

## Acceptance

Install the rebuilt server RPM, run another short generation, then download a
new support ZIP. The UI will show either an available process estimate or its
absence reason; the ZIP will preserve source and status. No valid counter is
guaranteed on hardware that does not expose it. Actual DRM/AMD-SMI availability
and correct attribution on the user server still require this functional test.
This change does not certify GPU billing or resolve the still-unverified Windows
startup on the user's PC. All prior Windows and diagnostics/ACE worker fixes
remain in the cumulative source archive.

No Git commit, push, tag, release or live server modification performed.
Suggested cumulative commit since the last explicitly confirmed commit:
Fix r210 diagnostics and ACE-Step startup, capture native lifespan failures and report non-billable GPU process telemetry
