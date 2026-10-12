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

### Isolated acceptance validation (r207)

Run without touching the production SQLite ledger, tariffs, or storage:

```bash
cd /opt/mta/application
PYTHONPATH="$PWD" /opt/mta/venv-mta/bin/python scripts/mta_billing_isolated_validation.py
```

The standalone script creates its own temporary MTA_DATA_DIR, user storage,
synthetic prices and jobs, validates CPU/GB-hour calculations, non-billable
validation jobs, idempotent closure, immutable snapshots and retrospective
job rejection. **Never use live production prices for this test.**

The automated regression `tests/test_r207_authenticated_worker_e2e.py` exercises
Bearer-token HTTP execution with a deterministic lightweight trusted WAV worker,
ledger attribution, request-idempotency, cross-user access rejection,
unsafe-command rejection and failed-job non-billing. It runs in a temporary
SQLite database without downloading AI models or using physical GPUs. This is
not certification of ROCm/GPU hardware or the live production ingress.

### AMD ROCm and AMD SMI on the Linux server

The standalone `scripts/install_mta.sh` wizard accepts `--gpu auto|yes|no`.
The default `auto` detects `/dev/kfd` and `/dev/dri/renderD128`; if absent,
GPU userspace installation is skipped. With `yes`, missing device access is an
installation error; `no` intentionally skips the GPU stack. Existing working
ROCm installations are preserved rather than upgraded. On supported EL9 hosts,
when ROCm is missing the wizard configures an AMD-signed userspace-only ROCm
repository and installs `rocm-hip-runtime`, `rocminfo`, and AMD SMI. The default
repository release is `7.2.4` and can be selected using `MTA_ROCM_RELEASE`.
Check AMD's published OS/GPU support for the target distribution before enabling
it: Rocky Linux 9.8 support must not be assumed merely because EL9 packages
are available. The installer never installs `amdgpu-dkms` or host kernel
modules; Proxmox LXC requires its host to provide `/dev/kfd` and `/dev/dri`.
If a different distro is used and the GPU runtime is absent, configure a
supported ROCm repository explicitly. Installation does not enable any paid GPU
metering: PID-specific GFX time must be independently validated first.

### ROCm HIP Events: diagnostic validation (0.3.0-r207)

`hipcc -O2 scripts/hip_event_probe.cpp -o /tmp/mta-hip-event-probe && /tmp/mta-hip-event-probe`
measures the elapsed duration between HIP events for GPU operations on an
instrumented stream. The dedicated validator `app.ai_hip_event_meter.parse_hip_event_sample`
accepts only bounded, synchronized, job-identified sample records, and returns
**diagnostic-only** evidence. It never emits invoiceable `gpu_seconds` or a
trusted `gpu-agent` metering source. HIP events measure stream elapsed time,
not exclusive engine busy time; concurrent clients, multi-stream operations,
PID namespaces in LXC and uninstrumented frameworks remain unverified. The
Strix Halo Radeon 8060S was observed to report `GFX: 0 ns` under AMD SMI
while a HIP event benchmark measured a positive elapsed interval. This does
not establish a billable per-job GPU counter. Keep GPU tariffs disabled.

### Concurrent GPU jobs: diagnostic capacity estimation (r207)

`app.ai_gpu_shared_estimator.estimate_shared_capacity()` provides an opt-in,
**non-billable** GPU-equivalent-capacity calculation (`shared-capacity-proportional-v1`).
For each non-overlapping, scheduler-attested wall-clock window it multiplies
externally observed whole-device utilization by the window duration, then
allocates that capacity among known MTA jobs proportionally to instrumented
HIP-event *activity weights*. The weights are not exclusive GPU time.

Unavailable utilization, unknown external activity and malformed inputs fail
closed: capacity is left unallocated rather than charged to users. HIP Events
alone must not be used to fabricate whole-device utilization. In particular,
when the AMD SMI global utilization is unreliable or not accessible, the
estimator cannot provide verified capacity allocations. Neither the existing
`gpu_seconds` billing metric nor any paid GPU tariff is activated by this
module. No automatic write into the billing ledger is performed.

The method is deterministic and versioned for later controlled calibration;
production scheduling/telemetry integration, trusted provenance, external
process detection and customer-facing consent remain future prerequisites
before any estimated GPU price can be enabled.

