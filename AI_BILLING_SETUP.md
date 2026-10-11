## Current policy: bill GPU runtime, not electrical energy

GPU usage is charged solely through verified `gpu_seconds` (as well as independently enabled CPU or persistent-storage charges). `gpu_energy_joules` remains **non-billable diagnostic telemetry** even if a legacy nonzero energy tariff exists. Energy estimates from calibrated idle/full-load power must never be ingested as measured GPU seconds or monetary charges. Reports may display measured or estimated energy with clearly identified provenance. GPU runtime without trusted per-job coverage cannot be billed. Disk temporary files remain excluded.

# AI accounting, tariffs, and billing (r207 preview)

Administrators can open `/admin/ai-billing` and `/admin/ai-tokens` on the **MTA** server. Jobs belong to the authenticated MTA user. Remote clients use personal bearer tokens through the MTA gateway; they must not call ACE-Step directly over the public internet.

## Resource rates and effective dates

Tariffs are denominated in **EUR per resource unit**, persisted in integer micro-EUR. Available resources include `cpu_seconds`, `gpu_seconds`, `gpu_energy_joules`, `disk_gb_hours`, `disk_read_bytes`, `disk_write_bytes`, `request_bytes`, and `response_bytes`.

Every rate has a **valid from** date (UTC). **Valid until** is optional: an empty end date means the rate remains active. The end is **exclusive**. Adding a later rate automatically ends the previous open-ended rate at the new start date. Overlaps are rejected. Costs use the rate effective when the job **started**, not today's rate. Changing rates after closing a billing period does not change its stored invoice snapshot.

Admin API: `GET /api/admin/ai-billing/prices` returns current applicable prices and validity history. `PUT /api/admin/ai-billing/prices/{resource}` accepts `micro_per_unit`, optional `valid_from` (`YYYY-MM-DD` UTC), and optional `valid_until`. Omitted `valid_from` means current UTC instant, whereas the web UI accepts a start date. `GET /api/admin/ai-billing/report?period=day|week|month|year|custom` supports `anchor` and custom `start`/`end` dates. `POST /api/admin/ai-billing/close` closes a period for a user.

## Billing limitations

Meters must be sourced from a trusted worker or GPU/cgroup agent. Duration of an HTTP request is **not** equivalent to CPU/GPU consumption. The current job ledger and rates do **not** themselves execute or meter all AI models. Billing closure rejects unmetered jobs; amounts may not be production-billable until each worker is instrumented, concurrency is accounted for, and storage usage is attributed. No automatic periodic charge collection, invoice payment, or tax accounting is implemented. The billing UI shows estimates and manually closed period snapshots.

For internet deployments, keep `/api/internal/ai-metering/` inaccessible from the public reverse proxy and provide a strong `MTA_AI_METERING_KEY` only to trusted metering agents.

## Automatic scheduled closing (UTC)

The Linux server wizard installs `mta-ai-billing.timer`, which invokes the one-shot `python -m app.ai_billing_scheduler` daily at 02:15 UTC. Configure weekly/monthly/yearly per-user schedules on `/admin/ai-billing`. The runner closes only the most recently completed full UTC period, idempotently; incomplete or unmetered jobs block closing, rather than generating a partial charge. View logs with `journalctl -u mta-ai-billing.service`. Run manually with `systemctl start mta-ai-billing.service`.

The admin page supports CSV export of per-day, per-user resource totals and usage cost. Billing periods are immutable internal accounting snapshots, **not fiscal invoices**; no VAT, payment collection, currency conversion or automatic billing emails are provided. Resource meters are accepted only from authenticated internal agents; individual remote models still need process-level instrumentation for trustworthy metered costs.

## r207: Linux process meter (partial, not yet production-grade GPU billing)

