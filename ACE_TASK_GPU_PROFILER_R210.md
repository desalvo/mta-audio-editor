# r210 — ACE-Step task-scoped ROCm kernel diagnostics

Version stays **0.3.0-r210**. This cumulative archive preserves previous r210 work and provides opt-in ACE task profiling with the source-checkout startup correction. No Proxmox plugin update is required for this profiler.

Current follow-up: [long ACE jobs and cancellation](ACE_LONG_JOBS_AND_CANCELLATION_R210.md)
adds task budgets, cooperative cancellation and profiling in ACE's real diffusion
thread. That guide describes the current capture scope and required restart.

## Why this collection path exists

The user's latest host evidence shows AMD-SMI `gfx_ns=0` in all 56 samples across approximately 60 seconds. Raw amdgpu fdinfo on kernel 7.0.14-19-pve contains memory fields but no `drm-engine-*` time fields, with no access errors. These observations justify trying task activity tracing rather than reclassifying zero as measured GPU time. They do not prove that profiling is supported by the installed GPU/runtime combination.

## Activation on the Rocky LXC

First build/install the updated server RPM through the usual workflow. Wait until ACE is idle. Run **inside the LXC**, as root:

```bash
python3 /usr/lib/mta-audio-editor-server/app/configure_ace_gpu_profiler.py --base /opt/mta
systemctl daemon-reload
systemctl restart mta-ace-step.service
systemctl status mta-ace-step.service --no-pager
```

The helper prepares `/etc/systemd/system/mta-ace-step.service.d/40-mta-gpu-profiler.conf`. It never restarts services itself. The existing unit/environment file and upstream ACE source are preserved. The override selects:

```text
/opt/mta/venv-ace-step/bin/python /usr/lib/mta-audio-editor-server/app/ace_profile_server.py --host 127.0.0.1 --port 8001 --no-init
```

It sets ACESTEP_QUEUE_WORKERS=1, matching upstream's recommended single-GPU queue configuration. Port can be changed with `--port`; the default matches the user's existing local service. An installation using a custom network bind or custom ExecStart arguments needs an operator-reviewed equivalent override; this helper deliberately creates a loopback-only command. Existing environment configuration such as API credentials, device, models and ROCm libraries is inherited.

This launcher runs with the **ACE virtualenv**, not the MTA web-server virtualenv. It imports PyTorch lazily and installs no dependencies. It was reviewed against upstream ACE-Step v0.1.8, commit `dce621408bee8c31b4fcf4811682eb9359e1bc94`, specifically `acestep.api_server.run_blocking_generate` and the canonical module reference used by its CLI. No upstream code is copied into this project.

### Source-checkout startup correction

The reported `ModuleNotFoundError: No module named 'acestep'` came from the
external launcher losing the source working directory that Python includes
when running `-m acestep.api_server`. The corrected launcher restores that
directory to the import path, respecting Python's safe-path option. It inherits
the original service's `WorkingDirectory=/opt/mta/ace-step`; it does not depend
on adding PYTHONPATH or reinstalling ACE. The regression now starts an actual
Python subprocess from an ACE source stub with PYTHONPATH absent.

If the profiler was disabled to restore working generation, leave it disabled
until installing the corrected server RPM. Then repeat the activation commands
above while ACE is idle. Confirm that the service stays active before submitting
the short test. If startup still fails, collect the service journal, then use
the rollback commands below:

```bash
journalctl -u mta-ace-step.service -b -n 160 --no-pager
```

The import correction
does not establish ROCm profiler support or billing eligibility.

## First functional test

Run a **10-second orchestral inference** in Arranger. The live-window collector publishes partial kernel seconds at model checkpoints when supported, then finalizes at the end of the task. Until the first useful checkpoint the GPU value can remain unavailable. See [live collection and unified workers](LIVE_GPU_AND_AI_WORKERS_R210.md) for overhead, activation and runtime coverage. The completion notification shows final GPU kernel seconds and the queue/diagnostics ZIP records:

```text
gpu_metrics_source = ace-torch-profiler
gpu_metrics_status = profiled_kernels_diagnostic
gpu_seconds_estimated = <positive diagnostic kernel-active seconds>
gpu_seconds = null
```

Download the diagnostics ZIP immediately after the run. Check audio playback and persistence as usual. This feature remains opt-in; start with a short task because profiler capture adds overhead and holds activity records until completion. A raw trace above 64 MiB or more than one million events is rejected from diagnostic processing. The temporary raw trace is deleted; it is not exposed through HTTP or included in diagnostics.

If the installed PyTorch build cannot collect ROCm activity, the job still runs and reports `profiler_unavailable`, `profiler_no_gpu_events`, or `profiler_failed`. MTA profiler error messages contain only the failure class, not prompts, configuration or raw trace content; existing upstream ACE logging is unchanged. The previously working host estimate remains preferred when profiling fails and a positive host estimate exists; host estimates are never relabeled as HIP data.

## Measurement and authorization boundaries

- Capture surrounds the actual `service_generate` work of a single ACE task in its GPU thread, not the HTTP adapter waiting time. Other preparation/decoding GPU stages may be outside this capture; the fallback without a compatible handler retains the earlier blocking-task wrapper.
- Only device kernel events are used; CPU spans, HIP API calls and memory-copy intervals are excluded. Overlapping kernel intervals on the single observed GPU are merged, avoiding double counting concurrent streams. Multi-device, malformed and impossible-duration traces are rejected.
- These are observed kernel activity intervals from the ACE process. They remain **diagnostic, nonbillable evidence**: the integration does not attest device exclusivity, external work, complete hardware accounting or invoice eligibility. The existing estimated field carries the diagnostic value; verified `gpu_seconds` and billing gates are unchanged.
- Captures of wrapped generations are serialized. Training or unrelated activity in the same process is not separately certified; do not treat this report as a complete resource accounting proof.
- `/mta/telemetry/{task_id}` uses ACE-Step's existing API-key authentication. It returns bounded summaries for exact ACE task IDs only; maximum 128 reports, retained for one hour. MTA uses the task ID it obtained from ACE submission and the existing configured endpoint/token, never a project-provided URL or path.
- A backend lacking this optional endpoint, a malformed report or unavailable profiler does not invalidate otherwise generated audio. A profiler failure never retries the original generation.

## Disable / rollback

When ACE is idle, inside the LXC:

```bash
python3 /usr/lib/mta-audio-editor-server/app/configure_ace_gpu_profiler.py --disable
systemctl daemon-reload
systemctl restart mta-ace-step.service
```

Only the helper's own marked override is removed. The original ACE service unit resumes its original command. The Proxmox agent and MTA data remain untouched. Disable the hook before moving to an unreviewed ACE-Step release.

## Validation and acceptance

The local regression exercises interval union, invalid/multi-device reports, task identity/authentication, failure without audio loss or duplicate generation, bounded report retention, reversible systemd preparation, standalone launcher/canonical API hooking, HTTP submission/poll/download/report handling, and persistence allowlists. PyTorch activity is simulated in these tests: there is no ROCm GPU in the development environment. Full physical acceptance requires the user's new short inference and diagnostics ZIP. Full-song inference and Windows startup acceptance remain independent outstanding checks. The server is not declared certified.

References reviewed:
- https://github.com/ace-step/ACE-Step-1.5/blob/v0.1.8/acestep/api_server.py
- https://docs.pytorch.org/docs/stable/profiler.html
- https://rocm.docs.amd.com/en/docs-7.2.4/how-to/rocm-for-ai/inference-optimization/workload.html

No commit, push, tag, release or live server operation was performed.