### AMD SMI JSON collector and host/LXC correlation (r207)

`app.ai_amd_smi_collector` normalizes `amd-smi process --gpu N --json`
read-only process snapshots. The process IDs are **host GPU PIDs**, which may
not exist in an LXC `/proc`; never assume container PID equals host PID.
`correlate_processes` requires `host_pid_namespace_verified=True` and a
**trusted host-view** `/proc` to verify exact job cgroup membership. This flag
must not be set from an ordinary LXC process. If processes cannot be mapped,
if unrelated processes are present, or if utilization is missing, the shared
estimator leaves GPU capacity unallocated. This collector does not claim that
zero GFX nanoseconds reflects zero GPU work, as Strix Halo/ROCm 7.14.1 tests
show a constant zero despite HIP kernel execution.

For a non-mutating diagnostic snapshot on `ollama-01`:

```bash
amd-smi process --gpu 0 --json
```

Collection is diagnostic only. Global utilization must come from a separately
verified source; neither PID memory nor HIP event elapsed is global GPU
utilization. No GPU price, billing record, background sampling daemon, or
host agent is enabled by this module. Before integrating host PID mapping,
install an authenticated least-privilege host-side agent, with an explicit
job-to-cgroup registry and test against unrelated GPU processes.

Run the related regression tests:

```bash
PYTHONPATH=. pytest -q tests/test_r207_amd_smi_collector.py tests/test_r207_gpu_shared_estimator.py
```

## Agentless GPU slot accounting — development stage (0.3.0-r207)

`app.ai_gpu_slot_accounting` implements a conservative **single logical GPU**
slot-service estimator, independent of ROCm or a Proxmox host agent. Its method
identifier is `agentless-equal-slot-v1`. Trusted server scheduling code must
call `acquire(job_id, gpu_key, at_ms=...)` **only when a GPU slot is granted**,
not while queued, and `release(job_id, at_ms=..., aborted=...)` when the
allocation ends. `preview(gpu_key, start_ms, end_ms, rate_micro_per_second=0)`
computes a repeatable *hypothetical* micro-EUR quote. The default rate is zero.
The API is deliberately **not** exposed to clients: user input cannot create
leases or choose hardware usage. Quotes are **not invoices**, are not attached
to immutable billing snapshots, and do not authorize monetary collection.

For overlapping leases on the same logical GPU, a millisecond of available
slot capacity is shared equally among active MTA allocations. Time spent in
queue does not count. A failed, aborted, non-billable or diagnostic job cannot
receive a monetary quote, while its reservation interval remains in the
capacity split. An active lease or running job in the window prevents a quote.
The computed total never exceeds the chosen window's slot capacity.

This is a **contractual slot-time estimate**, not actual GPU busy time, GPU
energy, HIP kernel execution time, or proof that other host processes were
absent. External GPU usage is explicitly unobserved. Consequently this module
never writes `gpu_seconds`, bypasses `finish_job`'s trusted GPU gate, sets
production tariffs, or creates invoices. Before billing is enabled, implement
trusted, crash-safe integration with the centralized scheduler and worker
lifecycle; persistent device-identity/migration rules, accurate concurrency
coordination across MTA instances, administrator opt-in tariff and disclosures,
ledger/snapshot integration, and full hardware acceptance tests.

Tests: `PYTHONPATH=. pytest tests/test_r207_gpu_slot_accounting.py`.

### Trusted worker slot lifecycle and non-monetary admin report (r207)

The central `execute_registered_worker` now supports an **opt-in** agentless
slot lease. An operator can enable this on the AI server with:

```bash
MTA_AI_GPU_SLOT_TRACKING_ENABLED=true
MTA_AI_GPU_SLOT_KINDS=demucs,whisper,drumsep,sam-audio
MTA_AI_GPU_LOGICAL_DEVICE=gpu0
```

Only explicitly listed, administrator-installed adapter kinds are included.
Select kinds that **actually run on the GPU**; the server cannot prove that a
worker used the GPU merely because it was assigned a logical slot. The lease
starts immediately before launching the subprocess (never at admission/queue
entry), is released on success, and aborted on failure/timeout. Both states
are persisted in SQLite. The release happens before the job is finalized.
GPU slot tracking is disabled by default, and leaves `gpu_seconds` unset.

Admin-only, read-only endpoints:

- `GET /api/admin/ai-billing/gpu-slots/preview?gpu_key=gpu0&start_ms=...&end_ms=...`
  returns a **zero-rate** breakdown, `not_an_invoice=true`; it refuses
  incomplete leases and still-running jobs.
- `GET /api/admin/ai-billing/gpu-slots/recovery?older_than_ms=3600000`
  reports possible stale leases without changing any records.

After a container migration, a killed worker may leave an active lease.
An operator must first confirm the previous worker is gone and then run
`app.ai_gpu_slot_accounting.recover_stale_leases(dry_run=False)` separately.
This recovery deliberately **never** runs automatically and aborts leases;
it cannot fabricate GPU usage or costs. A recovery of the compute job itself
is still handled through the separate `ai_billing.recover_stale_jobs` procedure.

**Not yet enabled or certified:** monetary rates, invoice/snapshot inclusion,
physical GPU utilization, fair sharing across independent MTA installations,
transactionally durable recovery across container migration, and the
agent-assisted measurement tier. The preview's hypothetical rate argument is
not available to end users or as a paid API. Deploying this code does not
change an existing CPU/storage invoice.

Targeted tests:

```bash
PYTHONPATH=. pytest -q tests/test_r207_gpu_slot_accounting.py tests/test_r207_authenticated_worker_e2e.py
```

### Agentless GPU slot-service pricing (r207, opt-in)

The resource `gpu_slot_seconds_estimated` is a **contractual reservation capacity
unit**, never a measurement of exclusive GPU work, energy or processor time.
It is independent of `gpu_seconds` (trusted, measured GPU telemetry), and the
billing engine refuses simultaneous positive tariffs for these two resources.
The default tariff is **zero**; existing deployments do not incur any GPU slot
cost unless an administrator deliberately sets a positive tariff.

Administrators can use the existing authenticated tariff endpoint:

```text
PUT /api/admin/ai-billing/prices/gpu_slot_seconds_estimated
{"micro_per_unit": 1000, "valid_from": "2026-11-01"}
```

This is an *illustrative* tariff and should not be applied to a production
account without first enabling trusted server-side slot tracking, reviewing
service terms, and validating complete evidence. Positive tariffs are versioned
in the existing immutable price history, and charges are split whenever the
rate changes within the reporting period. The normal `report` endpoint includes
`gpu_slot_service` with provenance and an explicit warning that external GPU
activity is not observable without a host agent. Successful jobs only are
eligible; failed, cancelled, aborted and diagnostic jobs are not charged.
A job waiting for capacity has no lease and contributes no slot seconds.

Pricing allocates the logical GPU's capacity across **all concurrently leased
jobs**, even when a report is filtered to a single user. Closing a period uses
the same allocation under the database billing transaction, captures the full
method and evidence in the immutable invoice snapshot, and fails closed when a
lease is still active or crosses the billing period boundary. When slot
tracking is enabled, a configured GPU worker without a lease prevents paid
billing rather than silently becoming zero use. The accounting does not
pretend to see external GPU processes; therefore charging constitutes an
explicit contract for scheduler-assigned capacity, not hardware utilization.

Note: `gpu_slot_service` is absent from older invoice snapshots; old invoices
remain immutable. The `gpu_slot_seconds_estimated` tariff is not yet a generic
host-agent-selected GPU price: automated tariff selection based on hardware
sensor quality remains outside this release.

Regression tests: `tests/test_r207_gpu_slot_paid_invoices.py`.

## Optional electricity-reference price suggestions (0.3.0-r207)

Billing is **off by default for every user**; prices provided here are
**suggestions for statistics and operator configuration**, not live rates that
silently create invoices. The Italian electricity benchmark is EUR 0.4343/kWh
(ARERA, October–December 2026, tax included; not a substitute for an actual
commercial tariff).

| Resource / model | Accounting unit | Indicative rate | microEUR/unit |
|---|---|---:|---:|
| AMD Radeon 8060S | equivalent allocated GPU-slot-second | EUR 0.000010 | 10 |
| AMD Radeon 8050S | equivalent allocated GPU-slot-second | EUR 0.000008 | 8 |
| AMD Ryzen AI MAX+ 395 or MAX 390 | CPU core-second | EUR 0.000001 | 1 |
| Persistent storage (hardware-independent policy) | GiB-hour | EUR 0.000002 | 2 |