`app.ai_metering_agent.run_metered_process()` isolates CPU readings to the direct worker PID using Linux `wait4` and collects best-effort physical disk read/write counters from `/proc/<pid>/io`. It does **not** attribute forked descendant processes, shared GPU activity, VRAM occupancy, GPU energy or persistent disk storage. The `execute_registered_worker()` entry point writes the AI job ledger and validates a WAV preview from the trusted, operator-configured worker. Failed invocations are recorded. Metrics without reliable provenance remain missing, never replaced with wall-clock estimates.

Clients with a personal AI token can submit **self-contained JSON** inference plans to `POST /api/ai-jobs/execute`. Only the administrator's fixed `MTA_AI_WORKER_EXECUTABLE` is run, with `MTA_AI_WORKER_ENABLED=true`; the API rejects caller-defined executable paths and source file paths. Successful requests return a WAV and `X-MTA-AI-Job-ID`. Audio uploads for Whisper/Demucs/other workers, process-tree CPU metering, per-process GPU metering, retained-disk byte-hours, and reliable concurrency attribution remain unimplemented. Thus this endpoint is for controlled tests rather than generalized remote AI production usage.

**Do not enable nonzero GPU, storage, or energy tariffs based on this process meter alone.** Full chargeable accounting requires dedicated job-scoped cgroups and GPU telemetry appropriate to the actual AMD/NVIDIA hardware, independently verified against overlapping workloads.

### Resource attribution and billing safety (r207)

`app/ai_metering_agent.py` reads CPU consumption from Linux `wait4()` for the
specific directly launched worker PID, and block I/O from `/proc/<pid>/io`.
It **never** bills machine-wide CPU usage (`/proc/stat`), overall GPU load,
or host-wide disk statistics (`/proc/diskstats`). Output WAV bytes are not added
again to process block I/O, avoiding double counting.

If a directly launched worker is observed spawning subprocesses, its results
are marked **unmetered** rather than charging partial CPU/disk values as
complete usage. Such jobs block automatic billing. This observation is a
safety check, not full process-tree accounting: short-lived subprocesses may
be missed without a dedicated cgroup-v2 scope. GPU seconds, GPU power/energy,
VRAM and persistent storage quotas also remain unmetered in this fallback.
Consequently, **do not use this fallback as the basis for production consumption
billing**. A per-job cgroup v2 and device-specific GPU telemetry integration,
with actual server hardware validation, is required before enabling full billing.

## Persistent storage accounting (r207 refinement)

Disk capacity billing only accepts snapshots from an explicitly assigned,
per-user **persistent** directory via `ai_billing.measure_persistent_directory`.
The scanner ignores `tmp`, `temp`, `.tmp`, `cache`, `.cache`, `previews`,
`.preview`, `__pycache__`, partial files and symbolic links. Model caches,
session previews, ephemeral worker output, host-wide disk usage and shared
model weights are **not** billed as user storage.

`disk_read_bytes` and `disk_write_bytes` are retained for compatibility and
potential diagnostics but never contribute to charges. In particular `/proc`
I/O counters cannot distinguish temporary files from persisted assets.
Disk occupancy is integrated between successive samples as GiB-hours, not
charged from transient writes. A period without sufficient storage samples
cannot be represented as a fully audited storage bill. Operators should
provision a dedicated per-user persistent directory and periodic sampling
with trusted user-to-directory mapping; the current release does not
create or populate that mapping for all pre-existing project storage.

**Remaining production limitations:** GPU/VRAM/energy attribution for each
job, full worker process-tree accounting and universal remote AI execution
are not yet fully implemented. Neither HTTP duration nor host GPU utilization
is a valid substitute for billable, per-job GPU measurements. Do not issue
consumption invoices until trustworthy telemetry is configured and verified.


## Automatic persistent-storage sampling (r207)

