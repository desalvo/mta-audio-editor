## 0.3.0-r208 — Hardware snapshots and billing refinement

- Freeze advisory CPU/GPU hardware and suggested profile rates per AI job; report historical profiles without repricing on LXC migration.
- Preserve per-user billing opt-in, separate accounting telemetry from invoice tariffs, and update scheduled-closure regression coverage.
- Explicitly document Proxmox unprivileged guest security review and remaining hardware acceptance tests.

## 0.3.0-r207 — CI coverage refinement (11 October 2026)

- Added behavioral tests for authenticated AI gateway allowlisting, request limits, credential isolation, HTTPS/private upstream validation, response handling and audit on transport failures.
- Added isolated-model adapter tests for transcription/chords, DrumSep, SAM Audio, Demucs, singers and backing vocals without downloading GPU models, including output path containment and invalid options.
- Fixed `UnboundLocalError` in `singer-separation`: function-local `sys` imports in other branches hid the module import.
- Added administrator billing HTTP tests covering authorization, tariffs, reconciliation, invoice/schedule operations, CSV output and diagnostic-only GPU calibration endpoints.
- Keep CI `--cov-fail-under=70` unchanged. All 29 new focused tests pass locally, along with Ruff and CI Bandit checks. Full-suite aggregate coverage requires CI confirmation; do not claim certification from the focused run alone.

## r207 — Accounting and billing transaction finalization (pre-commit)

- Fix shared SQLite connection context to rollback on exceptions, not commit partial changes.
- Lock historical tariff modifications and persistent-storage sample insertion with BEGIN IMMEDIATE, coordinating with atomic billing closure.
- Add concurrent storage-versus-closure, rejected tariff revision, and rollback regression tests.
- Local verification: 195 r207-specific tests passed; Ruff clean; Bandit medium/high clean; pip check clean.
- Full pytest attempted but did not finish (stalled near 25%); CI, coverage certification, GPU benchmarks and native/hardware validation remain pending.

## Italiano — Chiusura transazioni accounting/billing r207

- Corretto il contesto SQLite: rollback su eccezione, evitando commit parziali.
- Serializzati aggiornamenti tariffe e campioni di storage persistente con BEGIN IMMEDIATE rispetto alla chiusura atomica.
- Aggiunti test di regressione per rollback, tariffe rifiutate e concorrenza campionamento/chiusura.
- Verifiche locali: 195 test r207 superati, Ruff, Bandit medio/alto e pip check superati.
- Suite completa non conclusa (arresto ~25%); CI, coverage e collaudi hardware/nativi ancora da eseguire.

## 0.3.0-r207 — Recovery and output-cache refinement (uncommitted cumulative)

- Add read-only replay after uncertain remote POST failures; preserve a single idempotency key and prohibit automatic second inference or local fallback.
- Extend remote result MIME validation to JSON alongside WAV/ZIP and expose JSON decoding to native routing.
- Add bounded, throttled expiration cleanup of optional cached AI outputs, with tests and bilingual deployment guidance.
- No version increment; software and hardware certification remain separately gated.

## 0.3.0-r207 — Native per-model remote inference (cumulative update)

- Verified all seven opt-in native AI inference families through their existing execution paths and added dedicated singer-separation regression tests.
- Preserved separate choices for multi-stage flows; remote failures do not trigger local AI inference.

## 0.3.0-r207 — Native per-model remote inference

- Added persistent opt-in local/remote routing for native Whisper, chords, Demucs, DrumSep, SAM Audio, singer separation and backing-vocal separation.
- Native project routes now validate ZIP/JSON/WAV AI results and use no implicit local fallback when remote mode is chosen.
- Added per-worker settings in the native application and dedicated regression coverage.
- Remaining: end-to-end native/real-model validation and per-job GPU runtime certification.

## 0.3.0-r207 — AI multi-artifact response protocol (uncommitted cumulative)

- Add validated ZIP output bundles for text/transcription and multi-stem AI workers while preserving legacy WAV responses.
- Add path traversal, symlink, duplicate filename, JSON/WAV and size validation; regression tests.
- The specialized native routes still require dedicated adapters and remote-mode wiring.

## 0.3.0-r207 — Central AI worker registry and authenticated WAV transport

- Introduced fixed per-model operator-configured worker registry and authenticated, bounded WAV upload for central metered AI jobs. Existing specialized AI routes and non-WAV/multi-stem output are not yet routed through this contract; see AI_UNIFIED_WORKERS.md.

- r207 pre-commit: atomic AI job completion guards against concurrent overwrites; concurrent multi-user billing tests; documented central-worker coverage gaps.
- r207 (uncommitted cumulative): GPU energy recorded for diagnostics only; billing charges verified GPU seconds, never joules, including when historic energy tariffs are present.
- r207: Add administrator-managed per-device idle/full-load GPU power calibrations and non-billable, job-scoped energy estimates with explicit exclusivity and lifecycle guards.
- r207 cumulative: add ACE-Step wizard `--benchmark` GPU capability test (AMD amdgpu_top / NVIDIA nvidia-smi), automatic test CLI generation, per-process DRM and NVIDIA process telemetry, JSON output and optional distro monitor-tool setup. Results are diagnostic, not certified per-job GPU energy billing.
- r207 GPU instrumentation: detailed job-cgroup-only DRM engine and VRAM/residency snapshots, deduplicated by client; explicitly diagnostic when process lifetime coverage is not assured.


- r207 billing hardening: each positively-priced GPU resource must have explicit per-job telemetry; user-supplied job kind cannot bypass GPU checks. An explicit measured zero remains valid. This does not implement a certified GPU meter.
- r207 cumulative: added optional per-job cgroup-scoped Linux DRM GPU engine diagnostics, without treating sampled counters as certified billing measurements.
- r207 cumulative: Reject CPU billing periods containing jobs without explicit per-job CPU telemetry when CPU tariffs are active.
### Uncommitted r207 — GPU telemetry provenance guard
- Reject GPU usage submitted as CPU/cgroup process measurements; require the dedicated GPU-agent source and an explicit GPU sample.
- Add regression coverage for GPU metering provenance; physical GPU telemetry remains unavailable without a per-process GPU sensor.

### r207 accounting corrections (uncommitted cumulative update)
- Exclude failed, unfinished and unmetered AI job usage from monetary summaries.
- Split persistent storage GiB-hour prices at UTC tariff effective timestamps, including intraday changes.
- Accept explicit timezone-aware tariff timestamps alongside existing dates.
- Add billing regression tests; preserve fail-closed GPU accounting policy.

### r207 (uncommitted) — GPU billing safety guard
- Reject billing GPU-capable jobs with only CPU/cgroup telemetry when GPU or energy rates are active; add regression tests.
- Do not infer job GPU load from global host GPU counters.

### r207 (uncommitted) — cgroup v2 worker accounting
- Add opt-in per-job delegated cgroup v2 CPU and disk I/O metering including all job descendants.
- Join the cgroup before worker exec, reject incomplete process trees, and exclude temporary I/O from storage charges.
- Keep GPU and energy unbilled without trusted per-job device telemetry; add regression tests.

### r207 (uncommitted) — Billing closure correctness
- Reject overlapping historical invoices and jobs spanning billing period boundaries.
- Refuse to invoice persistent storage without bracketing observations or where telemetry gaps exceed 26 hours.
- Add regression tests for overlapping periods, cross-boundary jobs and absent storage samples.
- Do not derive GPU charges from host-level utilization.

- r207 (uncommitted): add per-user scheduled UTC weekly/monthly/annual billing closures, immutable-rate protection, unfinished-job guard, CSV usage export, admin schedule controls and systemd billing timer.
## r207 — AI billing effective-dated tariffs (uncommitted cumulative update)
- Add `valid_from` and optional open-ended `valid_until` for each resource tariff, reject overlapping periods, and apply rate by job start time.
- Expose tariff validity through the admin API and web billing table; document invoice snapshot and measurement limitations.


AI gateway reverse proxy addition (r207 consolidated): HTTPS /api/ai-gateway endpoint support in native clients, example Kubernetes NGINX/HAProxy ingress and Docker HAProxy proxy, per-user token and usage administration guidance. No raw ACE-Step internet exposure.

## 0.3.0-r207
- Native ACE-Step local/remote selection with persisted HTTPS URL and private bearer credentials; prevent local auto-start in remote mode.
- Added native-only connection settings and first-use prompt, plus documentation and regression tests.

## 0.3.0-r207 — Remote ACE-Step HTTPS groundwork
Remote ACE-Step HTTPS endpoint allowlisting; MTA Linux wizard remote URL; remote AI setup documentation. Native full-AI offloading remains pending.

## 0.3.0-r206 — 2026-10-11

- Fix ACE-Step wizard version selection overwritten by /etc/os-release VERSION; retain existing VERSION= configuration compatibility.
- Add regression cases for distro VERSION and saved/CLI version precedence.

## 0.3.0-r205 — CI regression and coverage repairs

- Update ACE-Step wizard documentation test to renamed ACE_STEP_INSTALLATION.md.
- Add executable ACE-Step inference smoke protocol branch tests without GPU dependency, raising real application coverage.
- Align Android, iOS and Windows release metadata with revision 205.

## 0.3.0-r204 — Windows windowed startup crash fix

- Disable Uvicorn default logging configuration inside the native desktop launcher (`log_config=None`), preventing an `isatty()` exception when frozen Windows executables have no stdout/stderr streams.
- Add a no-console regression test and synchronize release metadata across desktop and mobile platforms.

## 0.3.0-r203
- Introduced standalone MTA web installer wizard for Debian/RHEL-family hosts, VMs and LXC.
- Documented install, web access, reconfiguration, and uninstall.

## 0.3.0-r202

- Self-contained ACE-Step installer, documented as a single-file download with explicit uninstall and optional confirmed data purge.
- Rename general wizard guide and link it in Italian/English READMEs.
- Align Android, iOS, Windows build metadata and fix dry-run OS detection under unprivileged CI.

## 0.3.0-r201
Rename the ACE-Step installer to executable `scripts/install_ace_step.sh`; document Linux bare-metal, VM and LXC usage, retaining device validation and idempotent configuration.

## 0.3.0-r200
- Consolidate fresh install, reconfiguration, upgrade and forced reinstall into one idempotent ACE-Step LXC wizard.
- Persist ACE-Step version, TCP port, bind mode and firewall preference, and propose saved settings on rerun.
- Offer network firewall configuration while keeping localhost/8001 as secure defaults.
- Remove obsolete standalone ACE-Step reinstall script.

r199: ACE-Step LXC wizard supports Debian-family and RHEL-family >=9 with early OS rejection and apt/dnf routing.

## 0.3.0-r197 — Rocky Linux LXC ACE-Step reinstall

- Add safe, auditable ACE-Step source reinstallation and systemd service for Radeon 8060S ROCm LXC. Preserve persistent checkpoints and projects.
- Record real upstream inference evidence and limitations of MTA integration.

## 0.3.0-r196 (2026-10-11)
- Fix 18 Ruff findings from CI including unused imports, production assert, and validated HTTP request destinations.
- Add a dedicated pinned ACE-Step runtime-image GitHub Actions workflow; configure container deployments for the pinned image, persistent model caches, and authenticated remote MTA API.
- Confirm the real GPU image build and model inference remain pending execution on supported hardware.

## 0.3.0-r196 — pinned ACE-Step runtime CI

- Added separate GitHub Actions workflow to build and publish a CUDA ACE-Step service image from the audited upstream commit, excluding model weights.
- Docker Compose requires an explicitly chosen immutable image tag instead of mutable upstream `latest`; on-demand model caches remain persistent.
- Added optional NVIDIA GPU Compose override and deployment documentation; real inference and native runtime packaging not yet validated.

## 0.3.0-r195 — Reviewed ACE-Step CI source bundling

Adds ACE-Step source vendoring from a verified stable release (`v0.1.8` default), immutable SHA resolution, a weekly update-proposal pull request, source integrity and license validation, deterministic bundles and SHA256 artifacts, and regression tests. Does not yet package a ready-to-run inference runtime or validate generation.

### 0.3.0-r194 — Shared model cache telemetry and reproducible source bundling
- Add authenticated model-cache telemetry to MTA for remote clients, without exposing checkpoint files or internal model API.
- Mount cached models read-only in MTA service, with persistent ACE-Step cache in Docker/Kubernetes.
- Provide opt-in pinned upstream source vendor script (source not embedded in this build because upstream retrieval was unavailable).
- Keep native C++/VST3 experimental, no real inference certified.

### 0.3.0-r193 — ACE-Step native setup progress
- Native setup shows a polling progress bar for Git clone, dependency installation and first model initialization, reporting model cache growth without invented percentages.
- Native lifecycle remains opt-in and stops only the MTA-owned server.
- Added progress regression coverage.

## 0.3.0-r193 — Native ACE-Step guided installation and one-click live inference test

- Native-only opt-in Git/uv source deployment in a private data folder, model cache, local API start.
- UI Install / Start / Test / Refresh buttons with background installation and live audio inference.
- Fail closed for multi-user deployments and missing prerequisites; no verified production model inference yet.
- Trusted internal Python ACE-Step adapter works as a subprocess across platforms.
- C++ VST3 host status unchanged (`native_host_ready=false`).

- Native single-user ACE-Step server now auto-starts with MTA after recorded download consent; it is terminated on MTA shutdown. Manual Stop disables later auto-start and never kills an unrelated server.

## 0.3.0-r192 — Opt-in live ACE-Step inference smoke test

- Added a real audio-generation smoke test requiring an installed ACE-Step worker and explicitly returning unverified when unavailable.
- Added `--smoke-input` to the ACE-Step HTTP worker to exercise upload, task polling and audio retrieval from an independently provided WAV.
- Preserved track/master routing, nondestructive generated-track import, and native DSP/VST3 experimental status; no model weights bundled.
- The smoke check does not guarantee musical fidelity; production inference and VST3 realtime remain unverified.

## 0.3.0-r191 — ACE-Step transport integrity and native latency tests

- Strict no-proxy loopback HTTP transport and JSON health response validation.
- End-to-end mock HTTP ACE-Step Cover pipeline coverage; this does not prove actual model inference.
- Additional compiled C++ latency compensation regression tests.
- Preserve cumulative track/master routing and non-destructive import.

## 0.3.0-r190

- Added explicit non-overclaiming ACE-Step backend readiness diagnostics and native C++ non-allocating noise gate.
- Inference readiness remains unverified until an actual generation completes on a model-backed server.

## 0.3.0-r189
- Deploy ACE-Step alongside MTA in Docker Compose/Kubernetes with persistent on-demand model storage and private API routing.
- Add desktop local ACE-Step launcher requiring operator-installed upstream executable and explicit download consent.
- Restrict trusted Docker sidecar endpoint with explicit environment allowlist.
- Preserve non-destructive Arranger/Remix and experimental native audio/VST3 components.

## 0.3.0-r188
- Add preallocated, nonallocating C++20 DC offset filter and standalone tests.
- Validate actual WAV bytes returned by ACE-Step before publishing results; prevent truncated or invalid audio.
- Add explicit loopback server probe separate from inference readiness; preserve non-destructive track/master generation.
- Add regression tests for invalid ACE-Step outputs and cross-platform release version.

## 0.3.0-r187

- Added optional ACE-Step 1.5 HTTP worker adapter using local API audio-conditioned cover generation, task polling and verified WAV output via existing MTA worker contract. No models bundled and not certified without live inference.
- Kept track/master source routing, non-destructive result insertion, VST3 latency-compensated native DSP foundations and native_host_ready=false.
- Added adapter protocol tests and setup documentation.

## 0.3.0-r186

- Guard AI worker output duration relative to the selected track or rendered Master Out; preserve fail-closed audio validation and non-destructive track import.
- Reject source audio exceeding 30 minutes and prevent worker plan from overriding server-generated source manifest.
- Introduce native C++20 planar/interleaved PCM conversion for the future VST3 audio-buffer bridge, with allocation-free processing and atomic invalid-sample rejection.
- Align Windows, Android and iOS build revision metadata.
- AI model inference and realtime native hosting are not yet production validated; native_host_ready=false.

## 0.3.0-r185

- AI Arranger/Remix generated WAV outputs are appended as new project tracks with independent files and non-destructive source retention; generate-and-add endpoints and editor control added.


- AI Arranger/Remix input source selector: exact rendered Master Out (mute, solo, track/master inserts, faders and pan) or an isolated rendered track with inserts.
- Track context menu starts AI Arranger/Remix with that track selected.
- Worker manifest explicitly identifies master vs track audio.
- No built-in AI model inference yet; native_host_ready remains false.