The GPU slot unit is **contractually allocated GPU capacity**, divided
conservatively between overlapping jobs; it is not physical GPU engine time.
CPU time means accumulated cgroup CPU time, not wall time. On Strix Halo the
CPU and GPU share an APU power budget, so these model-specific prices are
illustrative service-cost proxies, **not additive physical power measurements**.
Persistent-storage pricing is a fixed generic capacity policy, not a measurement
of the actual underlying storage technology or electricity draw.

API for operators:

- `GET /api/admin/ai-billing/suggested-prices?cpu_model=AMD%20Ryzen%20AI%20MAX%2B%20395&gpu_model=AMD%20Radeon%208060S`
- `GET /api/admin/ai-billing/user-settings` (users not listed are disabled)
- `PUT /api/admin/ai-billing/user-settings/{user_id}` JSON `{"enabled":true}`
- `PUT /api/admin/ai-billing/user-settings/{user_id}` JSON `{"enabled":false}`

Automatic scheduled closings skip all users without explicit opt-in. The admin
HTTP close endpoint rejects disabled users. Direct library billing functions
remain available for **isolated diagnostics/testing** and existing historical
snapshot compatibility. Hardware suggestions are not silently inserted into
historical rate tables: applying real prices is a distinct, explicit admin
operation; keep `gpu_seconds` and `gpu_slot_seconds_estimated` mutually exclusive.
A production deployment that needs different rates for multiple GPU/CPU models
must record the device/model binding per job and apply hardware-specific price
history: this full dynamic pricing path is **not yet implemented**. Thus,
profiles published here are advisory defaults, not automatic per-job rates.

### Radeon 780M and portable profile discovery

The illustrative GPU catalog includes **AMD Radeon 780M** at **4 microEUR per equivalent GPU-slot-second** (assumed GPU power 33.15 W at the 2026-Q4 electricity reference rate). This is a pricing assumption, not a measured power draw. `GET /api/admin/ai-billing/suggested-prices` now tries to identify a GPU agent via `rocminfo` when the `gpu_model` query parameter and `MTA_AI_GPU_MODEL` override are absent. CPU agents are not considered. Missing/ambiguous identification gives no GPU price suggestion. For remote workers the local hardware profile is not proof of the worker's device; per-job hardware bindings and tariff snapshots remain future work. Discovery never installs prices, enables user billing, or creates charges.

### AMD Ryzen 9 7940HS / Radeon 780M indicative rates

The hardware-specific advisory catalog includes **AMD Ryzen 9 7940HS** at **1 microEUR per measured CPU core-second** and **AMD Radeon 780M** at **4 microEUR per equivalent allocated GPU-slot-second**. Persistent storage remains **2 microEUR per GiB-hour**, irrespective of device model. The assumed CPU-core power (8.289 W) and GPU power (33.15 W) are illustrative allocations at the reference electricity price, **not independent measurements of this shared APU**. Avoid interpreting their combined theoretical charges as measured electrical consumption. Device identification is advisory, per-job remote worker identification is not yet proven, and tariff suggestions never enable billing, populate active tariffs, or opt users in.

## 0.3.0-r208 — Billing dashboard and optional Proxmox host agent

The administrative `/admin/ai-billing` page now has a responsive dashboard with
period filters, projected (statistical) prices, per-user billing opt-in, profile
suggestions, GPU-slot diagnostics, scheduler controls, reconciliation, immutable
closure confirmation, invoice audit, and read-only GPU-agent status. No price
suggestion automatically enables billing. The existing administrative APIs
remain protected by `require_admin`.

The **optional** host agent reads `amd-smi process --gpu 0 --json` and host
`/proc/<pid>/cgroup` through a UNIX socket, requiring a random secret stored
outside the repository. To install on an actual Proxmox host with `amd-smi`
already installed, copy the repository scripts there and run:

```sh
sudo bash scripts/install_mta_proxmox_gpu_agent.sh
```

The service uses `/run/mta-gpu-agent/agent.sock`, no TCP port. Explicitly
bind-mount that socket directory (not `/proc`!) into the LXC with matching
permissions. Configure `MTA_AI_GPU_HOST_AGENT_SOCKET` inside the LXC and the
`MTA_AI_GPU_HOST_AGENT_TOKEN` from `/etc/mta-gpu-agent.env` using a secure
secret delivery mechanism; never commit secrets. Review permissions, cgroup
visibility, and Proxmox device passthrough on **each** migration target.
Without the agent or the mount, agentless slot estimation remains available.
The agent reports diagnostics only: host process identification and cgroup
strings must not be treated as certified GPU time or automatic invoice data.