Set `MTA_AI_USER_STORAGE_ROOT=/var/lib/mta/ai-user-storage` in the server
`/etc/mta/mta.env`, then create per-user directories named with the numeric MTA
user ID (e.g. `/var/lib/mta/ai-user-storage/12`). **Only those directories**
are sampled by `app.ai_storage_sampler`; it does not scan the host, ACE-Step
model caches, or temporary worker directories. A missing user directory is
measured as zero. Subdirectories and files in cache/tmp/preview categories are
ignored, as are symbolic links. The root must exist and must not be a symlink.
The daily `mta-ai-billing.timer` runs the sampler before closing periods.
To manually sample: `python -m app.ai_storage_sampler`.

Intervals longer than 26 hours between storage samples are **not billed**
because the intervening occupation is unknown. This is conservative; it is not
a statement that storage was unused. Inaccurate sampling clocks, stale samples
or filesystem layouts that do not assign unique persistent roots to individual
users must be resolved before financial use. For higher accuracy, schedule the
sampler more frequently than once daily and sample upon creation/deletion.

GPU/VRAM/energy accounting and complete subprocess-tree CPU attribution are
**not yet implemented**. No host-global metrics are charged. This package is
not certified for automated monetary billing.


### Fail-closed period validation (r207, updated)

Before closing a period, the ledger rejects overlapping previously closed periods,
unfinished/failed/unmetered jobs, and jobs that started before the period but
continue into it. A crossing job requires explicit allocation before invoicing.
When `MTA_AI_USER_STORAGE_ROOT` is set, storage readings must cover both
period boundaries, and every sampling gap must be at most 26 hours. Missing
samples are **not** interpreted as zero usage. Temporary files and per-process
read/write I/O remain excluded from chargeable persistent storage.

These safeguards do not replace complete per-job GPU telemetry or cgroup-based
process-tree isolation. GPU charges must not be inferred from host utilization;
this release is not certified for production consumption billing.

### Delegated cgroup v2 CPU process-tree accounting (r207 enhancement)

For servers with a Linux **cgroup v2 subtree explicitly delegated to the MTA
service account**, set `MTA_AI_CGROUP_PARENT` to the writable directory below
`/sys/fs/cgroup/` (e.g. `/sys/fs/cgroup/mta-ai-delegated`). The directory and
controllers must be delegated by systemd/the administrator; do **not** chmod
host-wide cgroup directories or run the public application as root. If the
variable is unset the earlier conservative direct-PID fallback remains.

Each worker joins a fresh job-specific cgroup **before executing AI code**.
Its `cpu.stat/usage_usec` and `io.stat` report process-group counters, including
short-lived descendants, without sampling the overall machine. `io.stat` is
**diagnostic only**; temporary files are not billed as persistent disk storage.
If the cgroup is unavailable, exits nonzero, times out or retains active
children, the execution fails closed rather than accepting incomplete CPU
numbers. Nested containers/LXC must be configured to permit delegation.

**Limitations:** the cgroup agent measures CPU, not per-job GPU time, VRAM or
energy. AMD ROCm and NVIDIA GPU accounting require workload/device-specific
instrumentation and validated allocation, especially under concurrency.
This build does not yet connect all inference models to the same remote
execution endpoint. It is **not certified for production consumption billing**.

### Strict delegated cgroup preflight (r207 cumulative)

For job-level CPU and I/O measurements, `MTA_AI_CGROUP_PARENT` must point to a dedicated, writable cgroup v2 subtree with **both `cpu` and `io` enabled in `cgroup.subtree_control`**. The runner now verifies `cgroup.events: populated 0` recursively before and after execution, so a surviving worker in a nested cgroup cannot be misclassified as finished. If these requirements fail, job metering and billing fail closed. These counters belong to the job cgroup, not the host. Disk I/O remains diagnostic: temporary files are never counted as billed persistent storage.

**Remaining deployment limitation:** per-process AMD/ROCm GPU execution time and energy require a trusted sensor and hardware validation. The cgroup accounting mechanism alone cannot certify GPU charges; do not enable GPU pricing for production billing without this integration.

### GPU priced-period closure guard (r207 cumulative update)