## 0.3.0-r184

- Stage project-owned WAV audio sources for external AI workers with temporary isolated input paths.
- Validate input audio and fail closed on unsafe or unsupported sources.
- Pass the source manifest to the selected worker for AI Arranger and Remix generation routes.
- Add an allocation-free C++20 dry/wet crossfade primitive for future A/B preview playback.
- Keep native playback readiness disabled pending VST3 realtime validation.

- r181: external AI preview generation routes with explicit trusted worker opt-in; native stateless C++ soft-clip DSP.

## 0.3.0-r180 — External worker contract and native PDC mix (development)

- Added explicit opt-in external inference worker protocol, size-limited JSON plans and validated WAV results. No ACE-Step inference is bundled or operational by default.
- Added experimental preallocated C++20 multiroute PDC mixer with gain/mute for offline testing; realtime production remains disabled.
- Added regression tests and synchronized platform release metadata.

## 0.3.0-r179 (uncommitted)

- AI Arranger / Remix authenticated preflight diagnostics for missing chord and section context; no fake inference readiness.
- Native C++20 sample-accurate block gain ramp for click-free mixer automation, with fail-before-write input validation.
- Preserve all r176-r178 changes and native_host_ready=false until production realtime integration.

## 0.3.0-r178 — AI job isolation and compiled native mixer foundation

- Deep-copy AI plans on submit/read/cancel, preventing user and callback mutation of queued constraints.
- New compiled C++20 native mix matrix: multi-route PCM sum, gain, mute, nonfinite protection and no allocations in callback.
- All r177 AI job endpoints and VST3 delay-compensation DSP retained.
- AI inference remains unavailable without a validated worker; native engine is not connected to realtime production (`native_host_ready=false`).

## 0.3.0-r177 — AI job lifecycle and compiled PDC multi-route processing

- Added bounded authenticated non-destructive AI job planning endpoints with cancellation and ownership isolation. No inference is claimed or started.
- Added C++20 preallocated, realtime-allocation-free multiroute PDC processor with disabled-route handling and fail-closed nonfinite checks.
- Added compiled regression coverage; preserved `native_host_ready=false`.
- No automatic third-party model downloads, no change to .maeproj/.maeprojz semantics.

## 0.3.0-r176
- Expose authenticated AI Arranger and Remix planning endpoints; generation explicitly fail-closed.
- Expose native C++20 VST3 latency alignment planner through a stable C ABI.
- Synchronize release metadata across platforms.

## 0.3.0-r175 — Remix planning foundation

- Add Remix with instrument replacement and user-described auto-remix, reusing optional preservation of structure, chords, tempo, melody, and vocals.
- Validate track identities, replacement targets and requests; no artificial or destructive audio output.
- Keep AI generation disabled until real, licensed backends are integrated.

## 0.3.0-r173

- Fixed Windows executable metadata revision mismatch that caused CI test_r65_release_safety to fail.
- Synchronized build identity with Android/iOS native package revisions.
- Added automated regression checks for consistent version identity.

## 0.3.0-r172 — Restore independent numeric build identity

- Restore a strict 14-digit Europe/Rome build timestamp in `BUILD_INFO`, separate from `VERSION`, `REVISION` and `RELEASE`.
- Preserve cumulative functionality and experimental native VST3 safety (`native_host_ready=false`).
- Validate release identity in CI before the full Python test suite.
- Add a bounded C++20 per-route plugin/IPC latency alignment planner (up to 64 routes, with overflow rejection), compiled regression-tested; experimental control plane only, not connected to production callbacks.

## 0.3.0-r171 — Quality / Ruff fixes

- Fix six Ruff violations detected by CI on r170, with diagnostic logging for VST3 worker cleanup failures.
- Preserve VST3 fault isolation and all previous functionality; no native host readiness change.

## 0.3.0-r170 — Safe concurrent rendered playback previews

- Serialize duplicate preview renders and atomically publish only valid WAV outputs; incomplete results never enter the playback cache.
- Include enabled insert settings in playback URL identity to prevent stale browser FX preview reuse.
- Retain experimental native host status (`native_host_ready=false`); browser/WebAudio playback remains separate from native VST3 realtime hosting.

## 0.3.0-r169 — atomic VST3 offline render chain

- Preflight every VST3 insert before processing a track.
- Keep all intermediate plugin outputs outside the destination path and atomically publish only a complete successful output.
- Detect worker timeouts and missing/empty audio output with contextual errors.
- Preserve earlier exports on failed plugin processing.
- Experimental realtime host remains disabled (`native_host_ready=false`).

## 0.3.0-r168 — Project-scoped VST3 snapshot storage

- Persist bounded component/controller snapshots for a specific track or master insert, bound to its VST3 module identity.
- Preserve snapshots in portable project archives and reject oversized/malformed snapshot members on import.
- Prune snapshots for deleted inserts via explicit control-thread cleanup; no realtime I/O.
- Experimental API; not yet automatically connected to production playback or save hooks. `native_host_ready=false`.

## 0.3.0-r166 — persistent control-thread VST3 snapshots

- Add portable plugin-identity-bound component/controller checkpoint envelopes with SHA-256 integrity checking.
- Atomically save state pairs with bounded decoding and private temporary files.
- Add supervisor checkpoint import/export for restoring state across application sessions.
- Recovery and snapshot APIs are control-thread-only; `native_host_ready=false` remains unchanged.

## 0.3.0-r165 — Atomic optional VST3 component/controller supervisor checkpoints

Support joint component and optional controller snapshots with failure-atomic checkpoint replacement, correct restore ordering, and unsupported-controller handling. Experimental worker-thread only; `native_host_ready=false`.

## 0.3.0-r164 — Independent controller state IPC (experimental)

Separate 1 MiB-bounded opt-in controller `getState`/`setState` on the isolated VST3 worker, separate from component state. Controller support is plugin-dependent. Never invoke state operations in realtime callbacks; `native_host_ready=false`.

## 0.3.0-r163 — VST3 processor state IPC (experimental)

Bounded SDK getState/setState transport via the opt-in stream-events protocol, Python snapshot/restore operations, and fail-closed IPC handling. This is off-callback only; native_host_ready=false.

## 0.3.0-r162 — isolated worker PCM fault containment

Reject nonnumeric, boolean, nonfinite and out-of-range returned PCM from external adapters and IPC. No VST3 state getState/setState yet; native_host_ready=false.

## 0.3.0-r161 — IPC fault containment

The single-quantum persistent IPC path now force-closes an untrustworthy subprocess on transport failure; it cannot silently carry a damaged protocol frame into the next block. Native host activation remains disabled. This does not implement getState/setState.

## 0.3.0-r160 — supervised VST3 worker state initialization

- Add optional `restore_state` control-thread hook invoked for every newly created IPC worker, before processing audio.
- Fail closed on restore errors: discard worker, return dry and enforce the configured restart budget; add restoration diagnostics.
- Cover first start, fault recovery and seek/reset with focused tests. This is a state-rehydration hook only, **not** Steinberg `getState`/`setState` serialization.
- Retain all cumulative r153–r159 changes and keep `native_host_ready=false`.

## 0.3.0-r159 — IPC worker fault containment

- Contain unexpected third-party processor exceptions without replaying partially processed PCM.
- Reject malformed event-batch responses (wrong count, container type, sample count or non-finite samples), close invalid worker and recover only on a new quantum.
- Keep `native_host_ready=false`; production callback and native plugin state restore remain unverified.

## 0.3.0-r158 — isolated VST3 fault recovery and seek barrier

- Add bounded, configurable recovery spacing after VST3 IPC faults; emit dry for each skipped block without replay.
- Add a control-thread-only reset_session seek barrier to close stale plugin state and start a new epoch at the next quantum.
- Track reset/deferred-block counts and test fault/seek lifecycle. `native_host_ready=false` remains mandatory.

## 0.3.0-r157 — VST3 rejected worker cleanup

- Close any newly opened plugin worker whose channel or event configuration fails recovery validation, preventing orphan VST3 subprocesses across restart cycles.
- Add regression tests for incompatible workers and cleanup failures; native_host_ready remains false.

## 0.3.0-r156 — track Delay UI deduplication (`native_host_ready=false`)

Remove duplicate Delay input rendered inside every track header and duplicate JavaScript delay control functions and CSS declarations. Retain one working per-track delay and existing delay effect processing, with a regression test against recurrence. No production VST3 host activation.

## 0.3.0-r155 — bounded supervised VST3 IPC recovery (`native_host_ready=false`)

Added control-thread-only supervisor for persistent event-enabled VST3 IPC sessions. No automatic replay after partial DSP failure, bounded restarts, epoch tracking, dry fallback, strict PCM/event preflight and test coverage. This does not integrate with the production playback callback; plugin state after a crash is lost, and host activation remains disabled.

## 0.3.0-r154 — bounded event batch preflight (native_host_ready=false)

Stateful persistent VST3 IPC now supports bounded batch requests (up to 128 blocks and 65536 frames), validates every MIDI/automation event and PCM quantum prior to sending any IPC data, and retains original legacy single-block support. DSP rollback after plugin failure is not guaranteed; production playback remains disabled.


### 0.3.0-r153 — Experimental VST3 event IPC (native host remains disabled)
Persistent offline VST3 IPC optionally accepts bounded MIDI note-on/off and normalized parameter changes per PCM block, with sample offsets. The legacy PCM stream is unchanged. Events are validated and mapped into Steinberg EventList/ParameterChanges on the isolated worker process. This is not an enabled realtime host.

## 0.3.0-r152 — safe event/audio dispatch

Reject exact-sequence event packets with mismatched audio frame counts and fail closed on bounded stale-event scan exhaustion. Preserve the r121–r151 cumulative work. `native_host_ready=false`; live SDK and playback integration still pending.

## r151 — Experimental PCM/event worker synchronization

Worker-side `Vst3EventAudioPump` pairs native PCM blocks and bounded MIDI/automation event packets using epoch, sequence and frame count. Empty event blocks remain playable, failed delivery fails closed, and non-finite processor output is rejected. This is a test-only bridge: no Steinberg SDK MIDI queue or production playback connection is claimed; `native_host_ready=false`.

## r141–r150 — Bounded worker event dispatch (experimental)

Added `native/audio_core/vst3_event_dispatch.hpp`: epoch/sequence gating, bounded MIDI and parameter dispatch, atomic prevalidation, preserved sample offsets, failure counters, lifecycle reset, and deterministic sequence consumption. The worker adapter is not yet wired to Steinberg SDK processing or production playback. `native_host_ready=false`.

## 0.3.0-r140 — five native functional cycles (r136–r140)

- r136: worker processor exceptions contained; no worker-thread termination from plugin adapter exceptions.
- r137: reject non-finite worker PCM before returning a processed block.
- r138: add allocation-free bounded SPSC transport for prepared MIDI and automation event packets.
- r139: detect and discard stale transport epochs; preserve future events with bounded scans.
- r140: stress test 20,000 event packets across producer and consumer threads and dry fallback.

**Experimental only:** events are NOT yet mapped to Steinberg SDK VST3 event/parameter queues; playback integration and multiplaform stress are pending; `native_host_ready=false`.

## 0.3.0-r129 — Native PCM latency alignment reference (experimental)

- Implement preallocated C++ frame-accurate PCM delay-line supporting mono/stereo, irregular block sizes, in-place processing and reset on seek.
- Add C++20 regression tests for delay alignment and invalid sample rejection.
- This is an isolated reference component: it is not yet wired into live playback and does not account for reported VST3 plugin latency dynamically.
- `native_host_ready=false` remains mandatory until end-to-end playback, MIDI/automation and all platform tests pass.

## 0.3.0-r128 — worker stability hardening (experimental)

- Clear worker output buffers before every processing call to avoid stale PCM leaking from incomplete writers.
- Add deterministic native stress tests for failure, restart isolation, underruns and repeated lifecycle.
- native_host_ready remains false; production host integration and platform validation are still required.


## 0.3.0-r128 — Native public C ABI and exact-quantum enforcement

- Added `native/audio_core/vst3_runtime_api.h`, a usable C/C++ v2 ABI including thread-affinity and lifetime contracts.
- Native playout rejects mismatched negotiated frame/channel quantum, zeroing the caller-sized output when safe.
- Regression coverage for C clients, C++ ABI, mismatch and lifecycle.
- VST3 playback in the production engine and full native host readiness remain disabled.

## 0.3.0-r126

- Add native ABI v2 configuration query and callback-thread-only diagnostic counters.
- Keep experimental VST3 host disabled pending production integration and cross-platform validation.

## 0.3.0-r125 — Native PCM input validation and stopped-runtime isolation

- Reject non-finite PCM on native callback before queuing; clear output deterministically.
- Do not playout stale queued results from faulted/stopped/unstarted runtime; return explicit native API error and silence.
- Compiled C++20 regression tests for input validation and native API lifecycle.
- Experimental only: `native_host_ready=false`; full playback integration, latency compensation, MIDI automation, and multiplatform stress tests remain unverified.

## 0.3.0-r124 — Bounded callback result polling

- Hard limit of eight result-queue pops per callback to protect the deadline from stale IPC responses.
- Expose poll-budget exhaustion in native playout diagnostics; compiled C++ regression.
- Experimental only: `native_host_ready=false`, no production callback integration.

## 0.3.0-r123 — Native runtime diagnostic ABI

- Add ABI version and stopped-only worker statistics on C API.
- Add compiled C++ integration tests for worker diagnostics; readiness remains false.

## 0.3.0-r122 — real ADelay IPC behind native C bridge

- Test-only native C ABI connects native callback-side PCM queue to a dedicated Python worker and persistent Steinberg VST3 subprocess.
- Real ADelay test validates both mono and stereo with 180 blocks and nonzero audio, and is added to SDK CI.
- Includes all r121 changes; `native_host_ready=false`, production playback remains untouched.

## 0.3.0-r121 — experimental native C ABI for PCM bridge

- Exported opaque-handle native runtime API for create/start/process/stop/destroy and a disabled readiness probe.
- Native callback only exchanges PCM with bounded queues; processor runs exclusively on its worker thread.
- Added compiled C++20/ctypes lifecycle, validation and dry-playout smoke tests.
- Actual Steinberg VST3 subprocess not connected to this C ABI or the DAW playback. `native_host_ready=false` remains mandatory.

## 0.3.0-r120 — cumulative r101–r120 native readiness gate

This release includes every uncommitted change from r65 through r100. Twenty distinct control-plane validations (quantum, channel shape, sample rate, queue sizing, lookahead, worker scheduling, quiescence, IPC handshake/version, plugin lifecycle, processing, latency, crash recovery, MIDI, automation, platforms and realtime stress) are explicitly checked in native C++ and exercised by parameterized compiled tests. Existing worker runtime now refuses an unsafe restart that could replay stale queue data. **These are acceptance checks, not proof they are all satisfied by MTA's production engine.** The actual realtime host remains disabled: `native_host_ready=false`. End-to-end IPC binding to the native callback, measured latency compensation and multi-platform tests remain open. No claim of production readiness.

## 0.3.0-r100 — native worker runtime (r88–r100)

Cumulative changes since r65 including r87. Thirteen native worker engineering increments: bounded worker configuration, lifecycle states, processor ownership, control-thread start/join, callback/IPC separation, fault latch, scheduling fairness, worker-thread backoff, fault diagnostics, immutable quantum, watchdog integration point, stop statistics and disabled readiness gate. This is an experimental control-plane worker runtime, NOT an end-to-end VST3 realtime host. `native_host_ready` remains `false`.

## 0.3.0-r87 — native VST3 realtime readiness contracts (r78–r87)

Ten cumulative engineering iterations: negotiated playback quantum, transport epoch tokens, frame deadlines, latency budgets, bounded bypass ramps, parameter automation packets, MIDI event packets, worker fault circuit breaker, PCM sanitization, and readiness guard. All are experimental worker/control-plane building blocks; none enable the realtime host. `native_host_ready` stays `false`.

## 0.3.0-r77 — native worker pump and playout shape safety

- Introduced a bounded worker-only processor adapter with finite-output validation and dry bypass on failure.
- Fixed native callback handling of irregular frame counts: delayed output is accepted only for matching shapes; shape mismatch becomes silence instead of a buffer overflow.
- Preserved all cumulative changes through r76; native_host_ready remains false.

## 0.3.0-r76 — native audio playout boundary (experimental)

- Add `Vst3PlayoutBridge`: bounded native SPSC input/output queues and preallocated dry lookahead.
- Callback-facing `callback()` performs no IPC, waits, heap allocations or VST3 calls; worker-facing take/return remain separate.
- Deterministic late block discard and dry bypass with diagnostic counters.
- Add compiled C++20 tests for audio order, delayed wet output and missing blocks. Readiness remains false.