The agent installer deliberately **does not** install AMD host kernel drivers
or alter Proxmox GPU passthrough; those are host responsibilities. The regular
MTA installer handles ROCm userspace inside the LXC. First deployment of the
host agent must be tested on Proxmox before relying on the data; no live host
installation has been performed by these repository changes.

### r208 pre-commit refinement: Proxmox agent and billing dashboard

- The optional Proxmox host agent still reports **diagnostics only**, never
  authorizes billable GPU seconds. The LXC client accepts only a fresh snapshot
  (within 30 seconds), validates every host PID and GPU identifier and rejects
  malformed or replayed responses. A socket bind-mounted at
  `/run/mta-gpu-agent/agent.sock` is detected automatically; set
  `MTA_AI_GPU_HOST_AGENT_SOCKET` to override the path. The authentication token
  must still be configured separately and protected (`MTA_AI_GPU_HOST_AGENT_TOKEN`).
- Host and LXC PID namespaces differ. No PID match is inferred from numeric
  equality alone. Without a trusted host association, GPU slot accounting stays
  agentless. Deploy the host agent per Proxmox node; migrations must rediscover
  the *current* socket. The host service and LXC bind mount still require
  actual operational validation on your Proxmox installation.
- The Billing dashboard GPU preview now supplies an explicit last-24-hour
  interval. Its totals are calculated at *configured historical tariffs*, not
  at advisory hardware-price suggestions. The advisory detected CPU/GPU profile
  and suggested micro-EUR rates are displayed separately.
- Important remaining limitation: the detected model is currently a **local
  advisory profile**, not an immutable hardware identity attached to every AI
  job. Hardware-specific tariffs are therefore **not yet automatically chosen
  per job**, especially following LXC migration or off-host worker execution.
  Do not enable monetary hardware-based billing expecting that behavior until
  this gap is closed and verified. Per-user opt-in remains disabled by default.
- Quality/SAST and host deployment checks must be run against the committed
  package. Regression tests cover protocol validation and the billing UI.

### Proxmox Debian agent (r208, opt-in tags)

Build the standalone host package on Debian/Proxmox with
`bash packaging/proxmox-gpu-agent/build_deb.sh dist`. Install it **on the Proxmox
host**, not inside LXC, with `apt install ./mta-proxmox-gpu-agent_0.3.0-208_all.deb`.
The service requires `amd-smi` on the host; an unavailable AMD SMI leaves the
agent failing safely and does not stop agentless billing inside MTA.

Only containers marked with **both** `mta-audio-editor` and `mta-gpu-agent`
are eligible. The opt-in tag is intentional; discover candidates using
`python3 /usr/lib/mta-proxmox-gpu-agent/tag_sync.py` without `--apply` first.
The systemd reconciliation timer applies a **read-only** mount from the host
`/run/mta-gpu-agent` directory to privileged, explicitly tagged CTs using a
free Proxmox `mpN` mountpoint. It never overwrites existing mounts or restarts
a container. Mount changes take effect after an operator-approved CT restart.
Unprivileged CTs require operator review of UID/GID permissions and are not
auto-modified. Tokens are root-only; never paste them into logs or tickets.

On a tagged LXC, `app.ai_proxmox_gpu_agent_client.snapshot()` discovers the
mounted socket and reads the token from `/run/mta-gpu-agent/token`, with
explicit environment overrides available. On hosts without the agent, or after
a migration to an unprepared host, agentless slot statistics remain available.
These agent snapshots are **diagnostic** and never directly authorize billed
hardware GPU seconds. A token is a shared secret: only opt in trusted LXC
administrators; a privileged LXC with a host bind mount is not a security
boundary against a hostile container administrator.

The `.deb` does not install DKMS/kernel AMD drivers or restart LXC instances.
To uninstall: `apt remove mta-proxmox-gpu-agent`; review previously configured
`mpN` entries explicitly (removal does not rewrite LXC configs).

## r208 hardware snapshots and migration-safe statistical profiles