If any positive GPU-second or GPU-energy tariff overlaps the requested billing
period, completed GPU-capable AI jobs must provide **explicit per-job GPU
telemetry** from the trusted `gpu-agent` metering source. A CPU-only `cgroup`
measurement can no longer silently result in a zero GPU charge. Billing closes
with an error when GPU telemetry is missing; ordinary process/host GPU load
is not substituted. Resource-specific devices and process attribution still
require deployment-specific instrumentation and real AMD/NVIDIA GPU validation.
This is an accounting safety control, **not** an implementation of per-job GPU
sensors or support for all remote AI worker types.

### Accurate resource price boundaries and diagnostic-only failed jobs (r207)

Resource tariffs accept a UTC ISO date (`YYYY-MM-DD`) or an offset-aware
ISO datetime (`YYYY-MM-DDTHH:MM:SSZ` or `+HH:MM`); timestamps without a
timezone are rejected. Persistent-user-storage GiB-hours are split at the
actual effective timestamp of each tariff, even mid-day. Temporary files,
worker I/O and shared model caches remain excluded from storage billing.

Reports may expose diagnostic usage for failed or unfinished AI jobs but
never add it to the amount due. Closed billing periods still reject
failed/unmetered work and incomplete storage observations. GPU billing
continues to require trusted per-job GPU telemetry; CPU/cgroup readings
are not a substitute. No GPU hardware validation is claimed here.

### GPU source integrity (r207 hardening)

A regular CPU worker (`worker` or `cgroup`) is not allowed to submit `gpu_seconds` or
`gpu_energy_joules` as if it had measured a GPU. Such values require the separately
authenticated `gpu-agent` source; the GPU source must explicitly report a GPU
measurement. This validates provenance claims in the ledger, **not** the physical
accuracy of the sensor. An actual per-process GPU collector and GPU hardware
validation are still prerequisites for production GPU-based billing.

- Fail-closed paid storage: when an effective positive storage rate exists, closing a period requires a configured per-user storage sampler; missing configuration cannot silently generate a zero charge.


### CPU coverage guard (r207 cumulative)

When a positive CPU tariff overlaps a billing period, every completed job in
that period must contain an explicit `cpu_seconds` measurement from an
accepted per-job meter. A GPU-only agent cannot imply zero CPU usage. Jobs
with missing CPU readings block the billing closure. In particular, a zero
quantity must be a measured zero, not a missing field. This protection does
not validate an external meter's hardware provenance; production GPU billing
remains gated on independently tested, per-job hardware telemetry.

### Billing preflight (r207)

Administrators can inspect `GET /api/admin/ai-billing/readiness` or open
`/admin/ai-billing` and select **Check readiness**. The results check the
availability of a delegated cgroup v2 `cpu`/`io` subtree, trusted AI worker,
and user-specific persistent storage when billable. With a positive GPU rate,
readiness explicitly fails because verified per-job GPU hardware telemetry is
not yet integrated. A configured service key or host-wide GPU utilization
never counts as proof of job-specific GPU metering. This is a diagnostic
preflight, not a production-billing certification.

### Diagnostica DRM per job (sperimentale, non fatturabile)

Impostando `MTA_AI_DRM_DIAGNOSTICS=1` assieme a `MTA_AI_CGROUP_PARENT`,
l'esecutore acquisisce contatori `drm-engine-*` da `/proc/<pid>/fdinfo`
soltanto per i processi del cgroup dedicato al job. I contatori di file
descriptor duplicati dello stesso client DRM vengono deduplicati. La misura
`gpu_diagnostics.observed_engine_seconds` può essere incompleta: processi che
terminano tra i campionamenti e driver senza `drm-client-id` non sono misurabili.
**Non è un contatore di GPU time verificato per billing**, non misura VRAM o
energia e non viene salvato come `gpu_seconds`. Il job resta non fatturabile
per risorse GPU finché non sarà disponibile telemetria affidabile e completa.
Non viene mai usata l'occupazione globale della GPU o dell'host.