## 0.3.0-r75 — native PCM block queue (experimental)

- Added fixed-capacity C++20 SPSC block exchange retaining sequence, channel count and exact frame count.
- All memory allocated at initialization; push/pop perform bounded copies without locks, I/O or allocation.
- Added compiled C++ concurrency and overflow regression tests. No audio callback wiring yet; readiness stays false.

## 0.3.0-r74 — bounded VST3 IPC playout scheduling

Experimental application-thread playout coordinator with explicit block-period lookahead, deterministic dry bypass, late-result discard, bounded backpressure and metrics, seek/stop dry flush. Not suitable for hard realtime callbacks; native_host_ready remains false. Includes all uncommitted r65–r73 revisions.

## 0.3.0-r73 — latency planning and dry-path reference alignment

Adds explicit sample-rate-aware IPC lookahead + plugin delay accounting, bounded PCM delay-line reference, and tests for stereo/mono alignment across irregular blocks. This is an offline reference only; realtime safety and native_host_ready=true remain blocked. Includes r65–r72 cumulatively.

## 0.3.0-r72 — experimental ordered asynchronous VST3 delivery

Adds bounded, application-thread-only block coordinator with ordered processed results, stale-result discard, deterministic dry bypass on late/error output, and regression tests. This is NOT an audio callback integration and native_host_ready remains false. Includes all changes since r65.

## 0.3.0-r71 (includes unpublished r65–r70)

- Experimental bounded asynchronous VST3 IPC bridge (`native/vst3_probe/async_bridge.py`): nonwaiting enqueue/poll, ordered results, backpressure, fault latching and explicit shutdown.
- Python bridge is NOT hard realtime safe: Python locks, allocations, queue operations and scheduling are forbidden in the audio callback.
- Realtime host readiness remains false; latency alignment, bypass recovery, MIDI/state and multiplatform validation still missing.

## 0.3.0-r70 (cumulative, unpublished r65 and r66 included)

- r67: Add real Steinberg ADelay acceptance for bounded multi-request VST3 sessions, including uneven request lengths and sample-rate/channel coverage in GitHub Actions.
- r68: Add an experimental interactive C++ `--stream-pcm` worker accepting bounded little-endian Float32 PCM frames through stdin/stdout without reinitializing the plug-in.
- r69: Add a Python watchdog-controlled persistent worker with timeout, process-crash handling, response validation, and deterministic shutdown; asynchronous worker I/O is off the audio thread.
- r70: Add atomic, bounded-memory, long-duration WAV PCM16/24/32 render through live VST3 insert workers and real ADelay IPC parity acceptance on Linux CI.
- Keep `native_host_ready=false` and realtime routing disabled; more platform, callback, latency, and crash-recovery work is required before enabling native host.

## 0.3.0-r67

- Added real-Steinberg-SDK ADelay multi-request session acceptance to Linux CI: mono/stereo, 44.1/48/96 kHz, irregular frame boundaries, continuity against unsegmented rendering and a two-insert chain.
- Documented explicit blocking requirements before native VST3 host activation; readiness remains false.
- Includes all unpublished r65/r66 improvements; no intermediate commit is necessary.

## 0.3.0-r66
- Added bounded, state-continuous multi-block VST3 WAV export via offline session chains.
- Preserves PCM16/24/32, mono/stereo, 44.1/48/96 kHz, with atomic output protection.
- Native realtime readiness remains disabled; this path is offline-only.

## 0.3.0-r65 — Offline VST3 session transport hardening (r61–r65 cumulative)

- r61: transport sample positions use the actual processed frames rather than fixed 512-frame strides.
- r62: compare consecutive blocks using previous actual frame length; PPQ follows the real sample clock.
- r63: proactively refuse session requests larger than the remaining frame budget before materializing them.
- r64: reject non-sequence and bytes/string PCM containers; keep native process isolation.
- r65: add odd-sized mono/stereo and input-security regressions, package/revision updates.

Limitations: This is still a bounded offline multi-request subprocess. Interactive IPC and hard realtime guarantees are not implemented; native_host_ready remains false. Existing startup/process-per-session limitation persists.

## 0.3.0-r60 — Native VST3 multi-request offline session (r51–r60 cumulative)

- R51–R52: bounded binary MTASPCM1 session envelope and C++ parser, with up to 128 PCM requests.
- R53–R54: one native VST3 initialization and activation processes successive requests in order, maintaining processing state and continuous musical transport within a session.
- R55: reject truncated payloads, invalid frame counts, unsupported channel counts and sample rates, oversized input, invalid or non-finite PCM.
- R56: separate per-request output frames while keeping the original single-request rendering interface.
- R57: Python adapter handles timeout, exit failures, missing output, invalid envelopes, mismatched dimensions and NaN/Inf.
- R58: optional serial session chain supports up to eight inserts, with per-plugin process isolation.
- R59: protocol, bounds, stereo, malformed responses, and chain regression tests.
- R60: version, cross-platform build metadata and bilingual documentation updated. One release package for all ten increments.

**Scope and limitations:** This implements **multi-request processing in a single offline subprocess session**. It does not yet implement a long-lived interactive daemon or shared-memory realtime IPC, and it does not enable the VST3 host on the realtime audio thread (`native_host_ready=false`). Sessions still have a cumulative limit of 1,048,576 frames, not unlimited WAV streaming. MIDI/event timing and per-job automation are diagnostic-only, not a production sequencer. All external third-party plugins run in an isolated subprocess.

Example API: `render_native_session([[0.0] * 512, [0.25] * 256], (plugin_path, cid), probe_binary)`.

## 0.3.0-r50 — VST3 multi-rate regression CI fixes

- Update r21 and r27 regression tests to assert the dynamic `pcmSampleRate` used by the C++ probe for processing configuration and musical transport; retain the supported 44.1/48/96 kHz behavior.
- Preserve the 70% coverage threshold and all r49 VST3 batch features.

## 0.3.0-r49 — five-iteration development batch

- r45: Fix Ruff F401 unused run_batch import in sample-rate tests.
- r46: Detect hard-linked output/input aliasing in batch preflight.
- r47: Add configurable cumulative frame budget for atomic and dry-run batches.
- r48: Add an atomic JSON report file for batch CLI results.
- r49: Expand regression coverage and align release metadata.

Realtime VST3 hosting remains disabled; native persistent worker not yet implemented.

## 0.3.0-r44 (three integrated internal iterations: r42–r44)

- r42: Consolidated batch input/output preflight for atomic publishing.
- r43: Experimental `--atomic-batch` stages every WAV before touching destinations, with same-filesystem backups and best-effort rollback of replaced files.
- r44: Added regression tests for staging failures and rollback. Real-time playback remains unchanged; native persistent worker remains pending.

## 0.3.0-r41 — configurable VST3 offline sample rates
- Add 44.1 kHz, 48 kHz, and 96 kHz support to the isolated native PCM renderer and WAV export.
- Propagate the requested rate to VST3 setupProcessing and ProcessContext, including musical transport timestamps and test stimulus.
- Preserve source sample rate and PCM bit depth in the output WAV; validate unsupported rates before launching the probe.
- Keep the plugin isolated and the realtime engine disabled; a persistent C++ worker is not yet implemented.

## 0.3.0-r40 — VST3 batch WAV preflight
- Add `--dry-run` to the isolated VST3 WAV batch CLI, validating all source WAV formats, sizes, directory targets and collisions before launching plugins.
- Produce machine-readable `ready` reports with bit depth, channel count and frame count; do not create or overwrite outputs during preflight.
- Add functional tests for normal batch rendering, invalid sample rates, missing output directories and CLI behavior.
- Native VST3 worker persistence and realtime audio activation remain explicitly unsupported.


## 0.3.0-r39 — GitHub Actions regressions and VST3 host tests
- Replace obsolete 128-block-only source assertions with checks for the variable-length PCM path and fixed 128-block diagnostic fallback.
- Add functional, mocked tests of VST3 discovery, parameter validation, CLI error handling, and optional dependency failure to increase real application coverage without relaxing the 70% gate.
- Keep the experimental VST3 host isolated from the realtime playback engine.

## 0.3.0-r38 — Safe batch VST3 offline WAV rendering
- Added experimental manifest-driven batch CLI (`python -m native.vst3_probe.batch_wav_cli`) for up to 128 WAV exports.
- Validates all outputs, collisions, CIDs and limits before executing any plugin.
- Reports per-job outcomes in JSON and optionally stops at first error; each output remains atomically published.
- Does not claim a persistent native VST3 process; realtime remains disabled.

## 0.3.0-r37 — VST3 WAV CLI and input validation
- Added opt-in WAV CLI for native isolated insert chains with machine-readable JSON results.
- Reject invalid timeouts and empty chains before launching plugins; preserve atomic exports.

## 0.3.0-r36 — Ruff CI fix and high-resolution offline VST3 WAV export

- Fix unused `Path` import in `tests/test_r35_native_wav.py`, the GitHub Actions Ruff F401 failure.
- Extend isolated WAV export to signed PCM24 and PCM32 while retaining PCM16, mono and stereo.
- Preserve source bit depth, sample rate, channel count and frame count; reject unsupported formats.
- Add explicit saturated output quantization, NaN/Inf and frame-count guards, preserving atomic publication on failures.
- Add PCM16/24/32 identity, clipping, malformed output and no-overwrite regression tests.
- This path remains offline-only, bounded and opt-in; realtime host remains disabled.

## 0.3.0-r35 — GitHub Actions correction and isolated WAV renderer

- Remove the unused MAX_FRAMES import that caused Ruff F401 in the latest workflow logs.
- Add opt-in offline WAV-to-WAV processing backed by the existing native isolated VST3 PCM chain.
- Support 48 kHz, 16-bit PCM, mono/stereo WAV up to 1,048,576 frames with exact frame preservation.
- Publish outputs atomically; leave existing exports intact when plugin processing fails.
- Add conversion, unsupported-format, partial-frame, and failed-export regression tests.
- No realtime activation; SDK remains an external MIT-licensed dependency.

## 0.3.0-r34 — GitHub Actions Ruff correction

- Resolve unused-import F401 in the native VST3 PCM chain and its regression tests.
- Preserve r33 variable-length stereo VST3 processing and previous track-renaming fixes.
- Synchronize desktop and mobile revision metadata.

## 0.3.0-r33
- Native SDK VST3 offline PCM rendering now accepts bounded variable-length mono/stereo float32 interleaved buffers (up to 1048576 frames), with the same plugin instance across processing blocks.
- Strict PCM frame/channel validation and partial final-block handling. No realtime use.

## 0.3.0-r32
- Added opt-in real VST3 mono float32 offline PCM transport, 65536-frame subprocess processing, and bounded multi-plugin serial adapter.
- No realtime integration: plugin process isolation per insert; MIDI, stereo and latency-compensated native chains not yet supported.

## 0.3.0-r31
- Added fail-closed offline insert graph executor with sequential DSP blocks, sample-offset event dispatch, latency flush, bounded tails, finite-output validation, and deterministic chain tests.
- Fixed stale Windows version resource metadata. Production realtime VST3 host remains disabled.

## 0.3.0-r30
- Add bounded VST3 offline graph helpers for latency compensation, parallel stem alignment, stable mixing bounded tail budgeting, and sample-accurate offline MIDI/parameter event batching.
- Add deterministic regression coverage for impulse alignment, corrupted/nonfinite audio, and timing limits.
- Preserve the isolated VST3 probe; realtime integration remains gated.

## 0.3.0-r29
- Fix immediate track rename propagation across Tracks and Mixer without rebuilding the DAW UI.
- Wire mixer name editor Enter/Escape/blur to commit/cancel and prevent duplicate generic handlers.
- Keep track-name saves asynchronous and debounced.

## 0.3.0-r28 — offline VST3 event/parameter queues and latency metadata

- Allocated Steinberg SDK event and parameter queues outside the offline processing loop.
- Added opt-in note-on/note-off smoke events only when an event input bus exists, and one bounded parameter point when a writable controller parameter is available.
- Captured processor-reported latency and tail in the offline diagnostic result; **latency compensation is not yet implemented**.
- SDK helper implementations are compiled only when a complete external MIT-licensed SDK is configured.
- The diagnostic path remains separate from production playback. **Not realtime-ready**: callbacks, event queue allocation audit, compensation, plugin crash isolation, full cross-platform CI and audio fixture testing remain.

## 0.3.0-r27 — isolated VST3 musical transport context

- Added a valid Steinberg ProcessContext during all 128 offline audio blocks, with 48 kHz, 120 BPM, 4/4, sample-accurate project position and continuous musical time. The context is confined to the diagnostic process and does not modify playback.
- Added bounded Python validation of reported transport continuity and last project sample.
- Added regressions for monotonic transport and mobile revision consistency.
- **NOT realtime ready:** MIDI event queues, sample-accurate parameter automation, delay compensation, fault isolation and realtime allocation audits are still required. No production host switch has been enabled.

## 0.3.0-r26 — extended offline signal validation

Expanded the isolated VST3 diagnostic to 128 consecutive 512-sample blocks at 48 kHz to exercise the one-second default Steinberg ADelay effect. Reports output energy and a derived non-silent flag. No realtime readiness claim: MIDI, parameter automation, latency alignment, bounded RT callbacks and platform validation remain outstanding.

## 0.3.0-r25

Isolated VST3 probe: 16-block 440 Hz deterministic signal processing; per-block buffer clearing, bounded output energy and non-finite diagnostics. This remains experimental; no realtime integration or validated MIDI/automation/latency compensation.

## 0.3.0-r24

- Experimental offline processing probe for one silent block; diagnostic only.
- Python API validation and isolated smoke-test regression coverage.

## 0.3.0-r23 (2026-10-10)
- Verified native probe builds and links with the complete Steinberg MIT VST3 SDK.
- Link official Steinberg VST3 interface IID implementation files; avoids undefined references to IComponent, IAudioProcessor, IEditController and IHostApplication.
- Keep the SDK external and exclude SDK source and Git metadata from release ZIP.
- No change to playback, export, or realtime audio processing.

## 0.3.0-r23 (2026-10-10)
- Verified native probe builds and links with the complete Steinberg MIT VST3 SDK.
- Link official Steinberg VST3 interface IID implementation files; avoids undefined references to IComponent, IAudioProcessor, IEditController and IHostApplication.
- Keep the SDK external and exclude SDK source and Git metadata from release ZIP.
- No change to playback, export, or realtime audio processing.

## 0.3.0-r22 — External VST3 SDK checkout validation

- Reject incomplete Steinberg VST3 SDK GitHub ZIPs before native compilation.
- Require recursive SDK checkout for opt-in native VST3 compilation.
- Preserve the isolated diagnostic host; audio playback remains unchanged.

## 0.3.0-r21 (2026-10-10)

- Add explicit isolated VST3 `--configure` diagnostic: test processor setup at 48 kHz / 512 samples using a supported 32/64-bit format, without activation or processing.
- Return validated processing setup metadata to the Python probe; keep `native_host_ready=false` and production playback unchanged.
- Add tests for CLI safety, opt-in configuration, and mobile version consistency.
- The SDK-specific code path still requires compile/runtime validation against the Steinberg VST3 SDK and real plugins.

## 0.3.0-r20 (2026-10-10)

- Add isolated VST3 processor tail-length diagnostics (getTailSamples) after successful lifecycle initialization, bounded in C++ and validated in Python.
- Compile the standalone VST3 factory probe without SDK in both Linux DEB/RPM CI matrix targets, including ARM64.
- Keep realtime native VST3 hosting disabled pending official SDK and plugin interoperability tests.

## 0.3.0-r19 (2026-10-10)

- Fix Linux ARM64 packaging: install libopus-dev and pkg-config, and verify the Opus pkg-config entry before installing sphn/Demucs. This prevents audiopus_sys from building the incompatible bundled Opus source with modern CMake.
- Preserve native VST3 diagnostics in experimental isolated mode; no playback activation.

## 0.3.0-r18 (2026-10-10)

- Fix Android and iOS revision metadata mismatch causing six pytest failures in GitHub Actions.
- Add tests for VST3 discovery, path restrictions, and optional runtime; preserve the 70% coverage gate.
- Keep native VST3 probe experimental and isolated from playback.

## 0.3.0-r17 (2026-10-10)

- Harden VST3 factory class-name and category parsing by bounding reads of Steinberg fixed-size arrays.
- Reject out-of-range plugin bus channel counts before emitting diagnostics.
- Add regression guard for C++ metadata bounds; native host remains experimental and offline.
- Synchronize release identifiers and mobile build metadata.
- SDK-enabled compilation and GitHub Actions run logs were unavailable for validation.

