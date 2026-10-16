# r210 diagnostics UI and standalone ACE-Step worker repair

Version remains 0.3.0-r210. All source files from the supplied cumulative archive
are retained. No Git operation, live service change or hardware certification.

## Confirmed source defects

- The tab handler hid every other settings panel but omitted diagnosticsTab from
  its visibility list. The Diagnostics button called the loader while leaving
  its section hidden. Include the panel, and change the admin script cache URL
  so installed browsers receive the repair despite the unchanged revision.
- The installer selects app/ace_step_http_worker.py as an absolute file. The
  worker protocol invokes Python on that file from a temporary job directory.
  Its relative AceProcessMeter import failed without a package context, before
  it could contact ACE-Step. Support both module and absolute-file invocation
  using the installed sibling module, independent of cwd/PYTHONPATH.
- The stderr filter recognized Python exception lines but not the adapter's
  handled-error prefix. ZIP event capture deliberately excluded log messages,
  so even journal details were absent from support bundles. Add allowlisted
  failure categories and exit codes to structured events and the job error.
  Raw stderr, prompts, credentials and endpoint URLs are not added to ZIPs.
- Diagnostic event capture now also tolerates an unavailable diagnostic directory
  during the enabled-state check, preventing a logging failure from masking the
  original worker error.

## Preserved safety and accounting

Administrator authorization protects settings, creation and downloads. Mutations
require X-MTA-Request. Disabled diagnostics deny creation/download; ZIPs remain
private, temporary and no-store. No cgroup controller/delegation, recursive
population, cancellation or settlement check has been relaxed. A failed worker
still raises and cannot return a verified Measurement. GPU samples remain
non-billable diagnostics; no CPU/GPU time is inferred from wall time.
The separate ACE-Step HTTP service is not automatically part of the HTTP adapter's
cgroup: adapter CPU is not a certificate of the inference service's CPU/GPU use.

## Validation and deployment follow-up

Tests exercise actual JS click handlers, API authorization/enable/create/download,
installed-file and module startup, and multipart submit/poll/WAV download through
a loopback ACE-Step simulation including 100% progress. See validation report
for counts and environment limits. Simulation does not validate ROCm inference.

After building/installing the new RPM, open Settings > Diagnostics, enable and
save diagnostics before reproducing a generation. Create and download its ZIP.
If generation still fails, its job error and events.jsonl can distinguish import,
dependency, cgroup launch, connection, authentication, missing endpoint and generic
adapter failures without exporting arbitrary error messages. The old service
error alone cannot establish whether additional ROCm/model/API failures remain.

Still required on the real server: actual ACE-Step/ROCm generation, UI completion
and automatic close, measured versus estimated/unavailable CPU/GPU presentation,
playback and persistence after reopening, and browser ZIP download. Earlier
successful playback/persistence is historical evidence, not a new r210 server
certification. No production server certification is claimed.

Suggested commit (since the user committed the supplied baseline):
Fix r210 diagnostics tab visibility and standalone ACE-Step worker startup with safe failure reporting and regression coverage