- r207 billing hardening: each positively-priced GPU resource must have explicit per-job telemetry; user-supplied job kind cannot bypass GPU checks. An explicit measured zero remains valid. This does not implement a certified GPU meter.

### Per-job GPU DRM diagnostics (r207, updated)

With `MTA_AI_DRM_DIAGNOSTICS=1` and a delegated `MTA_AI_CGROUP_PARENT`, the
AI subprocess runner can now inspect Linux DRM fdinfo for **each PID in the
job's cgroup**. It collects actual DRM engine time counters (ns) and
per-client VRAM allocation/residency gauges (KiB), deduplicating DRM file
descriptors by `(driver, client_id)`. The worker's dedicated cgroup is the
only source of PIDs; no host-wide GPU statistics enter per-user accounting.

The available GPU counters depend on driver and kernel. For ROCm/AMD,
`drm-engine-*`, `drm-memory-vram` and `drm-resident-vram` may be available.
A sampled lifetime is **not guaranteed complete**, because processes can
start and exit between polls and some drivers omit per-client counters.
Consequently GPU readings are marked `billable: false`, exposed only for
diagnostics, and cannot become `gpu_seconds`/`gpu_energy_joules` charges.
Device power readings are global and are **never divided among users** as a
surrogate for actual per-job energy. Billing based on GPU/energy prices remains
blocked until a validated end-to-end device/worker integration is deployed.

## Calibrated GPU energy estimates (r207)

`app.ai_gpu_energy_estimator` offers an **explicitly estimated**, never
measured, energy model using idle/full-load power calibration per GPU:

- **Incremental energy:** `(full_load_watts - idle_watts) * exclusive_job_gpu_busy_seconds`.
- **Total allocation:** incremental energy plus `idle_watts * job_wall_seconds`.

Use an observed, stable calibration on the exact GPU/device/power cap, not a
nominal TDP or aggregate host utilization. GPU busy seconds must come from
job-specific counters with a *non-overlapping* interpretation: concurrent DRM
engine clocks **must not be summed**. If exclusive GPU assignment cannot be
confirmed, or the full process lifecycle cannot be observed, the estimator
returns no attributable energy. Clock and thermal fluctuations make this an
approximation even with fully measured seconds.

Admin-only APIs:

- `PUT /api/admin/ai-billing/gpu-calibrations` with `{"gpu_id":"GPU-UUID","idle_watts":40,"full_load_watts":240}`.
- `GET /api/admin/ai-billing/gpu-calibrations` to inspect calibration profiles.
- `POST /api/admin/ai-billing/gpu-energy-estimate` with `{"gpu_id":"GPU-UUID","gpu_engine_seconds":10,"job_wall_seconds":20,"exclusive_gpu":true,"complete_lifecycle":true,"baseline_policy":"incremental"}`.

These values are intentionally held **outside the billable `gpu_energy_joules`
ledger** and include `kind=estimated_not_measured` and
`billing_eligible=false`. No automatic invoice is generated from them.
Admin confirmation alone cannot certify lifetime coverage or exclusivity:
those are properties to be established by the worker scheduler and GPU sensor.

**Remaining production work:** full-lifecycle GPU process tracing; ROCm/NVIDIA
hardware-driver verification; enforceable exclusive GPU scheduling or a
validated sharing allocation method; integrate all native and server-side AI
workers through metered job execution; test concurrent users and workloads;
and define an explicit contractual policy on whether calibrated estimates
may ever be used in a bill. A measured GPU's instantaneous power/energy is
normally device-wide and may include unrelated host work.

### Concurrency audit (r207, pre-commit)