## 0.3.0-r16 — VST3 diagnostic hardening

- Validate the requested 32-hex CID in the C++ probe before loading plugin binaries, including in no-SDK builds.
- Reject non-object JSON and diagnostic output exceeding 2 MB in the Python adapter.
- Add targeted tests and retain the isolated, non-realtime host diagnostics from r15.
- SDK-backed C++ compilation and interoperability with third-party plugins remain unverified; playback is unchanged.

## 0.3.0-r15 — VST3 processor capability diagnostics and CI build gate

- Isolated lifecycle mode now probes supported 32-bit/64-bit sample formats and reported plugin latency. Values are sanitized in the Python adapter; no audio processing is enabled.
- GitHub Actions quality job now builds the standalone C++20 VST3 probe without Steinberg SDK as a regression gate.
- Added tests for capability decoding, invalid latency data and playback isolation.
- SDK-backed compilation and real plugin interoperability remain unverified. No claims of resolving remote Actions failures without corresponding logs.

## 0.3.0-r14 — Isolated VST3 diagnostic host context

- Added a stack-scoped minimal `IHostApplication` implementation with host name, interface negotiation and reference counting in the subprocess only.
- `--lifecycle` now passes that diagnostic context to `IComponent::initialize()`. Unsupported host-created objects explicitly return `kNotImplemented`.
- Added `host_context_provided` to diagnostic JSON/Python results. `native_host_ready` remains `false`.
- No playback, rendering, VST audio processing, plugin editor or automation changes.
- SDK-backed compilation and real-plugin interoperability are **not yet validated**. Some plug-ins can legitimately decline initialization.
- Preserved the r13 VST3 support manual cover titles and PDFs.

## 0.3.0-r13
- Correct VST3 manual cover titles in both PDFs and display current revision.
- Add isolated, opt-in VST3 IAudioProcessor/IEditController interface discovery; no realtime host activation.
- Preserve existing playback and exports.

## 0.3.0-r12
- Add isolated VST3 bus information diagnostics after successful component initialization; no realtime processing.
- Update VST3 support manual titles and license-only sections in Italian and English; regenerate PDFs retaining cover artwork.

## 0.3.0-r11
- Experimental isolated VST3 lifecycle diagnostic, no audio processing enabled.

## 0.3.0-r10

- Optional VST3 SDK-backed audio-component instance creation diagnostic by exact CID; release immediately, no playback activation.
- Validate instance creation request and report results independently of factory enumeration.
- Keep all realtime VST3 processing, GUI, MIDI and automation experimental and disabled.

## 0.3.0-r9

- Added bilingual VST3 manuals (Markdown and PDF) with the exact existing user manual cover page.
- Hardened untrusted native VST3 class metadata against duplicate CIDs and control characters.
- Kept existing playback/rendering unchanged.

## 0.3.0-r8

- VST3 native SDK probe: enumerate class IDs, names, and categories in an isolated process.
- Validate factory metadata before consuming it in Python.
- Keep the default audio path unchanged.

## 0.3.0-r7
- Optional Steinberg SDK factory class-count probing in isolated native process; no change to default audio engine.
- VST3 host implementation and licensing progress documentation.

## 0.3.0-r6

- Compliance: archive scanner for source/release ZIP and TAR; rejects unreviewed bundled VST3/AU/AAX and traversal paths.
- Packaging behavior unchanged; native audio host remains experimental.

## 0.3.0-r3

- Native audio core: bounded lock-free single-producer/single-consumer float PCM FIFO, fixed-capacity memory and atomic block writes.
- Existing Python playback and VST3 offline host remain unchanged; realtime host is not yet enabled.

## 0.3.0-r2

- Added transactional native C++20 mono-to-stereo constant-power pan mixer with input validation.
- Preserved Python audio backend and existing VST3 offline path; new mixer primitive is opt-in only.
- Updated Android, iOS, and Windows revision metadata.

## 0.3.0-r1 — early development

- Begin version 0.3.0 development; v0.2.0 remains stable.
- Reserve higher platform build numbers (30001) for mobile upgrades.
- Improve release channel separation for semantic version tags.
- Add compiled PCM planar/interleaved conversion primitives for forthcoming native VST3 processing; default audio path unchanged.

## 0.2.0-r302

- Added opt-in compiled PCM accumulation primitive for future native real-time mixer; no changes to current playback engine.
- Tests cover buffer validation and equivalent portable fallback.

## 0.2.0-r301

- Per-category vector icons for insert setup panels, including VST3.
- Optional C++ PCM gain routine; existing Python processing remains default.

## 0.2.0-r299

- Mixer Insert shows a strong green indicator for active FX, amber when all inserts are bypassed, and updates without global rerender.
- VST3 insert additions and parameter changes refresh the rendered playback path when audio is playing.
- Clarified rendered VST3 playback versus native real-time host limitations.

## 0.2.0-r297

- Experimental desktop VST3 track insert discovery and isolated offline processing via optional pedalboard host.
- VST3 plugin selection in mixer insert interface, path persistence, explicit unsupported master/live restrictions and setup guide.

## 0.2.0-r296

- mixer: double click on a channel name now allows renaming the track directly from the mixer.
- insert FX setup: refreshed visual design with artistic/photo background, integrated app mark and plugin-type specific mood.

## 0.2.0-r294 — Native Settings Save freeze fix

- Avoid synchronous full-page localization during Settings Save.
- Avoid importing the server module inside the native-settings IPC handler.
- Prevent concurrent saves and report bridge errors/timeouts.
- Keep playback updates deferred and unnecessary work out of Save.

## 0.2.0-r293 — Fast Settings dialog and save

- Localize only updated DOM subtrees rather than translating the entire track-heavy page for each mutation.
- Show Settings immediately while native configuration is loading.
- Avoid relocalizing the entire interface on save unless the language actually changed.
- Skip expensive playback metadata sync on Settings save while idle.

## 0.2.0-r292
- Optimize timeline tools and track selection: update DOM state without global rendering, preserving waveform canvases and scroll.

## 0.2.0-r292 — Insert setup button legibility

- Explicit readable colors and native WebView text-fill for Save preset & apply, Apply custom and Cancel in insert setup dialogs.

## 0.2.0-r290
- Keep the sticky Chords lane fully transparent: only chord labels appear over the first track, without the dark band. Chord drag/edit and marker behavior are unchanged.

## 0.2.0-r288
- Tap Tempo icon next to BPM; manual BPM/time signature edits regenerate active metronome tracks.
- New/updated metronome tracks no longer have BPM in their name.

## 0.2.0-r287 — Track delay and metronome interval

- Inline delay under track volume (milliseconds or beats based on transport mode), applied to playback/timeline/render/export via existing persisted track delay.
- Generated metronome and chords tracks preserve their non-destructive track delay across refreshes.
- Metronome start and stop (milliseconds) are persistent; empty stop means project end. Generated metronome WAV is silent outside the requested range, with unmodified timeline timestamps.

## 0.2.0-r287 — Track delay controls

- Inline delay under track volume (milliseconds or beats based on transport mode), applied to playback/timeline/render/export via existing persisted track delay.
- Generated metronome and chords tracks preserve their non-destructive track delay across refreshes.

## 0.2.0-r286 — YouTube guidance and initial track alignment
- Explain browser playback before YouTube URL import (Italian/English).
- Reset initial Tracks/timeline vertical scroll on first track insertion and disable scroll anchoring.

## 0.2.0-r285 — timeline chord and marker visibility
- Keep chord labels and marker editing handles visible during vertical track scrolling without changing their timestamp positions or event handlers.

## 0.2.0-r284 — branding and project title layout
- Top-left native application mark links to the GitHub project.
- Project title follows the playback controls on the line below.
- Enlarged sidebar branding while retaining responsive layout.

## 0.2.0-r283
- Fix GC cleanup test race: wait for both deleted audio and committed journal removal in CI.

## 0.2.0-r282
- Compact the transport into a single toolbar; move branding to the sidebar footer and remove the redundant project title box.
- Display a dedicated Insert button in every mixer channel and master strip, opening that channel's insert manager.

## 0.2.0-r281

- Optimize embedded Lyrics/Chords/Markers tab switching: update metadata dock only, without rebuilding tracks, waveform canvases, or plugin UI.
- Opening the Plugins inspector no longer rebuilds the entire timeline when its hidden DOM is already available.

## 0.2.0-r280 — Timed row split and reconcile
- Preserve start/end boundaries when splitting Lyrics, Chords or Markers rows.
- Add contextual Reconcile timestamp on start/end fields and optional end timestamps for Chords and Markers.

## 0.2.0-r279 — Metronome type indicator in Tracks

- Display Standard / Adaptive / Zone metronome beneath the volume controls of each metronome track.
- The label follows the project metronome mode and active IT/EN interface language.

## 0.2.0-r278 — Native UI localization fixes

- Reapply active locale to dynamically inserted contextual menu items and dialog titles.
- Expand EN/IT translations for metadata search, stem separation, model management, and editing actions.
- Keep language preference Auto / Italiano / English.

## 0.2.0-r277
- MusicBrainz results: per-row information button and compact layout; pagination button legibility.
- GitHub Actions macOS Chordino: execute installer script through bash.

## 0.2.0-r276

- Multi-singer SAM Audio temporal-anchor extraction, 2–8 singers, including selective re-extraction and persisted UI model choice.
- Fix SciPy missing from GitHub Actions; add worker/audio model tests to satisfy the production coverage gate without lowering its threshold.

## 0.2.0-r276
- CI: install soundfile as a development/test dependency; the selective-stem regression test imports it during pytest collection.
- Preserve all r274 FLAC project storage, MTA export, and AI separation behavior.

## 0.2.0-r274 — Optional FLAC project storage + MTA compatibility

- Global opt-in setting for FLAC project storage in web/native Settings; defaults to WAV.
- Persist storage mode per project, and ask explicitly before migrating a WAV project when opening it.
- Convert integer PCM WAV assets to fast FLAC level 1 with decoding verification; retain 32-bit/float files without silent quantization.
- Keep previews and export PCM in ephemeral locations outside the portable project; portable archives carry referenced FLAC assets.
- MTA export continues to render all sources to a common time-aligned PCM timeline, then writes MP3 audio slots; no raw FLAC streams in MTA.
- End-to-end FLAC conversion → `.maeprojz` archive → `.mta` export tests and regression coverage.

## 0.2.0-r272 — DrumSep hybrid ONNX inference

- Combine frequency-domain ISTFT with time-domain predictions; align centred Hann STFT and overlap-add windows.
- DrumSep kit-only mix is reconstructed from kick, snare, toms and cymbals rather than copying Demucs drums.
- Non-kit percussions remain a separate SAM Audio model selection; no misleading DrumSep claim.
- Real-model inference and subjective separation quality require native testing.

## 0.2.0-r271 — DrumSep ONNX integration

- Optional ONNX model download with SHA-256 and atomic installation; selectable Kick/Snare/Toms/Cymbals.
- Demucs to DrumSep selective extraction; SAM Audio remains for non-kit percussion.

## 0.2.0-r270 — optional SAM Audio percussion separation

- Select SAM Audio Small/Base/Large or DSP; the selection is remembered across projects.
- Selectively extract kick, snare, toms, cymbals or non-kit percussion through Demucs and optional SAM Audio.
- SAM Audio uses an isolated Python worker; user-authorized gated checkpoints are not bundled.
- Only requested outputs are imported.

## 0.2.0-r269 — selective stem extraction and percussion split

- Add selective re-extraction of lead vocals, percussions, drum body and Other on an existing track.
- Add optional drums/percussions second-pass spectral separation; imports only requested stems.
- Preserve existing stem workflow and add explicit validation of selection.

## 0.2.0-r268 — transport scrubber and MusicBrainz hover
- Add a viewport-independent seek slider in the transport with whole-project progress during playback; frame zoom and project navigation as distinct controls.
- Position MusicBrainz candidate details near the hovered row within viewport bounds rather than underneath the scrolling results list.

## 0.2.0-r267 — RoFormer beartype validator compatibility
- Override legacy beartype 0.18.x with a PEP 604-compatible validator in native packaging, and add a smoke check for Callable | None.
- Make RoFormer failure actionable with an explicit dependency diagnostic.
- Preserve installed model files and existing separation/outputs.

## 0.2.0-r266 — AI backing vocal output path fix
- Resolve audio-separator relative WAV filenames inside the per-job output directory, rather than the process working directory.
- Validate both generated stems before moving them; add regression coverage for UVR MDX-NET karaoke output naming.

## 0.2.0-r265 — editor/PDF marker/lyric associations
- Align all marker placements with lyric START times, preserve multiple markers between lines, and persist explicit manual lyric anchors in the Marker schema.
- Apply the same auto/manual associations when rendering Lyrics+Chords PDF.

## 0.2.0-r264 (2026-10-09)

- Lyrics editor: marker sections grouped by lyric start timestamp; drag a marker chip onto a lyric line to persist a manual association, restore Auto via context menu.
- Preserve manual lyric-line association when its timestamp changes.

## 0.2.0-r263

- Zoned metronome BPM labels with per-zone manual/auto edit and atomic partial regeneration; marker boundary ID based persistence.

## 0.2.0-r262
- Fix marker-label double-click on timeline: retain DOM across clicks and avoid initiating a drag on caption.
- Remove inert “Master / Preview” mixer-tab button; preview/master controls remain available in their working locations.

## 0.2.0-r261 — PyTorch/torchvision native-operator compatibility

- Align torchvision with the installed PyTorch release on Windows, macOS ARM64 and macOS Intel.
- Package torchvision native extensions and validate the torchvision::nms operator in GitHub Actions before building native installers.
- Surface an actionable error if an existing runtime has incompatible torch/torchvision libraries.

## 0.2.0-r260 — 2026-10-08

- Removed the redundant standalone “Project” sidebar button. The collapsible Project / File section and all project commands remain available.

## 0.2.0-r259 — model management, sidebar preferences, bilingual UI

- Central model-manager lists Demucs and backing-vocal models, including their filesystem paths and download/delete commands.
- Sidebar sections remember their open/closed state globally across projects.
- Additional IT/EN translations for vocal separation dialogs, download and status messages.
- Background macOS multiprocessing workers request a no-Dock activation policy.

## 0.2.0-r258 — native audio-separator dependency fixes
- macOS Intel: enforce binary NumPy 1.26.4 / Numba 0.61.2 / llvmlite 0.44.0 wheels, including a constraint on the optional resampy runtime installation.
- Windows: explicitly install and freeze six, required by audio-separator UVR runtime.
- Keep native separator import checks as production gates.

## 0.2.0-r257 — Native stem dependency convergence

- ARM64: install missing audioread explicitly before validating audio-separator.
- Intel macOS: isolate a legacy NumPy 1.x-compatible audio-separator wheel from Demucs 4.1 and NumPy 1.26.
- Windows: bypass broken diffq-fixed sdist via controlled wheel installation and explicit inference dependencies.
- Add Windows-specific requirements and native preflight validation.

## 0.2.0-r256

- CI regression fixes: update legacy context-menu text assertions to the current Add chord / Extract marker labels.
- Make revision metadata regression tests version-independent while preserving Android revision and versionCode consistency checks.

## 0.2.0-r255

- Stabilized Lyrics/Chords/Markers double-click editing without rerendering on single click, preserving scroll and last-row edits.
- PDF Lyrics+Chords reserves a leading column for line-start anchored chords.
- macOS Apple Silicon PyInstaller bundles audio_separator and ONNX Runtime; CI fails when the backing-vocal engine cannot be imported.

## 0.2.0-r253
- Metronome source-track refresh with zone-aware recalculation, marker-driven updates, and transport arrow nudging.
- Timeline shortcut M and track/waveform context menu Add marker; simplified Add chord and Extract marker labels.

## 0.2.0-r252
- Double-click timeline marker labels to rename.
- Exact timestamp alignment for marker guide and chord label.
- Playback marker highlighting and synchronized metadata list scrolling.
- Wider inline timestamp editor for lyrics/chords/markers.

## 0.2.0-r251
- Timeline marker captions are placed below the chord-label band to avoid collisions when Show Chords and Show Markers are both enabled.

## 0.2.0-r250
- Timeline markers: drag and reposition, with context menu to add, enable, disable or delete while markers are visible. Markers use a vivid high-contrast magenta line and handle with distinct hover and disabled states.
- Includes r249 update-download progress indicators.

## 0.2.0-r249
- Native desktop and Android installer downloads show live progress, downloaded/total MB and an indeterminate fallback when the server omits Content-Length.
- Desktop installer download is staged atomically, with incomplete transfers rejected.