Every newly created AI job records an immutable, **advisory** local hardware
snapshot in `ai_job_hardware_snapshots`: canonical CPU/GPU name, model/profile
revision and suggested micro-EUR rates. The values are captured when the job
is created, so later host/LXC migrations do not rewrite its historical
statistical identity. `job_hardware_snapshot(job_id)` reads the record, and
`report()` includes `hardware_by_job` for its job set.

These snapshots are *not* authoritative remote-worker attestations: local
`rocminfo`, `/proc/cpuinfo`, and environment overrides can identify the MTA
server rather than the actual remote execution hardware. Consequently they
never select a monetary invoice rate automatically. Financial billing still
uses explicitly configured, historized tariffs and requires explicit opt-in
per user. Jobs created before this additive schema change have no snapshot
and must not be backfilled using the current host hardware.

## r208 unprivileged LXC policy

The tagged Proxmox agent installer does not automatically mount a privileged
host socket into an unprivileged container: UID maps and ownership must be
reviewed by the host administrator. `mta_proxmox_tag_sync.py` reports
`manual-review` rather than silently weakening security. The host agent is
optional and absence of the socket does not interrupt agentless GPU slots.
Any configured mount requires a container restart to take effect; the package
never restarts running containers automatically.

## Acceptance criteria still requiring hardware

Verify actual HIP workers and correct CPU/GPU provenance for remote execution,
privileged/unprivileged Proxmox socket permissions, tagged CT migration to
another host, stale-job recovery and billing dashboard desktop/mobile layout.
No hardware validation or automatic per-worker model attestation is claimed
by the unit tests included with this release.

### r208: statistical energy-cost estimate separate from invoices

The report API now includes `suggested_total_micro` and each daily row includes
`suggested_cost_micro`. These values are **advisory electricity-cost proxies**:
CPU cost uses the immutable local hardware snapshot recorded when each successful
metered job was created; agentless GPU cost uses the job's immutable GPU profile
and its eligible allocated slot share; storage uses the generic suggested
GiB-hour price. Unknown hardware yields no CPU/GPU suggested component, rather
than guessing a model. Diagnostic, failed, and unmetered compute jobs never
contribute a suggested CPU amount. These estimates do **not** change the
existing `total_micro` based on the administrator-configured tariff history,
do not authorize invoice creation, and do not enable billing for any user.
Remote-worker hardware remains **unverified** by these local advisory snapshots;
no automatic hardware-dependent monetary tariff is selected from them.


### Proxmox Debian 13 host validation update (r208.1 agent package)

The updated optional host agent parses **AMD SMI 24.5.2** `amd-smi process
--json`, where each array member can carry `process_info` directly, and the
newer `process_list` shape. It reads `/proc/<host PID>/cgroup` on the Proxmox
host (for example `/lxc/130/ns/system.slice/ollama.service`). `gfx=0ns`
is **not** billable GPU runtime. Python `amdsmi` imports, ROCm DKMS and kernel
driver changes are **not** required on the host.

The Debian package `mta-proxmox-gpu-agent_0.3.0-208.1_all.deb` requires
`amd-smi` and `acl` on the host. The tag synchronizer selects only LXCs with
**both** `mta-audio-editor` and `mta-gpu-agent`. For unprivileged containers
with no explicit `lxc.idmap`, it grants narrow host POSIX ACL access to the
standard mapped-root UID (100000), and provisions a read-only bind mount.
A custom `lxc.idmap`, missing ACL command or missing live agent socket causes
a manual-review result instead of a new mount. **Do not assume the standard
UID mapping is correct on hosts with customized Proxmox mapping settings.**
This shared token is diagnostic-only and can be used by other explicitly
authorized containers with the same mapped UID and mount access. Production
environments requiring per-container credential isolation should use distinct
per-container proxies/tokens instead.

A configured mount becomes effective only after the guest is restarted;
**the package never restarts the LXC**. The timer reapplies ephemeral ACLs
after service restarts. On host migration the package must be installed
on the destination, and the tagged mount may require a guest restart.
Verify on host with `systemctl status mta-gpu-agent.service` and
`python3 /usr/lib/mta-proxmox-gpu-agent/tag_sync.py`; verify inside the
LXC with the application's optional host-agent diagnostic endpoint.
The agent remains non-billable regardless of its availability.