The durable `ai_compute_jobs` ledger stores both the authenticated `user_id` and
one unique job ID. Completion uses an atomic `UPDATE ... WHERE status='running'`
compare-and-set to reject duplicate or racing worker reports. A parallel-worker
regression verifies distinct user ownership and CPU values and simultaneous
completion attempts. Each `execute_registered_worker` invocation creates its
own temporary working directory; Linux cgroup metering creates an independent
`mta-<random-id>` child group for each invocation. This checks isolation in
software; actual multi-GPU scheduling/attribution remains unvalidated.

**Worker coverage:** `/api/ai-jobs/execute` executes the one operator-configured
worker accepting the JSON request/output WAV protocol. ACE-Step has an adapter
for that protocol. Other existing AI routes (Whisper lyrics, Demucs, lead/backing
vocals, DrumSep, SAM Audio and chord-analysis paths) still call their own
implementations and are NOT universally scheduled or metered through this
endpoint. Claiming that these are accounted for would be incorrect. Required
follow-up is authenticated upload/staging of the source audio, a server-selected
allowlisted worker registry, per-worker process/cgroup isolation, and tests for
concurrent GPU use and cancellation. GPU samples collected from `/proc` are
still diagnostic and not billable GPU seconds without lifecycle validation.

### r207 concurrent worker verification

`bash scripts/install_ace_step.sh --benchmark-concurrent --benchmark-remote-url https://mta.example.org --benchmark-tokens-file /secure/test-tokens.json` executes authenticated simultaneous test requests. Compare returned IDs and per-user ownership in the admin ledger. Observe actual cgroup/DRM telemetry on the Linux server; client wall-clock time is not CPU/GPU runtime. The generated WAV input and worker scratch files are temporary and are not billable persistent storage. GPU runtime must remain unbilled when per-job sensor completeness is not established.

## r207 accounting reconciliation preflight (current cumulative update)

Administrators may call `GET /api/admin/ai-billing/reconcile?user_id=ID&start=YYYY-MM-DD&end=YYYY-MM-DD` to obtain a **read-only**, structured pre-closure report (`ready`, `job_count`, `issues` with problem codes and job IDs). Like `close`, `end` is an inclusive calendar date; all accounting timestamps are UTC. The report identifies failed/unmetered/incomplete jobs, jobs intersecting the period boundaries, missing priced CPU/GPU metrics, untrusted metric sources, overlapping closed periods, and persistent-storage coverage gaps. It never includes authentication tokens.

This report is an advisory ledger audit: it does not replace the `close_period` fail-closed checks, guarantee physically correct GPU seconds, or prove that an untracked worker never ran. Admins must resolve issues and only then request closure. GPU hardware certification and real multiuser native end-to-end testing are still outstanding.

## Atomic billing closure (r207)

`close_period` now holds one `BEGIN IMMEDIATE` SQLite transaction across the
eligibility checks, pricing snapshot calculation and immutable invoice insertion.
The report and tariff reads reuse that transaction rather than opening other
connections, avoiding time-of-check/time-of-use races when concurrent workers
finalize jobs or the administrator edits tariff history. Repeated identical
closures return the existing record. Jobs cannot be inserted retroactively
into a closed interval, nor finalized across a previously closed interval.

The targeted concurrent regression closes a period from four threads while
checking that only one snapshot is inserted. This is a database consistency
check, **not** hardware GPU metering certification; physical GPU validation and
native platform end-to-end tests remain outstanding.

### Audit fatture chiuse (r207, controllo di integrità)

`GET /api/admin/ai-billing/audit-closed` (opzionale `?user_id=...`) verifica senza scritture gli snapshot immutabili già chiusi: coerenza del totale salvato, totale delle righe, JSON, intervalli e sovrapposizioni. Non ricalcola importi con tariffe correnti e non certifica la precisione dei sensori fisici. Conservare backup del database e limitare l'accesso agli amministratori.

### Riconciliazione benchmark concorrente con registro server