## 0.2.0-r245

- Fix macOS Intel x86_64 CI dependency resolution: librosa 0.11.x with NumPy 1.26.4, while using librosa 1.0.x on other platforms.
- Keep the preceding r243 Chord Lab features unchanged; align Android, iOS, and Windows revision metadata.

## 0.2.0-r243

- Android Gradle toolchain compatibility fix (Gradle 9.6.0).
- Restore wheel-compatible macOS Intel NumPy/Numba/llvmlite dependency pins.

## 0.2.0-r241 — dependency PR reconciliation

- Integrate GitHub Dependabot PRs #10–#15: Android Gradle Plugin 9.4.1; Ruff 0.16.10; PyMuPDF 1.28.2; macOS Intel Numba 0.68.0 / llvmlite 0.50.0 / NumPy 2.5.3; librosa 1.0.x; SoundFile 0.14.x; PyYAML 6.0.3+.
- Update platform toolchain regression checks and Android/iOS/Windows revision metadata.
- Verify deployment builds for macOS Intel, Android, Windows and iOS in GitHub Actions before publishing a production release.

## 0.2.0-r238

- Added a dockable, closable and resizable Piano / Chord Lab beside the Mixer with a scrollable two-octave mini keyboard.
- Added live note audition and common chord presets (major/minor/7/maj7/m7/dim/dim7/aug/sus2/sus4).
- Shift+click builds a live chord on the keyboard, highlights accumulated notes, plays them, and names the recognized chord when Shift is released.
- Piano panel visibility and width are persisted in the project.

## 0.2.0-r237

- Chord extraction defaults to Balanced (sensitivity 45, all advanced stages except beat quantization); legacy Default/Completo is migrated and removed.
- Lyrics/Chords extraction is automatically constrained to an active timeline Range.
- Utility/progress/extraction modals reset transient sizing on every open and keep safe minimum dimensions.
- Timeline Chords support CTRL/CMD multi-selection with batch disable/re-enable/delete; Backspace/Delete removes the selected Chords.
- Context menus display keyboard shortcuts for actions that have one.

## 0.2.0-r236

- Added track-referenced fixed/adaptive metronome generation from the track context menu; rhythmic analysis can use one selected track as the sole timing source.
- Added adaptive metronome shift in milliseconds or beats without recalculating the detected tempo map.
- Added transport display/input mode for absolute time (`mm:ss.mmm`) or musical position (`bar:beat`) using fixed tempo or the adaptive beat map.
- Persisted the metronome reference track, grid origin, shift and transport time mode in project data.
- Preserved the mixer as vertical channel strips with vertical level faders.

## 0.2.0-r235

- Added Adaptive Metronome: every request recalculates the complete beat-by-beat tempo map from the current song and regenerates the click track to follow internal tempo changes.
- Adaptive analysis excludes existing metronome tracks and persists the newly detected local BPM map in the project.

## 0.2.0-r234

- Preserva gli anchor manuali lyrics/chords durante aggiunte, eliminazioni e refresh della traccia Chords.
- Corregge export MP4 Karaoke e unifica la barra di progresso per gli export di progetto.
- Corregge apertura .maeprojz dal Finder su macOS tramite file-open argv emulation.

## 0.2.0-r233
- PDF Lyrics: una riga di lyrics che apre una nuova pagina mantiene sempre la formattazione Lyrics configurata anche quando non ha chords.

## 0.2.0-r232

- Lyrics + Chords + Markers: il timestamp di una nuova linea Lyrics usa ora il formato standard `m:ss.mmm` / `mm:ss.mmm`, con playhead precompilato e validazione coerente con gli altri editor.

## 0.2.0-r231

- Added CTRL/CMD multi-selection for synchronized Lyrics and Chords with one-shot batch deletion.
- Added partial Lyrics/Chords extraction over the current timeline range; only events inside the selected interval are replaced while events outside remain unchanged.
- Partial Chords extraction triggers a single Chords guide-track refresh after completion.

## 0.2.0-r230

- CI: removed unused `io` import from `app/mp3g.py` to satisfy Ruff.

## 0.2.0-r229

- Added project sample rate (44.1/48/96 kHz, default 44.1 kHz), fixed after the first active track is present and editable again only with no tracks.
- Audio imported at 44.1/48/96 kHz is normalized to the project sample rate for timeline use while originals are preserved.
- Added WAV export at 24-bit PCM or 32-bit float with 44.1/48/96 kHz output rates.
- Added MP3+G karaoke export as a ZIP containing same-basename MP3 audio and CDG synchronized graphics for lyrics/chords.
- Updated generated Metronome/Chords/stem tracks to honor the project sample rate.
- Restyled the M-Live/Merish MP3 specification cover to match the other MTA Audio Editor manuals.

## 0.2.0-r228

- Added M-Live / Merish compatible MP3 export using ID3v2.3 synchronized lyrics (SYLT), chords (SYLT chord content type), markers/events and USLT fallback.
- Added bilingual M-Live / Merish MP3 interoperability specification PDFs and validation tests.

## 0.2.0-r227

- Rigenerazione automatica della traccia Chords dopo ogni mutazione audio-rilevante: spostamento, modifica, aggiunta, disabilitazione, riabilitazione, eliminazione, reset ed estrazione.
- Refresh fast/parziale preferito sulla minima regione temporale interessata, con fallback automatico al render completo.
- Avviso di attesa sempre visibile durante il refresh della traccia Chords.
- Se non restano chords attivi, il refresh di una traccia Chords esistente genera correttamente una guida silenziosa invece di lasciare audio obsoleto.

## 0.2.0-r223
- Timeline chord moves now refresh an existing generated Chords audio track, preferring a fast partial-window render and falling back to a full render when needed.
- The UI always displays a wait/progress notice while the Chords track is being refreshed.

## 0.2.0-r222

- Lyrics/Chords PDF and preview: end-of-line anchored chords now stay close to the end of the lyric text or to the preceding chord instead of being pushed to the far-right page margin.
- PDF style now includes configurable vertical spacing between consecutive marker sections.
- Markers can indent their whole section by a configurable value in millimetres; preview and PDF apply the same geometry.
- New/edit marker forms automatically reuse color, section indentation and related marker options from the latest previous marker with the same name after leaving the name field.

## 0.2.0-r221
- Added keyboard shortcut C to add a chord at the current playhead when Show Chords is enabled, with popular/recent project chord shortcuts.

## 0.2.0-r220
- Chord deletion is now a real hard delete everywhere (timeline, Chords pane, Lyrics+Chords editor and cut/merge paths); deleted chords disappear immediately and are removed from persisted project data.
- Legacy chords carrying the old `deleted=true` soft-delete flag are purged when a project is rendered.
- Fixed timeline chord double-click editing by preserving the marker DOM node after a click without drag.
- Added a vertical waveform positioning guide while dragging a timeline chord, with the exact live timestamp shown beside the guide.
- Added visual chord shortcuts during chord editing, ranked by project usage frequency with most-recent occurrence as tie-breaker.


## 0.2.0-r219
- Registered Portable MTA Audio Editor (`.maeprojz`) as the primary OS document type on Windows and macOS.
- Added `.maeprojz` document/file associations on iOS and Android.
- Kept `.maeproj` registered as a legacy-compatible project type.
- Added regression tests for native/mobile portable project associations.

## 0.2.0-r218

- CI: fixed Ruff F841 in the track-export endpoint so the production workflow can proceed to downstream build jobs.


## 0.2.0-r217
- Portable MTA Audio Editor (`.maeprojz`) is now the default native save/open format; opened portable files stay bound so autosave/manual Save rewrite the portable file instead of only the internal workspace.
- Fixed Chords extraction persistence: refreshed extracted state is rendered before collection/persistence and synchronized to the bound portable project.
- Plugin Inspector now reserves horizontal timeline viewport while open so tracks/playhead/follow never continue underneath it.
- Insert plugin setup opened from Inspector is routed to the top-level utility modal and remains above the Inspector.
- Single-track MP3 export from Plugins/Inspector now asks bitrate, sample rate and editable ID3 metadata before destination selection/rendering.

## 0.2.0-r216
- Added an interactive Chords lane above the first timeline track when Show Chords is enabled.
- Chord markers can be dragged to retime them, edited by double click, and disabled, deleted or re-enabled from their context menu.
- Added “+ Chord at current position” to the timeline context menu.

## 0.2.0-r215
- CI: removed unused `io` import reported by Ruff F401 in the r210 preview/overlay regression tests.
- Tests: revision/build-number validation is now revision-agnostic so future revisions do not fail on a hard-coded r213 assertion.
- Mobile/native packaging metadata aligned to revision 214.

## 0.2.0-r213

- Fixed insert-plugin configuration windows being hidden below the absolute Plugins/Inspector overlay by moving utility dialogs to a higher application modal layer.
- Native single-track WAV/MP3/FLAC export now asks for the destination path before rendering starts; cancelling the save dialog prevents the render job from starting.
- Added atomic native save-to-preselected-path support for rendered audio files.
- Browser track/audio exports use the Save File picker for WAV/MP3/FLAC when supported, with download fallback otherwise.

## 0.2.0-r212

- Zoom timeline reso fluido: durante il trascinamento dello slider viene mostrato immediatamente un preview grossolano scalando la waveform già renderizzata; il redraw completo avviene una sola volta al rilascio.
- Aggiunti pulsanti `−` e `+` per variare gradualmente lo zoom.
- Doppio click sul cursore dello zoom per ripristinare il valore di default (100% / 70 px/s).
- Aggiunto selettore di preset zoom percentuali (25–400%), temporali (1/5/10 s, Fit) e musicali (1/2 beat, 1/2/4/8 misure).
- I preset beat/misure sono calcolati dinamicamente da BPM e time signature del progetto e adattati alla larghezza visibile della timeline.
- Range massimo dello zoom esteso a 1200 px/s per consentire viste musicali ravvicinate.
- Test completi: 705 test passati, coverage 71,23%.

## 0.2.0-r211

- Added direct horizontal clip movement in Select mode.
- Added Shift+drag grouped movement for all clips of selected track(s).
- Added Delete selected range to the timeline context menu.

## 0.2.0-r209

- Chord extraction: new Songbook/Stable, Balanced, Detailed and Raw pipeline presets with explicit sensitivity, minimum chord duration, density ceiling and optional beat quantisation.
- Chord extraction: harmonic refinement, sevenths, sus, dim/aug, slash-bass/inversions and temporal smoothing can be enabled/disabled independently.
- Chord extraction: Stable profile prioritises Madmom Deep Chroma + CRF / CNN+CRF for a more regular major/minor progression, then falls back to Chordino/MTA.
- Native macOS: Chordino discovery now uses only the runtime actually inside the frozen .app; stale CI/Homebrew paths are ignored.
- Native macOS CI: packaged-app smoke test is run with Chordino build/runtime variables removed, preventing false positives from the build workspace.
- Chordino diagnostics now distinguish missing Vamp host, missing plugin and host execution failures.

- r208: CI maintenance: remove unused test imports that blocked Ruff after r207.
## 0.2.0-r207

- Reworked timeline waveforms with a 4096-bin signed min/max envelope instead of the legacy 1024 absolute peaks.
- Waveform cache now preserves upper/lower signal asymmetry and transient detail and is sampled at 8 kHz before envelope extraction.
- Timeline rendering uses a filled high-resolution envelope with zoom-aware aggregation/interpolation and light visual smoothing.
- Legacy waveform caches remain readable and are automatically regenerated because the waveform revision now includes the new cache format.

## 0.2.0-r206

- Simplified automatic chord extraction to a conservative vocabulary (major/minor, 7, maj7, m7, sus2/sus4, dim, aug) with stronger temporal stabilization and fewer slash chords.
- Complex/altered chord symbols remain supported for manual editing and existing projects, but are no longer aggressively proposed by automatic extraction.
- Native macOS Chordino runtime discovery now searches actual PyInstaller app bundle locations (Frameworks/Resources/MacOS/_MEIPASS), builds VAMP_PATH from discovered plugin directories, and exposes runtime diagnostics when the host/plugin cannot load.


## 0.2.0-r205
- Project preview WAV garbage collection: orphaned/stale `.preview/*.wav` files are cleaned during project maintenance.
- Preview files belonging to deleted tracks are removed; only the two most recent previews per existing track are retained.
- Rebuildable `preview-master.mp3` is cleaned as part of project maintenance.
- Preview GC never touches source audio, Clip Library media, or shared-media blobs.

## 0.2.0-r204
- Fixed the Lyrics + Chords + Markers PDF preview in native WebViews by removing the iframe layer and injecting the exact rasterized PDF pages directly into the preview modal.
- Fixed the Plugins/Inspector stacking context so its header and close button stay above the Project Clips bar.
- Kept the Inspector header sticky while only the plugin body scrolls.


## 0.2.0-r203
- Clear Lyrics/Chords playback overlays immediately on Stop and project close. Pause keeps the current overlay visible.
- Widen the Lyrics + Chords + Markers timestamp column and force single-line timestamps.
## 0.2.0-r202
- Native `.maeproj` is now a lightweight modular project manifest, not a ZIP archive.
- Portable self-contained project archives use `.maeprojz`; legacy ZIP-based `.maeproj` files remain importable.
- Normal Save updates only the small manifest/workspace; Save Copy creates a portable archive.

## 0.2.0-r201

- Fix macOS arm64 Chordino provisioning: use the Homebrew include root for Vamp SDK headers while linking `libvamp-sdk.a` from the library directory.
- No application behavior changes.

## 0.2.0-r200

- Fix native Chordino provisioning in GitHub Actions on Windows and macOS.
- Windows now cross-compiles NNLS-Chroma x64 reproducibly on Linux and transfers it as a same-run artifact.
- macOS now uses the runner architecture, Homebrew Boost headers, and the actual Homebrew libvamp-sdk.a path.

## 0.2.0-r199

- CI maintenance: fix Ruff/Bandit findings from r198 (HTTPS validation for chord model downloads, logged ensemble failures, remove unused test import).
- No intended application behavior changes.

## 0.2.0-r198

- Project-open storage maintenance now removes unreferenced local audio before editing begins.
- Added content-addressed shared media store across projects with SHA-256 deduplication, hardlink-first local references, safe copy fallback, and reconstructible global reference index.
- Added emergency shared-media rescan/rebuild + garbage collection that scans every project before deleting any shared blob.
- Native autosave now writes only the persistent modular workspace; `.maeproj` is refreshed on explicit Save/Save Copy rather than every autosave.
- Recent native projects reopen their persistent workspace first, preserving crash-recovery state newer than the last portable archive snapshot.

## 0.2.0-r197

- Peak-normalize generated Metronome and Chords guide audio to 0 dBFS and reset their generated-track faders to 0.0 dB.
- Track deletion is now a single logical-delete transaction; the UI updates immediately without a pre-delete full native archive save.
- Added a persistent, crash-safe project garbage-collection journal for unreferenced audio. Cleanup runs asynchronously and resumes/reconciles on restart.
- Generated Metronome/Chords assets are disposable when their tracks are deleted; reusable imported Project Clips remain protected.
- Native project archives exclude pending-GC journal entries and files already logically deleted.


## 0.2.0-r196
- Fixed Lyrics + Chords + Markers editor rendering so word-level/automatic chords remain visible when lyrics are editor-only auto-syllabified; chords can again be selected and reassigned to individual syllables.
- Added staged project-opening progress for workspace, recent native projects, and native project files, covering project loading, metadata/tracks initialization, waveform/UI setup, workspace refresh, and audio prewarm.

## 0.2.0-r195
- Added Fast, Accurate and Maximum-accuracy chord extraction profiles.
- Added on-demand BTC-HCQT and ChordFormer model integrations.
- Added weighted multi-engine ensemble recognition with common extended harmony/bass refinement.
- Added model-manager metadata and progress disclosure for the new chord engines.

## 0.2.0-r194
- Chordino/NNLS-Chroma is now bundled in Docker/Kubernetes and native desktop builds instead of relying on a host installation.
- Linux/Kubernetes builds compile upstream NNLS-Chroma natively and use vamp-simple-host, including amd64/arm64 images.
- macOS native builds compile and bundle Chordino plus a private Vamp host; Windows bundles Sonic Annotator plus an x64 NNLS-Chroma runtime.
- Runtime discovery validates the actual `nnls-chroma:chordino` plugin and exposes host/plugin diagnostics to the UI.
- Native apps configure private PATH/VAMP_PATH automatically, so no system-wide plugin installation is required.
## 0.2.0-r193

- Inspector/plugin panel header is now always visible and reachable.
- Inspector content scrolls inside its own body while Inspector/Stems/Metadata and the close button remain sticky.
- Fixed panel stacking so timeline/mixer layers cannot cover the plugin frame header.

## 0.2.0-r192

- Added multi-stage high-fidelity harmonic analysis after the selected base recognizer.
- Extended chord vocabulary: sevenths, diminished/half-diminished, augmented, sixths, suspensions, added/extended ninths, altered dominant chords.
- Added dedicated bass-chroma analysis for inversions and slash chords (for example C/E and G7/B).
- Added temporal stabilization and base-engine root priors to reduce transient/over-complex labels.
- Chord extraction progress now reports the individual harmonic-analysis stages.

## 0.2.0-r191

- Added a unique generated Chords/Accordi guide track with synchronized digital-piano playback from active project chord events.
- Repeated creation regenerates/reuses the same Chords track and consolidates old duplicates.
- Chords guide participates in the normal mixer, live controls, playback graph and VU metering.

## 0.2.0-r190

- Lyrics + Chords + Markers: clicking an already selected chord now deselects it; double-click still opens structured editing.

## 0.2.0-r189

- Replaced multi-HTMLMediaElement playback with one deterministic WebAudio AudioContext transport.
- Track/master/metronome VU meters now read the actual WebAudio graph.
- Mixer controls are live; rendered track FX are hot-swapped without restarting transport.
- Lyrics editor automatically syllabifies words visually for fine chord anchoring without changing persisted lyric text.
- Disabled lyric lines remain timing boundaries, so they never steal or hide chords from the preceding active line.

## 0.2.0-r188

- PDF Lyrics + Chords + Markers preview now renders the actual generated PDF pages, eliminating divergence from export.
- Native WebViews preview rasterized pages from the same PDF backend instead of a parallel HTML reconstruction.

## 0.2.0-r187

- Playback: removed periodic hard-seek synchronization that caused regular drop-outs in non-Render mode. Re-lock now occurs only at transport actions or after real decoder stalls.
- Render playback: switched from one immutable rendered master to processed per-track stems so volume, pan, mute and solo are live WebAudio controls.
- Insert controls: parameter sliders now schedule live processed-stem replacement while playback continues.
- Preview stems keep volume/pan/mute neutral server-side to avoid double-applying mixer controls.

## 0.2.0-r186

- Lyrics + Chords + Markers: automatic chords before the first sung word are no longer forced onto that word; explicit/manual anchors take precedence.
- Marker editing now includes marker color.
- PDF chords always use the Chords style and never inherit marker/section styling.
- Chords can be anchored to a character position inside a word when syllable timing is unavailable.
- Metronome creation is idempotent: a project can contain only one metronome track, which is regenerated/reused on repeated requests.

## 0.2.0-r185

- CI maintenance: removed unused imports from the compound-meter regression test so Ruff no longer stops the production workflow; revision metadata tests now validate alignment dynamically instead of hard-coding r184.

## 0.2.0-r184

- Lyrics + Chords + Markers: double-click words, chords, and markers to edit them.
- Lyrics text can be edited inline without changing timestamps.
- Chords anchored to deleted words/syllables are reassigned to the previous available token, then the next one, with line-start fallback.


## 0.2.0-r182
- Corrected metronome timing when changing meter from 4/4 to 6/8 (and other /8 signatures): the denominator no longer doubles the audible click rate.
- Manual time-signature BPM recalculation now resolves half/double-tempo ambiguity against the current project BPM, preventing unintended x2/x0.5 jumps.
- Compound meters 6/8, 9/8 and 12/8 retain their grouped accent behavior without changing pulse speed.
- Lyrics + Chords + Markers editor: keep only the combined view, remove duplicate Chords/Markers sections, and provide an explicit persistent vertical scrollbar.

## 0.2.0-r180
- Lyrics + Chords + Markers editor: persistent Save action in top toolbar and footer.
- Prevent accidental loss of unsaved editor changes on close.
- Make all editor action labels readable in native WebViews.
- Make the complete editor body vertically scrollable while keeping controls accessible.

## 0.2.0-r179
- Fixed Render playback echo by preventing parallel rendered-master and per-track audio paths.
- Stabilized non-render playback and track VU metering.
- Metronome and BPM/time-signature analysis now honor compound meters such as 6/8.
- Lyrics + Chords PDF preview/native button readability fixed; added configurable lyric line spacing.
- Added automatic marker extraction from the track context menu.
- MusicBrainz matches now expose richer hover details, scrolling and pagination (10/page).
- Lyrics + Chords graphical editor button readability improved and individual chords can be enabled/disabled independently.
- Delete tracks / Delete selected range moved into the Select/Split/Range/Ripple toolbar row.

## 0.2.0-r177
- Fixed unreadable Lyrics + Chords editor controls.
- Timeline selection/range overlays are now drawn only on selected tracks; the toolbar shows the selected-track count.
- Moved Delete tracks / Delete selected range into the compact upper editor toolbar.
- Added native OS-language detection with Auto/Italiano/English override and bilingual native UI translation.
# Changelog

## 0.2.0 — revision 175

- Main transport now exposes the project time signature directly next to BPM; changing it recalculates BPM using the selected meter.
- Plugins/Inspector frame can be closed with an explicit × button and reopened from the Plugins sidebar entry without losing plugin state; visibility is persisted in the project.
- Carries forward adaptive/persisted mixer height, per-track vertical resizing, previous/current/next lyrics/chords display options, and time-signature-aware BPM estimation/PDF metadata.
- Project export excludes muted tracks using the live project state, offers optional peak normalization for WAV/MP3/FLAC, includes an explicit Stop Preview control, keeps export-button labels readable, and uses a single atomic overwrite path in native mode.
- Native sidebar keeps Save project, hides redundant Save project locally, and preserves Save project as.
- Updated desktop/mobile build metadata to revision 175 and retains the GitHub Actions Ruff/coverage fixes.

## 0.2.0 — revision 173

- Project exports now omit tracks explicitly marked Mute; MTA slot planning and mapping ignore muted tracks as well.
- Added per-track vertical height resizing in the Tracks/timeline view, persisted in the project with a 78 px minimum/default.
- Native desktop sidebar now hides the redundant “Save project locally” action and exposes “Save project” for an explicit manual save of the current project.

## 0.2.0 — revision 153

- Standardized release identity into three independent fields: product version `0.2.0`, revision `153`, and 14-digit `BUILD_INFO`.
- Stable release tag convention is now `v0.2.0`; exact artifacts use `0.2.0-r153`.
- Propagated the convention across runtime metadata, CI/CD, Docker, Kubernetes, Windows/macOS installers and Android/iOS packages.
- Preserved the `.maeproj` association fix and realtime playback work from the preceding revision chain.

## 0.2.0-151

- Reworked realtime transport around an `AudioContext` master clock instead of using one track as the timing authority.
- Added background decoder/source prewarming when a project opens so Play normally starts without a visible buffering phase.
- Reduced startup buffering to the minimum decodable window near the cursor; deep buffering continues in the background.
- Tracks start muted, hard-lock to the transport clock, then fade in over 8 ms to avoid audible inter-track start skew.
- Sync monitoring now runs every 120 ms with tighter micro drift correction and hard relock only for meaningful drift or decoder recovery.
- Non-render playback starts from dry/direct sources immediately; enabled track FX are prepared in the background and hot-swapped with a short clock-locked crossfade.
- Master volume no longer forces a rendered preview; it stays a realtime Web Audio gain control. Rendered-master mode remains available through the explicit Render Preview toggle.
- Mute, Solo, Pan and Volume remain downstream realtime controls and therefore do not wait for server render or buffering.

## 0.2.0-150

- Project files now use the dedicated `.maeproj` extension instead of `.zip` / `.mta-project.zip`.
- New project saves/exports use MIME type `application/vnd.mta-audio-editor.project`; legacy `.mta-project.zip` and `.zip` project archives remain readable.
- Windows installer registers `.maeproj` with MTA Audio Editor and double-click launches the application with the selected project.
- macOS bundle declares the `.maeproj` document type and exported UTI `com.desalvo.mtaaudioeditor.project`.
- Native desktop startup consumes an associated project path and opens it automatically in the editor.
- Android and iOS declare the same project MIME/UTI for platform file association/document pickers.

## 0.2.0-149

- Restore New project activation: after creation the app now reopens the canonical project through the same `openP()` path used by Open project, immediately restoring Tracks, Mixer, timeline and toolbars.
- Native YouTube import adds operating-system clipboard fallback (macOS `pbpaste`, Windows native clipboard API, Linux Wayland/X11 fallback) plus explicit Paste buttons for URL and track-name fields.
- Redesign YouTube import into clear Source, Positioning and Rights sections with responsive layout for narrow native windows.

## 0.2.0-148

- Lyrics editor: insert new rows anywhere with **+ above** / **+ below** controls.
- Lyrics editor: add a dedicated **Split** action that divides a segment timing at its midpoint and creates an editable row below.
- Lyrics editor: delete any row before saving, with confirmation for non-empty rows.
- Chords editor now mirrors the Lyrics row workflow with **+ above**, **+ below**, **Split** and **Delete** on every chord row; Split creates an editable chord point at the temporal midpoint.
- Preserve word-level timing against the original lyric row even when rows are inserted or removed.

## 0.2.0-147

- Lyrics editor redesigned as a large structured, resizable editor instead of a one-line prompt.
- Lyrics rows expose Start, End and Text as separate editable fields; Chords and Markers use the same structured Time/Value workflow.
- Timed editors support `mm:ss.mmm` or seconds, add/remove rows, automatic sorting by start time and mobile-safe scrolling.
- Editing a Lyrics row invalidates stale per-word karaoke timing only for the changed row.

## 0.2.0-146

- Fix GitHub Actions Ruff S110 failures in native AI accelerator probing by logging non-fatal CUDA/MPS probe errors instead of silently passing.

## 0.2.0-145
- Lyrics/Chords extraction chooser stays open until a real background job exists and the progress dialog can show a concrete preparation/download/analysis state.
- Extraction progress now uses real audio time in 5-second chunks, with indeterminate progress while a model is being loaded/downloaded and monotonic percentages during analysis/sync/save.
- Native Open recent is persisted by the native bridge in `native-settings.json`, so recent projects survive WebView/app restarts.
- Lyrics/Chords extracted by background jobs are immediately persisted, reloaded into the UI, and synchronized to any bound native project archive so they survive the next launch.
- Added regression tests for timed-text JSON round-trip and native recent-project persistence.

## 0.2.0-144
- Lyrics extraction now defaults to OpenAI Whisper **base** (still user-selectable).
- Lyrics/Chords/Markers panel is responsive, wraps controls safely on narrow windows, and can expand into a dedicated full-size working window and return to the docked view.
- PDF preview no longer relies on an embedded PDF viewer in native WebViews; it renders a faithful printable HTML preview while keeping real PDF download/export unchanged.
- Native/web transport startup is faster for simple unprocessed tracks by playing the original project audio directly; dynamic prebuffer requirements were reduced and playback no longer waits for a full autosave before starting.
- Spacebar play/stop handling is captured more robustly across native WebViews.
- Mute/Solo changes now queue a second rendered-master refresh when a previous refresh is still running, so the latest mixer state is never dropped.
- Track context menu adds **Recalculate BPM from this track**, updating project/base BPM from the selected track.

## 0.2.0-143

- Native AI Models: pulsanti Lyrics/Chords con testo sempre leggibile nelle WebView native.
- Waveform timeline più densa: rendering per pixel visibile con interpolazione tra i picchi persistiti, mantenendo il rendering leggero.
- Lyrics e Chords: estrazione progressiva con output parziale live, progressbar e comando Annulla estrazione.
- Download modelli Lyrics/Chords tramite job con progressbar (indeterminata quando il backend non espone i byte totali).
- Accelerazione AI automatica: CUDA o Apple Metal/MPS quando disponibili, fallback CPU; Madmom prova il backend Torch accelerato prima del fallback NumPy.
- Madmom Deep Chroma/CNN: input convertito automaticamente in WAV PCM RIFF 44.1 kHz prima dell'analisi, eliminando gli errori sui contenitori MP3/M4A/AAC.
- Android metadata aggiornati a versionCode 20143 / versionName 0.2.0-143.

## 0.2.0-142

- Android CI: installa i package SDK reali `platforms;android-37.0` e `build-tools;37.0.0`, mantenendo compileSdk 37, AGP 9.1.1 e Gradle 9.3.1.
- Corretto il fallimento `Failed to find package platforms;android-37` sui runner GitHub Actions.

## 0.2.0-141

- Android toolchain aligned with androidx.core 1.19.1: compileSdk 37, AGP 9.1.1, Gradle 9.3.1, explicit API 37/build-tools install in CI.

## 0.2.0-140

- Fixed GitHub Actions Ruff regressions in sample-editor/native TLS code.
- Fixed chord dependency auditing for the commit-pinned non-PyPI madmom-infer package while retaining strict auditing of all resolved PyPI dependencies.
- Integrated Dependabot Android updates: androidx.core 1.19.1 and ONNX Runtime Android 1.30.0.

## 0.2.0-139

- Project Clip browser now starts collapsed and resets to collapsed whenever a project is created, opened or imported.
- Web Settings are robustly available to administrators and reload the session if needed before routing.
- Native desktop viewport is pinned to the application frame so accidental document scrolling cannot strand the UI below the top.

## 0.2.0-138

- Redesigned About dialog with a large application logo and documentation cover photo background that does not interfere with application information.
- Build identifiers now use the strict 14-digit `YYYYMMDDhhmmss` format.
- Native Settings buttons use explicit WebView-safe text styling.
- Settings is now available to normal web users with editor preferences, AI model management and account access; administrators also get server administration access.

## 0.2.0-137

- Export is now an on-demand dedicated dialog and is no longer kept as a persistent panel beside the mixer.
- Removed the vertical PROJECTS section from the sidebar.
- Added native-only Open recent under PROJECT / FILE, limited to projects that still exist in the native workspace.
- Web Open project now lists projects already active on the server; Open local project imports a project archive from the user's device.
- Native Open project keeps the filesystem-native project picker.

## 0.2.0-136

- Added a dedicated high-resolution waveform/sample editor opened from a track context menu or by double-clicking its timeline waveform.
- Added sample-addressable selection/readout plus cut, copy, paste and remove operations that create an isolated edited source for the selected track.
- Added in-place Pitch Correction (semitones + cents), pitch-to-scale Auto-Tune, Normalizer, Maximizer and 32-band Graphic EQ with factory presets and debounced processed previews.
- The sample editor uses a cached pre-insert track render and an adaptive min/max envelope pyramid so waveform detail follows the current zoom without plotting every audio sample.

## 0.2.0-135

- Fix native Madmom chord recognition bundling by explicitly freezing its lazily imported chord/chroma/CRF modules and checking real submodule availability.
- Clarify Chordino/NNLS-Chroma status: it uses no AI model and requires an installed Sonic Annotator + Chordino engine.
- Replace slow waveform full-audio fetch/decode rendering with zoom-aware drawing from persisted waveform peaks only.

## 0.2.0-134

- Fixed native Lyrics/Chords model download buttons and native TLS trust-store handling.
- Native TLS now uses the OS trust store via truststore, with verification kept enabled.
- Fixed Chords AI runtime by pinning madmom-infer to an upstream commit that actually contains chroma/chord modules; PyPI 0.2.0 predates them.
- Model download endpoints now return useful diagnostics instead of a generic HTTP 500.

## 0.2.0-133

- Track context menu: “Separa” now always opens a parameter wizard before starting, with explicit Demucs model, stem count and optional Lead/Backing model selection.
- Track stem jobs now pass the selected stem_count to the Demucs plugin instead of only storing it in the job metadata.
- Dynamic multitrack playback: removed aggressive 50 ms hard-seek correction that could starve buffering tracks after 1–2 seconds; buffering recovery is now conservative and drift correction is smooth.
- Dynamic multitrack playback: require a real buffered-ahead window before synchronized start and use a healthier active media clock when the previous clock stalls/ends.
- Transport Stop now invalidates pending playback/render startups immediately and aborts media loading where possible, preventing delayed restart after Stop.
- Improved timeline/audio synchronization during start, seek, resume and recovery from buffering.

## 0.2.0-132

- Mixer: separate fader, dB scale and realtime VU columns so meters never overlap the volume control.
- Mixer: always-visible graduated dB scale beside every track and Master fader.
- Mixer: double-clicking the volume fader resets the level to 0 dB for tracks and Master.
- Mixer: add realtime-only red PEAK LEDs, latched at 0 dBFS until meter reset/stop.