Eseguire il benchmark con `scripts/benchmark_ai_concurrency.py --verify-ledger /path/to/auth.sqlite3` **sullo stesso host del server** (per accedere in sola lettura al registro). Il report include `server_verification` con ID job, ID utente, stato e secondi CPU/GPU registrati, e rileva account di prova non distinti o job non presenti. Non include token nel JSON. La verifica dei secondi GPU richiede ancora confronti con la telemetria AMD/NVIDIA reale e non attribuisce GPU time mancante. Su installazioni containerizzate il file del registro va reso leggibile nel contesto del benchmark oppure si deve eseguire il controllo nel container. Non esporre il database via HTTP.

Il test anti-fallback per le sette famiglie native (`tests/test_r207_native_remote_routes.py`) simula errori remoti e controlla che siano propagati, ma non sostituisce il collaudo su Windows/macOS/Linux con monitoraggio dei processi locali.

### Recupero conservativo dei job orfani (r207)

Dopo un crash del server, un job può rimanere `running` senza una finalizzazione. La funzione
`app.ai_billing.recover_stale_jobs(older_than_seconds=86400, dry_run=True)` elenca i
job più vecchi della soglia (minimo 3600 secondi), ma **non li modifica** per impostazione
predefinita. Eseguire `dry_run=False` esclusivamente dopo avere verificato sul server
che i processi AI corrispondenti non siano più in esecuzione e che il loro metering
non stia per finalizzare il job. La procedura aggiorna in una transazione atomica
soltanto job ancora `running`, marcandoli `failed` / `unmetered` e registrando un
consumo vuoto: non attribuisce CPU o GPU inventate e non produce addebiti per questi
job. Ripetere il recupero è idempotente. Evitare l'automazione basata soltanto
sull'età del job, poiché inferenze reali possono durare a lungo.

### Remote AI idempotency (r207 refinement)

Native remote WAV requests now send `X-MTA-AI-Idempotency-Key` (32-character UUID
hex by default). The server persists a unique `(user_id, request_key)` claim
before launching inference for both JSON and WAV execution endpoints.
A repeated key with identical content returns HTTP 409 with a structured
`duplicate_request` state and, once known, the original `job_id`; different
content using the same key returns HTTP 400. Concurrent admissions serialize
through `BEGIN IMMEDIATE`, preventing duplicate jobs/accounting. Users remain
isolated from one another. The native client can provide `request_id` to reuse
an idempotency key across an explicit retry; it does **not** auto-retry timeouts.

Claims in `admitted` state after a crash are **not** automatically restarted or
removed because a worker may still be running. An operator must first inspect
worker state and the job ledger. Completed responses are **not** replayed from
the ledger: a 409 deliberately prevents a second charge, but may require manual
artifact recovery. Legacy clients that omit the header do not yet gain the
idempotency guarantee. This is a software safety refinement, not GPU billing
validation or an end-to-end hardware certification.

### Inspecting an ambiguous remote AI timeout

A client that knows its original `X-MTA-AI-Idempotency-Key` can query:

```http
GET /api/ai-jobs/request-status/{request_key}
Authorization: Bearer <user-token>
```

The owner-only response includes `state` (`admitted`, `completed`, `failed`), `job_id` (when recorded), and `created_at` (Unix seconds). Unknown requests return 404; a token belonging to another user cannot read the claim. This request **does not** re-execute the job and does not replay lost WAV/ZIP results. Preserve the original key when investigating a timeout; a new key creates a new inference and may be charged separately. For existing or stuck claims, investigate server-side job and process status rather than attempting a silent retry.

CI validation of this refinement: `PYTHONPATH=. pytest -q tests/test_r207*` passed (172 tests). Python `compileall` passed. Full coverage suite was interrupted during execution; `ruff` was not installed in the validation environment. Use the full `.github/workflows/ci-cd.yml` checks before merging.

## r207 refinement: optional recovery of completed AI results