## 0.2.0-131

- Fix macOS Intel native dependency resolution: keep NumPy 1.26.4 while installing the chord engine so it remains compatible with Numba 0.61.2 / llvmlite 0.44.0 used by Whisper.

## 0.2.0-130

- Fixed macOS x64 native CI packaging for Whisper by pinning numba 0.61.2 and llvmlite 0.44.0 only on Darwin/x86_64, ensuring CPython 3.12 prebuilt wheels are used instead of an LLVM source build.

## 0.2.0-129

- Fixed GitHub Actions coverage gate after AI model manager growth by adding focused coverage for Lyrics/Chords model download, catalog, availability, cache and deletion paths.
- Kept the production coverage threshold at 70%; full suite now reaches 70.13%.

## 0.2.0-128

- Hide all Lyrics export controls until Lyrics exist.
- Show Lyrics+Chords TXT/ChordPro exports only when both Lyrics and Chords exist.
- PDF preview/download labels now reflect whether the document contains Lyrics only or Lyrics + Chords.
- Added defensive export guards for missing Lyrics/Chords.

## 0.2.0-127

- Added independent Lyrics and Chords reset actions with confirmation. Resetting clears both synchronized content and the corresponding engine/model provenance, without affecting the other analysis type or project rights metadata.
- Added inline in-app preview for the Lyrics + Chords PDF, using the exact same renderer as the downloadable export.
- Added responsive PDF preview styling for desktop and mobile web clients.

## 0.2.0-126

- Added unified on-demand model management for Lyrics (OpenAI Whisper) and Chords, with server storage in web deployments and local storage in native desktop applications.
- Added selectable Whisper models (tiny/base/small/medium/large-v2/large-v3/turbo), with large-v3 as default.
- Added explicit chord engines: Madmom Deep Chroma + CRF (default AI), Madmom CNN + CRF, Chordino / NNLS-Chroma and built-in MTA Chromagram.
- Chord extraction UI now always discloses the exact engine/model and checkpoint licensing before extraction.
- Added download/delete APIs and model-manager UI for Lyrics/Chords models; model choices also apply to Import & Separate workflows.
- Persist the last Lyrics and Chords engine/model used in project metadata.

## 0.2.0-125

- Fix lyrics extraction in production: OpenAI Whisper is now installed in Docker/server and native builds instead of being only an optional requirements file.
- Bundle the Whisper Python package in PyInstaller desktop applications; model weights remain on-demand and cached.
- CI audits the lyrics dependency set and production Docker smoke validation imports Whisper.
- Clarify in the UI that the selected Whisper model is downloaded on first use.

## 0.2.0-124

- Lead/backing vocal separation now uses selectable AI karaoke models by default via audio-separator 0.47.0.
- Default model: UVR-MDX-NET Karaoke 2; optional Mel-RoFormer Karaoke models are selectable.
- Models are downloaded on demand to server cache, or locally in native desktop mode.
- Center/side DSP is retained only as an explicit fallback.

## 0.2.0-123

- Added optional second-pass Lead Vocals / Backing Vocals separation after Demucs.
- Supports a configurable dedicated AI separator through MTA_LEAD_BACKING_COMMAND, with a deterministic FFmpeg center/side fallback.
- Added web workflow option and job metadata reporting the vocal split method.

## 0.2.0-122

- Fixed GitHub Actions Ruff failures in clip metadata probing and YouTube import job validation.
- Clip metadata probe failures are now logged instead of silently ignored.

## 0.2.0-121

- Project Clip Browser: added a collapsible per-clip details panel, collapsed by default.
- Persist technical clip information: semantic type, codec/container format, bitrate when available, duration, byte size, provenance, project-relative location and embedded metadata.
- Added editable per-clip notes stored in the project without changing track-to-clip `source_clip_id` associations.
- YouTube imports record the source URL as provenance; local file imports record the original filename.
- Existing project clips are backfilled conservatively via ffprobe and stored to avoid repeated probing.

## 0.2.0-120

- Project clip browser: rename reusable clips without changing existing track names or breaking associations.
- Track-to-library association is now explicit via stable `source_clip_id`, with automatic migration of existing projects.
- Added per-clip audio preview controls in the project clip browser.
- Added case-insensitive clip-name search and pagination with at most 10 clips per page.

## 0.2.0-119

- Added a reusable project Clip Browser containing audio assets independently from their timeline instances.
- A library clip can be inserted on the timeline any number of times without duplicating the source audio file.
- Dragging a clip to the timeline creates a new track at the horizontal drop time; touch devices get a dedicated pointer-drag handle, with a + button fallback that inserts at the current play cursor.
- Existing projects automatically backfill the clip library from current tracks.
- Deleting timeline tracks no longer deletes audio assets retained by the project clip library.

## 0.2.0-118

- Added server-side YouTube audio import for a single `youtube.com`/`youtu.be` video, using yt-dlp stable 2026.08.19.
- YouTube imports are audio-only, asynchronous, size-limited, restricted to validated HTTPS YouTube video URLs and reject playlist-only URLs.
- Added explicit user confirmation that the content may lawfully be downloaded/imported.
- Imported audio follows the normal track pipeline: ffprobe validation, duplicate detection, project original preservation, waveform generation, optional auto-sync and first-track BPM estimation.

## 0.2.0-117

- Fixed the Container production gate after the msgpack 1.2.3 dependency update: the CI runtime verification now expects msgpack 1.2.3, matching the Dockerfile and installed image.
- Quality/Ruff/unit-test behavior from 0.2.0-116 is unchanged.

## 0.2.0-117

- Fixed the Container production gate after the msgpack 1.2.3 dependency update: the CI runtime verification now expects msgpack 1.2.3, matching the Dockerfile and installed image.
- Quality/Ruff/unit-test behavior from 0.2.0-116 is unchanged.

## 0.2.0-116

- Fixed CI Ruff F821 in `app/codec.py` by importing `RightsRecord` for synchronized MTA metadata restoration.
- Preserved the 0.2.0-115 mobile context-menu behavior and multi-provider rights metadata features unchanged.

## 0.2.0-115

- Added iPhone/iPad and touch-device track contextual menus via a 600 ms long press on track headers and timeline lanes.
- Long-press is cancelled when the finger moves beyond a small threshold so normal scrolling does not accidentally open menus.
- Added a touch-friendly `⋯` menu button on every track as an accessible fallback; it is hidden for fine-pointer desktop users.
- Preserved desktop right-click behavior and reused the same track context-menu actions on all input methods.
- Increased contextual-menu touch targets on coarse-pointer devices and suppressed Safari touch callouts on context-enabled track surfaces.

## 0.2.0-114

- Rights metadata is explicitly multi-provider: one project can persist simultaneous repertoire records from SIAE, Soundreef and other configured providers without collapsing them into a single match.
- Project Info now shows every stored repertoire record and its provider, title/original title, authors, performers, publishers, identifiers and source.
- Lyrics + Chords PDF and ChordPro exports now include all stored fields for every selected provider record, not only a subset.
- Clarified in the repertoire UI that provider selections are search preferences while stored records are cumulative project metadata.

## 0.2.0-113
- Track colors and drag/drop ordering.
- Key/BPM metadata in lyrics/chords PDFs and transposition-aware chord export.

## 0.2.0-97

- Added native on-device stem separation for iPhone/iPad using Core ML-compatible Demucs models.
- Added Auto / Local / Server mobile execution modes with automatic server fallback.
- Added authenticated model provisioning and on-device model compilation/cache.
- Added chunked 44.1 kHz stereo inference with overlap-add and WAV stem import into the project.
- Added conservative device-aware Auto stem recommendations and a 12-minute local safety limit.
- Added `scripts/export_demucs_coreml.py` documenting/exporting the expected Core ML model contract.

## 0.2.0-81

- Added persistent editable per-track MTA slot assignment in the Track Inspector.
- Export suggestions now honor explicit track slots and confirmed mappings update the track slot preference.
- Factory FX presets now expose schema-valid parameter values to the client; changing preset immediately refreshes visible controls.
- Added synchronized rotary knob + numeric controls for continuous plugin parameters, while the 32-band EQ keeps dedicated faders.
- Expanded the IT/EN user manuals: MTA = Multi Track Audio, MTA8/MTA16 creation, project/single-track exports, online/mobile authentication/TOTP scope, track slot workflow and FX controls.
- README now links directly to all IT/EN PDF manuals and includes an English section.
- Replaced documentation UI screenshots derived from the historical mockup with captures rendered from the current application template/JS/CSS and a deterministic demo project.
- Updated MTA format documentation and data/API/architecture references.
- Regenerated all IT/EN PDF manuals and checked section-heading orphan candidates.

## 0.2.0-73

- CI: remove the stale unused `revision` assignment in the waveform import fallback so Ruff F841 passes without suppressing the rule.

## 0.2.0-73

- CI: suppress Ruff/Bandit S310 on both `urllib.request.Request` construction and `urlopen`, only after strict HTTPS/provider-host validation in `_validate_oauth_endpoint`.
- Keeps the OAuth endpoint allowlist, HTTPS-only policy, no embedded credentials, and port 443-only validation introduced in 0.2.0-69.


## 0.2.0-73
- Waveform cache resa esplicitamente persistente e validata all'apertura: i picchi salvati nel progetto vengono mostrati subito e la revision server-side rigenera automaticamente solo waveform mancanti o obsolete, salvando il risultato nel progetto.
- La revisione waveform generata durante import/metronomo usa ora la stessa firma track-aware (sorgente + insert) usata per la validazione successiva.
- Il Play/Preview resta indipendente dalla disponibilità o dal calcolo delle waveform.
- Rimosso il pulsante Record dalla transport, non essendo associato ad alcuna funzione di registrazione.
- Aggiunti Mute all / Unmute all, Solo all / Unsolo all e Bypass all FX / Enable all FX per tutti gli insert di traccia e master. Il cambio globale degli FX invalida e rigenera le waveform delle tracce interessate.

## 0.2.0-73

- Security/CI fix for social OAuth HTTP calls: endpoints are now restricted to HTTPS and to the explicit Google, GitHub and Facebook provider hosts before any network request.
- Ruff S310 is suppressed only on the validated `urlopen` call, with regression coverage for rejected schemes, credentials, ports and untrusted hosts.

## 0.2.0-68

- Added optional OAuth 2.0 login/registration with Google, Facebook and GitHub; all providers are disabled by default.
- Social registrations trust only a provider-supplied verified email, skip local email verification, and remain inactive until administrator approval.
- Added signed, short-lived OAuth state bound to an HttpOnly browser cookie and persistent provider/subject identity mapping.
- Existing local accounts are never auto-linked solely by matching email.
- New registrations notify administrators when SMTP is configured; administrator approval sends the activation email to the user.
- Added Docker/Kubernetes defaults and `docs/SOCIAL_LOGIN.md` with provider callback and enablement instructions.

## 0.2.0-68

- Auto-save enabled by default, configurable in desktop Settings; manual Save remains available.
- Session Undo/Redo with standard shortcuts.
- Timeline Cut/Copy/Paste/Remove for selected ranges/tracks.
- Fixed selected-track checkbox lookup.

## 0.2.0-68

- Fixed desktop-native save-location chooser by waiting for the pywebview JS bridge instead of silently returning while the bridge is still initializing.
- Import & Separate now requires and opens a native save destination chooser when the destination is a new project.
- Renamed Native settings to Settings and made native detection/session/bridge readiness consistent.
- Grouped Import MTA, Import Audio, Import & Separate, Tracks, Plugins and Mixer into a dedicated collapsed-by-default EDIT / IMPORT / MIX sidebar section.
- Tracks, Plugins and Mixer now perform explicit navigation/focus actions and report when a project/track is required.

## 0.2.0-68

- Portato a 1024 MB (1 GiB) il limite predefinito di import/upload per server, Docker e Kubernetes.
- `MTA_MAX_UPLOAD_MB` resta configurabile in Docker; il wizard Kubernetes configura coerentemente applicazione e Ingress NGINX/HAProxy fino a 10240 MB.
- Le app desktop native hanno ora **Native settings** con limite import/upload configurabile 1–10240 MB, persistente e applicato immediatamente senza riavvio.
- Il limite continua a essere verificato sia sul `Content-Length` sia durante la copia streaming del file, evitando di caricare l’intero upload in RAM.

## 0.2.0-68

- Corretto il secondo errore Android rilevato nel run GitHub Actions 37057175276: il progetto usa dipendenze AndroidX ma non abilitava `android.useAndroidX`.
- Aggiunto `mobile/android/gradle.properties` con AndroidX abilitato e Jetifier disabilitato, dato che le dipendenze del progetto sono già AndroidX.
- Aggiunto test regressivo per impedire la rimozione accidentale della configurazione AndroidX.

## 0.2.0-68

- Il menu contestuale di una traccia include anche `Rimuovi`, per eliminare la traccia selezionata dal progetto.

- Aggiunti input numerici sincronizzati con gli slider del volume per tracce, Inspector, Mixer e Master; valori ammessi da -60 a +12 dB con autosave.


- `Import Audio` ora avvia automaticamente l'import immediatamente dopo la scelta del file, senza richiedere un secondo click.
- `Delete tracks` ora elimina realmente le tracce selezionate dal progetto; non richiede più una selezione temporale.
- `Delete song segment` mantiene invece il comportamento di cancellazione intervallo/ripple sulla timeline.

- Added full multi-user authentication with a responsive photographic login based on the approved mockup.
- Added self-registration with mandatory email confirmation and administrator approval before activation.
- Added `admin`/`user` roles, admin-only user management, activation/deactivation, role changes and deletion safeguards that preserve at least one active administrator.
- Added optional RFC 6238 TOTP with in-app secret generation and QR-code enrollment.
- Added user profile management, email-change reverification/reapproval, password change and email password reset.
- Added SMTP/STARTTLS/SMTPS configuration with optional credentials, connection test, confirmation mail and activation notifications to all active administrators with confirmed email addresses.
- Added persistent SQLite authentication/session data on the application volume and HttpOnly/SameSite application sessions while keeping HTTP Basic only for operational compatibility.
- Updated Docker Compose and Kubernetes bootstrap configuration to include the administrator email.
- Preserved the previous Python 3.14/Trixie, CPU-only PyTorch, CI security, Kubernetes TLS and MTA reverse-engineering work.

# Changelog

## 0.2.0-13

- Fixed Ruff 0.16.9 CI failures in the standalone Kubernetes wizard: removed an unused import and documented narrow S310/S606 suppressions for the hard-coded HTTPS self-update URL and intentional shell-free self-restart.
- Kept the Python 3.14 production/CI baseline while making dependency resolution deterministic on GitHub-hosted runners.
- Pinned Pydantic to 2.12.5 (pydantic-core 2.41.5), a stable Python 3.14-compatible pair, after the 2.13.5/core 2.46.5 combination intermittently failed to resolve in the Quality job.
- Added a Dependabot guard against Pydantic 2.13.x/2.14.x until the CPython 3.14 production gate is deterministic.
- Moved the production and CI baseline from Python 3.11 to Python 3.14, absorbing the previous Docker Dependabot PR.
- Updated NumPy to 2.5.3 and aligned the dependency policy with the Python 3.14 baseline, absorbing the remaining grouped Python dependency PR intent.
- Split Kubernetes assets into Namespace, PVC, Deployment and Service resources and added Kustomize base/overlays.
- Added NGINX Ingress and HAProxy Ingress examples.
- Added a standalone standard-library Kubernetes manifest wizard with self-update, automatic restart after update, persistent last-used values, nodeSelector support, StorageClass selection and local Kustomization output.
- Added wizard generation tests and security notes for locally persisted/generated credentials.


## 0.2.0-10

- Resolved the two open Dependabot proposals without changing the 0.2.x Python 3.11 support baseline.
- Incorporated compatible dependency updates from PR #4: Demucs 4.1.0, pytest 9.1.1, pytest-cov 7.1.0, Ruff 0.16.9, Bandit 1.9.4, pip-audit 2.10.1 and WeasyPrint 70.0.
- Kept NumPy at 2.4.6 because NumPy 2.5.x requires Python >=3.12.
- Kept the production base image on python:3.11-slim-bookworm instead of PR #1's Python 3.14 proposal.
- Added Dependabot ignore policy for Python 3.12+ Docker bases and NumPy 2.5+ while the 0.2.x compatibility policy remains Python 3.11.
- Fixed Gitleaks pull-request scans by checking out full Git history in the security job.
- Updated the Docker stem-plugin smoke import for Demucs 4.1, which no longer requires torchaudio for inference.
- Retained setuptools 84.0.0 / wheel 0.48.0 runtime hardening for the previous Trivy findings.