To allow a native client to retrieve a completed WAV or artifact ZIP after a lost
HTTP response, set `MTA_AI_RESULT_CACHE_DIR` to a private directory on the **MTA
server** and optionally set `MTA_AI_RESULT_CACHE_TTL` (seconds, 60–604800;
default 86400). Results are not retained if the directory is not configured.
The server writes cache files with private permissions and checks their SHA256
before serving them. `GET /api/ai-jobs/request-result/{request_key}` requires the
original user's bearer token and will never restart inference. It returns 409
for unfinished jobs and 410 for completed jobs with unavailable/expired data.
The original idempotency key must be retained by the client after a timeout.

**Operations:** configure an external cleanup service that deletes expired
cache files; expiry is enforced when reading, but periodic disk garbage
collection is not yet provided. The result cache consumes actual disk capacity,
is not included in per-user persistent storage billing, and should have a
filesystem quota and an operator-defined retention policy. The current native
client still needs explicit orchestration to use `request-result` automatically.

On Linux the non-cgroup worker runner now signals its process group after
termination, including when the leader exits before its descendants; cgroup-v2
is still the preferred method for reliable process-tree accounting. CPU usage
from a detached process tree is not promoted to billable usage.

### r207: recovery and bounded cache cleanup

For opt-in retained AI outputs, configure `MTA_AI_RESULT_CACHE_DIR` and
`MTA_AI_RESULT_CACHE_TTL`. The desktop transport exposes
`app.ai_remote_client.recover_audio(server_url, token, original_request_id)`;
this authenticated GET fetches a retained result, never submits another AI job
and never falls back to local inference. The caller must preserve the original
idempotency key. It is a recovery API; existing desktop screens do not yet
invoke it automatically after a timeout.

Expire stored outputs with a scheduled execution of:

```bash
PYTHONPATH=. python scripts/cleanup_ai_results.py
PYTHONPATH=. python scripts/cleanup_ai_results.py --apply
```

The first command previews expired entries; `--apply` removes only expired
cache pairs with recognized opaque filenames. Configure the command in the
host's systemd timer or cron if retention is enabled. This cache is not billed
as persistent user storage. Do not use shared writable filesystem permissions.

Software checks alone do not certify GPU metering or native installers: complete
hardware and platform-level acceptance tests before enabling real billing.

### Linux LXC delegated cgroup launcher (r207 update)

The wizard's `mta-audio-editor.service` now sets `Delegate=cpu io` and starts
`app.ai_cgroup_launcher`. The launcher moves its own systemd-managed web PID
into a `mta-web-process` leaf of its delegated unit cgroup *before* enabling
`cpu` and `io` on the parent; it then prepares `mta-ai-accounting`, enables
both controllers there, and exports `MTA_AI_CGROUP_PARENT` to the web process.
Each inference runs in a distinct child cgroup via the existing metering agent.
If any step is blocked by LXC/systemd, the web service still starts, but the
accounting environment variable is cleared and paid CPU metering fails closed.
Do not create or chmod the global cgroup hierarchy or run a privileged LXC to
bypass delegation. Verify `Check readiness` after reboot and with actual jobs;
preflight success alone does not certify measurement completeness. This setup
has not been validated inside the user's Proxmox LXC environment.

### Diagnostic accounting and Rocky LXC upgrade (r207 maintenance)

The `ai_compute_jobs.billable` SQLite field distinguishes ordinary billable jobs (`1`) from internal diagnostic runs (`0`). Internal smoke tests should call `create_job(..., diagnostic=True)`. On the first schema upgrade, existing `accounting_validation` smoke tests are marked non-billable, retaining all measurements for audit. Diagnostic usage is visible in reports but excluded from monetary totals and billable-job closure prerequisites. Run period closing tests using a disposable data directory, not the production SQLite database.

The Linux wizard resolves the remote Git ref before deciding whether a source update is necessary. It refuses to replace a checkout with locally modified tracked files, checks for the cgroup launcher before activating systemd, stages dependencies and saves previous source/service for rollback on failed HTTP health. After updating, validate your environment-specific worker startup and ingress externally.