## 0.2.0-9

- Fixed the current Trivy production-image gate by upgrading runtime packaging tooling to `setuptools==84.0.0` and `wheel==0.48.0`.
- `setuptools 84.0.0` vendors `jaraco.context 6.1.0` and `wheel 0.46.3`, eliminating CVE-2026-23949 and CVE-2026-24049 reported against the base image's `setuptools 79.0.1`.
- Added a Docker build-time import smoke test for core runtime modules and optional Torch/Torchaudio stem-separation modules.
- Retained all 0.2.0-8 MTA reverse-engineering, security, documentation and CI improvements.

## 0.2.0-8

- Consolidated the GitHub Actions fixes for Python 3.11 and current action tags, including Trivy `v0.36.0`, CodeQL v4 and NumPy 2.4.6.
- Hardened XML parsing with `defusedxml` and replaced silent exception swallowing with explicit logged fallbacks.
- Upgraded proprietary MTA analysis with a corpus-verified 256-byte shared keystream recovered from COLORS.
- Decoded COLORS normal records as four decimal centisecond digits plus three decimal progressive highlight-position digits and minute carry; special sentinel values remain read-only/undocumented.
- Added corpus-verified LYRICS/CHORDS decoding with monotonic minute/centisecond timing and XOR-0x30 text/chord recovery.
- Added MIDITK decoding to byte-exact Standard MIDI plus MIDI header, PPQ, track-length, tempo and Marker meta-event analysis.
- Added `docs/MTA_FORMAT_RESEARCH.md` and `docs/PROJECT_ARCHITECTURE.md` and updated online/PDF manuals with current compatibility boundaries.
- Retained conservative write policy: unknown fields and proprietary writer semantics are preserved, not synthesized, until hardware round-trip validation is complete.

## 0.2.0-6

- Fixed current GitHub Actions references and Python 3.11 compatibility.
- Added `defusedxml` for untrusted XML parsing and explicit exception logging/fallbacks.
- Corrected Python 3.11-incompatible test syntax reported by Ruff.

## 0.2.0-5

- Added verified structural parsing for stock M-Live SYL/XML attachments.
- Added read-only LYRICS/CHORDS decoding and initial COLORS keystream/timing analysis.
- Added MtxInfoData parsing and conservative EBML FileData attachment fallback.

## 0.2.0-4

- Added Delay, Lexicon-style Reverb, Room/Ambience, 32-band Graphic EQ, Amplify, Stereo Imager, Maximizer/Loudness, Mastering Wizard, De-Noise and Crackling Cleaner.
- Added factory presets and persistent validated user presets for every insert processor.
- Added parameter editor and reversible Auto Mix with Balanced/Studio/Live/Gentle profiles.

## 0.2.0-3

- Removed the MTA8/MTA16 slot limit from the editing/mixing workspace.
- Added explicit MTA output-slot mapping and many-to-one track merge during export.
- Added independent WAV/MP3/FLAC track export and FLAC master export.
- Added the first Matroska/SYL reverse-analysis reports and binary diff tooling.

## 0.2.0-2

- Added the photographic DAW interface, mixer and master preview.
- Added direct MP3/WAV track import/replacement and Demucs stem separation.
- Added per-track/master insert chains and WAV/MP3 master export.

## 0.2.0-1

- Added production CI/CD, CodeQL, Dependabot, SBOM/provenance and security gates.
- Added default-on authentication, request-integrity checks, upload/path hardening and non-root container deployment.
- Added integrated user/admin online and PDF documentation.

## 0.2.0

- Added non-destructive clip editing, arbitrary range deletion, ripple editing, track import/replace/sync, history/timeline events and initial MTA import/export preservation model.

## 0.1.0

- Initial FastAPI/FFmpeg MTA8/MTA16 web editor prototype.

## 0.2.0-68

- Kubernetes wizard: HAProxy ingress now always emits `kubernetes.io/ingress.class: haproxy` in addition to `spec.ingressClassName: haproxy`.
- Reverse-engineering notes: confirmed the 181392 ns Matroska timecode scale, 40 MP3 frames per Cue interval, exact 320 kbit/s frame/SimpleBlock sizing, and frame-major per-track interleaving evidence.

## 0.2.0-73
- Fixed macOS ARM native project dialogs so interacting with/selecting the default project name cannot be interpreted as a backdrop action.
- Native filesystem actions now wait for the pywebview `pywebviewready` event and tolerate slower WebKit bridge injection (up to 15 seconds), fixing transient “Bridge nativo non ancora disponibile” errors.
- New Project and Import & Separate modal actions now use explicit non-submit buttons and protected modal event propagation.

## 0.2.0-113
- Fixed Import & Separate current-project type detection in the UI.
- Native desktop Demucs splitting now uses the upstream Demucs model resolver/cache directly instead of the MTA model server.
- Re-importing an already stored source now reuses the existing project file and starts separation even when the source is not on the timeline.

## 0.2.0-r181

- Lyrics + Chords + Markers editor: moved per-event Modify/Enable-Disable/Merge/Delete/Restore actions to context menus for lyric lines, individual chords, and markers.
- Added context-menu marker creation with required start time and optional end time.
- Lyric line timestamps are directly clickable/editable with m:ss.mmm / mm:ss.mmm validation.
- Updating lyric times preserves manual chord anchors.

## 0.2.0-r183
- PDF Lyrics + Chords + Markers preview rebuilt as native-WebView-safe HTML preview.
- Fixed chord styling when a PDF page begins with a chord row.
- Granular chord anchors: line start/end, word/syllable, and chord-to-chord sequences.
- Editor preserves scroll position after operations; added cut/copy/paste and undo/redo.
- Moved Dividi qui to the word context menu and compacted editor rows/timestamps.
- Added saving-in-progress overlay and close protection while persistence completes.

- Edit Lyrics / Edit Chords / Edit Markers now open scrolled to the event nearest the current timeline/playhead position, without moving the transport.

## 0.2.0-r245
- Chords: refresh starts after project PUT, without waiting for native synchronization.
- Fast WAV patch updates only affected samples and waveform envelope bins.
- Serialized generated-Chords refresh requests to prevent overlapping operations.

### 0.2.0-r295
- Prevent recursive MutationObserver localization attribute writes that can lock the native WebView on sidebar clicks, even without a project.
- Translate changed title/ARIA attributes only when their values differ, without rewalking the entire subtree.


### 0.3.0-r130: experimental native parallel dry/wet latency alignment
New native/audio_core/vst3_parallel_mix.hpp aligns dry PCM to plugin-declared latency, supports wet/dry mix and fault-driven latency-aligned dry output; tested in C++20. Experimental isolated primitive, NOT connected to production playback. native_host_ready remains false.


### 0.3.0-r131–r135: five native functional preparation cycles
- r131: optional strict negotiated PCM quantum/channel validation on experimental SPSC playout callback.
- r132: coverage for deterministic latency-aligned dry fallback during wet timeout.
- r133: composed IPC lookahead + plugin algorithmic latency budget and per-path alignment decisions.
- r134: bounded sample-offset MIDI and automation packets with epoch/sequence validation (worker preparation only).
- r135: bounded exponential restart policy for control thread, with long-run dry callback regression.
All remain experimental isolated prerequisites; production playback, actual VST3 MIDI/automation forwarding, full fault restart orchestration and platform acceptance are not implemented. native_host_ready=false.

## 0.3.0-r174 — AI Arranger foundation
- Added extensible ACE-Step 1.5 and DiffRhythm 2 model catalog, eight musical style presets, typed request validation, and authenticated project-scoped planning endpoints.
- Added optional preserve-structure and preserve-chords constraints sourced from existing, active project markers and chord events, with explicit best-effort warnings.
- Added non-destructive project/selected-track/timeline-range planning; generation fails closed until a verified inference backend is installed.
- Synchronized Windows/Android/iOS revision metadata and retained `native_host_ready=false`.

- r182: add AI worker readiness endpoint, fail-closed status and native stereo pan ramp; retain native_host_ready=false.

- r183: bounded fail-closed AI worker capability handshake and native peak/RMS PCM metering (experimental).

- r207 (uncommitted update): added Linux direct-child process CPU/disk I/O meter and authenticated JSON-plan executor, with persistent job outcomes. Dedicated process-tree/GPU/retained-storage instrumentation and full remote audio upload support remain pending; do not use for final resource billing.

- r207 (uncommitted refinement): Separate transient process disk I/O from
  billable persistent storage, support per-user persistent directory snapshots
  and GiB-hour integration, exclude caches, previews and temporary files,
  and test prevention of transient I/O charges.

- r207 update: automatic per-user persistent-storage sampling, exclude temporary files and unknown long sampling gaps from billed storage.

- r207 cumulative accounting hardening: require delegated cpu/io controllers and recursively empty job cgroups before accepting CPU/I/O metering; reject missing cgroup.events occupancy signals; add regression coverage. GPU billing still requires per-job hardware telemetry validation.

- AI billing: reject period closure for positive persistent-storage tariffs without a configured sampler; preserve strict sample-gap checks.

- r207 cumulative: Added an administrative billing-readiness endpoint and
  dashboard preflight for cgroup v2, worker, persistent storage and GPU sensor
  completeness. Paid GPU billing remains blocked until genuine job-specific
  hardware telemetry is integrated and verified.

- r207 cumulative hardening: allow bounded, validated per-model metadata with
  authenticated remote WAV submissions, without client-supplied filesystem or
  executable paths; add regression tests. Universal native endpoint migration
  remains pending and must not be marked complete.

- r207 (uncommitted, cumulative): Added opt-in concrete server subprocess adapters for Whisper lyrics, chords, Demucs stems, DrumSep ONNX, SAM Audio and configured vocal separation with validated JSON/WAV artifacts. Added an authenticated concurrent multi-user benchmark mode to the ACE-Step wizard; clarified native remote-route acceptance and remaining legacy routing gaps.

### r207 cumulative — remote native transport contract
- Added HTTPS-only remote AI transport with per-user bearer authentication,
  bounded WAV uploads and WAV/multi-artifact ZIP responses carrying job IDs.
- Fail explicitly on remote network errors; never trigger local AI fallback.
- Added regression tests for authentication transport, disallowed paths,
  unsupported workers, missing job IDs and offline servers.
- Historical desktop AI views still need explicit wiring to remote mode.

### r207 cumulative — billing reconciliation audit
- Added read-only, admin-authenticated reconciliation API that enumerates per-job accounting gaps, unsafe billing-boundary overlaps, invalid/missing metering, and storage sampling coverage without exposing bearer tokens.
- Added regression tests for cross-user isolation, priced GPU telemetry absence, failed jobs, boundary crossing, and persistent-storage sampling gaps.
- Hardware GPU attribution, full-system native acceptance and real concurrent load measurements remain outstanding; do not certify production GPU billing from this audit alone.

### r207 — atomic accounting closure follow-up
- Protect eligibility checks, pricing reads and snapshot insertion inside one SQLite `BEGIN IMMEDIATE` transaction.
- Reject retroactive job creation and finalization that intersect immutable billed intervals.
- Add concurrent four-thread billing-closure and late-insertion regression coverage.
- Refresh legacy test fixtures to honor the authorized worker allowlist and GPU sensor provenance.

### r207 — closed-invoice integrity and concurrent benchmark reconciliation (cumulative)
- Add read-only admin audit of saved invoice totals, rows, corrupt snapshots and overlapping closed periods, without retrospective repricing.
- Allow the concurrent benchmark to verify per-user job ownership, completion and measured CPU usage directly against the server-side SQLite ledger, without including access tokens in results.
- Add parametrized no-local-fallback tests for all seven native remote AI kinds and ledger audit regression tests.
- Hardware GPU measurement and native OS end-to-end certification remain pending.

### r207 refinement — immutable invoice audit hardening (2026-10-11)
- Closed-invoice integrity audit now rejects non-integer, negative, boolean, non-finite and string-encoded micro-unit totals and row charges rather than coercing malformed JSON.
- Validates snapshot period identity against the immutable invoice record; preserves compatibility with legacy snapshots that omit a user ID.
- Added regression tests for corrupted monetary values and snapshot identity. The r207 test selection passes (157 tests; 4 FastAPI deprecation warnings).
- Hardware-dependent GPU metering, multi-user GPU/CPU/storage measurement and native OS end-to-end certification remain pending.

- r207 refinement (uncommitted): add dry-run-first, transaction-safe orphaned AI job recovery for server crashes, retaining fail-closed resource accounting and idempotent finalization; add negative and lifecycle tests.

- r207 cumulative refinement: add durable per-user idempotency claims for JSON and WAV AI execution; native remote transport sends a unique request key and supports explicit reuse for operator-driven retries. Duplicates and concurrent submissions never launch a second inference under the same key. Preserve ambiguous claims after crashes rather than silently retrying or charging twice. Add multi-threaded regression tests.

- r207 refinement (uncommitted): add a per-user authenticated request-status API (`GET /api/ai-jobs/request-status/{request_key}`) allowing clients/operators to inspect admitted, completed, and failed idempotent requests after network timeouts without resubmitting inference or exposing request fingerprints. Extend status lifecycle/isolation tests. 172 r207 tests pass; broader CI run was interrupted by execution limits, and Ruff was not installed in this environment. Result artifact replay remains unavailable; hardware/native E2E tests remain outstanding.

### r207 refinement: secure AI result replay and child-process cleanup
- Add optional per-user AI result retention and owner-authenticated WAV/ZIP recovery endpoint for responses lost after a timeout, without starting or billing a second inference.
- Verify cached outputs by SHA256 and TTL; require an operator-specified private storage directory.
- Kill the worker process group after direct-child completion to limit leaked subprocesses.
- Add result-cache isolation/tampering tests; maintain r207 version and cumulative changes.

- r207 refinement (uncommitted): add conservative AI result cache expiry cleanup,
  explicit owner-authenticated native result recovery client, and no-local-fallback
  regression tests; 180 r207 tests pass in the development environment. Hardware
  GPU and full CI validation are still outstanding.
- Align the legacy ACE-Step deployment test with the current mandatory HTTPS
  and bearer-token policy for remote hosts; do not relax runtime validation.
- Certification status: targeted r207 and ACE-Step deployment checks green;
  general test suite did not complete within execution budget, so full CI
  and end-to-end native validation remain unverified.

### 0.3.0-r207 refinement addendum (no revision increment, 2026-10-11)
- Passed Ruff and configured CI Bandit checks, and added explicit parameterized SQL branches for per-user accounting/billing queries.
- Fixed native remote transport's advertised JSON result type; preserved HTTPS and no-local-fallback invariants.
- Added per-user token/event and invoice/tariff filter regressions; focused r207 suite: 186 passed.
- Full CI/coverage and medium-severity security triage remain open, as do native hardware/GPU validations.

### r207 — Further security refinement (unchanged revision)
- IT: trasporto HTTPS con blocco downgrade su redirect, loopback come host web predefinito, 6 test di sicurezza aggiuntivi; Bandit con soglia media e Ruff superati. Il problema esterno MoviePy/Pillow nell'ambiente locale resta aperto.
- EN: HTTPS-only redirect protection, loopback default web bind, six new security tests; medium-threshold Bandit and Ruff checks pass. The unrelated local MoviePy/Pillow environment mismatch remains unresolved.

### r207 — Optional HTTPS web installer refinement (uncommitted follow-up)
- Optional TLS for the MTA Linux web server with existing or self-signed X.509 certificates, wizard persistence and secure key permissions; HTTP remains the default.
- HTTPS installer regression tests, route and worker regression tests, and additional accounting/billing API coverage tests for CI.
- HTTPS web opzionale nel wizard Linux con certificati esistenti o self-signed, persistenza e permessi sicuri; HTTP resta il default.

### 0.3.0-r207 — LXC cgroup and pending email security refinement
- The Linux wizard now installs a delegated cgroup v2 launcher, using a web
  process leaf and per-job accounting subtree with CPU/I/O controller gating.
  Unsupported environments start the web UI with metering disabled, not a
  fabricated usage measurement.
- Updating an account email preserves the verified old address, password and
  active status until the new mailbox is confirmed; confirmation promotes the
  pending address atomically. SMTP-unconfigured state is reported in the
  account-update API, and pending email is exposed to the account owner.
- Added regression tests. GPU usage remains nonbillable without validated
  per-job hardware sensors; real Proxmox LXC deployment validation remains pending.

- Maintenance r207: introduce persistent diagnostic/billable job distinction, exclude diagnostic jobs from charged totals, backfill known historical accounting smoke tests, and strengthen installer remote-commit checking, source preflight, local change protection and health rollback.
