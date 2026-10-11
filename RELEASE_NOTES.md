## 0.3.0-r195 — Reviewed ACE-Step CI source bundling

Adds ACE-Step v0.1.8 default stable source lock, immutable SHA resolution, weekly upstream release checks with a reviewable update PR, pinned-source CI bundling and artifact integrity tests. Does not yet package a ready-to-run inference runtime or validate generation.

### 0.3.0-r194 — Shared model cache telemetry and reproducible source bundling
- Add authenticated model-cache telemetry to MTA for remote clients, without exposing checkpoint files or internal model API.
- Mount cached models read-only in MTA service, with persistent ACE-Step cache in Docker/Kubernetes.
- Provide opt-in pinned upstream source vendor script (source not embedded in this build because upstream retrieval was unavailable).
- Keep native C++/VST3 experimental, no real inference certified.

### 0.3.0-r193 — Native ACE-Step progress
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
- Native C++20 DC blocker utility with standalone compiled regression coverage (not enabled in production playback).
- ACE-Step output WAV validation and optional `--check-server` loopback probe.
- Model inference is still unverified; `native_host_ready=false`.

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

AI Arranger and Remix can now pass verified source WAV data to trusted external workers through a temporary manifest. Real ACE-Step inference remains unimplemented and unvalidated. Native realtime host remains disabled.

r181: Optional trusted AI worker execution returns validated WAV previews from authenticated Arranger and Remix endpoints. No bundled ACE-Step model or guaranteed musical fidelity. Native C++ soft-clip DSP included; production native host remains disabled.

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

- AI Arranger/Remix modal and authenticated planning routes, covering instrument swaps and auto-remix presets, prompts and preservation constraints. No audio generation until a real AI worker is installed.
- Native C++20 VST3 delay compensation plan exported as `mta_vst3_plan_latency` for control-thread use; realtime host stays gated (`native_host_ready=false`).
- Android/iOS/Windows version metadata synchronized.
- Compiled native C++ shared library; targeted tests passed. Full pytest/coverage inconclusive due local timeout at about 31%; CI must confirm.

## 0.3.0-r175 — Remix planning foundation

- Add Remix with instrument replacement and user-described auto-remix, reusing optional preservation of structure, chords, tempo, melody, and vocals.
- Validate track identities, replacement targets and requests; no artificial or destructive audio output.
- Keep AI generation disabled until real, licensed backends are integrated.

## 0.3.0-r173

Windows metadata now correctly reports Revision 173 alongside its binary file version. The full CI suite must still be confirmed on GitHub Actions.

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

## 0.3.0-r168

- Integrate project insert VST3 checkpoint capture/staging with the experimental control-thread supervisor.
- Protect against plugin switches while capturing and reject stale state on reopen.
- Native production host remains disabled (`native_host_ready=false`).

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

## 0.3.0-r126 — Native ABI v2 negotiation and callback-affine telemetry

- Export immutable negotiated frames/channels/sample rate/queue/lookahead for host setup.
- Expose callback-only bounded playout statistics for integration diagnostics.
- Explicit ABI version bump to 2; test native exports by compiling C++20.
- Telemetry cannot be read concurrently from a control thread; do not enable production audio or set native_host_ready=true.

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

## 0.3.0-r122 — cumulative preactivation native bridge

Real plugin smoke-test now spans the native C ABI and persistent VST3 IPC on Linux, outside DAW playback. This is an integration harness only: the Python worker and userland timing do not meet hard realtime requirements. `native_host_ready=false` remains mandatory.

## 0.3.0-r121 — cumulative native bridge ABI

This early release builds on committed r120. It exposes a testable native runtime C ABI while keeping `native_host_ready=false`. The worker callback is a test processor, not an end-to-end VST3 plugin connection; realtime, MIDI, automation, measured latency compensation, and platform qualification remain blocked.

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

## 0.3.0-r76

Experimental native VST3 playout bridge with preallocated callback-side dry fallback and separate worker-facing block exchange. Includes all unpublished changes since r65. `native_host_ready=false`. The bridge is not yet connected to realtime playback.

## 0.3.0-r75

Experimental native, fixed-capacity SPSC PCM block queue with sequence metadata and C++ concurrency regression tests. Includes uncommitted r65–r74 work. `native_host_ready=false`.

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

## 0.3.0-r50 — VST3 multi-rate test compatibility

- Fix two obsolete tests reported by GitHub Actions: processing configuration and transport musical position now use the negotiated `pcmSampleRate` rather than requiring 48 kHz.
- Keep the multi-rate audio implementation unchanged.
- Previous CI run: 1105 passing tests, 2 obsolete assertions failing, coverage 70.12%.

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

## 0.3.0-r37
New experimental `python -m native.vst3_probe.render_wav_cli SOURCE DEST --probe EXE --insert VST3_PATH CID` interface for offline VST3 WAV rendering. Invalid timeouts and empty insert chains now fail before execution. Realtime remains disabled.

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
Native offline VST3 PCM multi-block rendering supports variable-length mono/stereo with bounded buffers, partial last blocks and per-insert subprocesses. Not realtime-ready; no full MIDI/automation routing or latency compensation in native chain.

## 0.3.0-r32
Real VST3 offline serial PCM adapter, bounded mono 48k/512x128 sample buffers and fail-closed subprocess handling. Does not enable realtime playback, generalized latency compensation or VST3 stereo/MIDI chains.

## 0.3.0-r31
Offline serial-insert render graph with deterministic multiblock scheduling and latency/tail flush. Tested with fake DSP processors; SDK probe remains separate, and real plugin adapter/realtime callbacks are NOT yet implemented.

## 0.3.0-r30
Offline VST3 graph timing toolkit: validated plugin latency and tail budgets; compensation of rendered streams, deterministic parallel-stem alignment and mixing. Not activated in realtime playback.

## 0.3.0-r29
- Track names now update instantly in Tracks and Mixer; mixer renaming commits on Enter or blur and cancels on Escape.

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

# MTA Audio Editor 0.3.0-r25

- Native VST3 offline diagnostic: 16 sequential blocks with deterministic non-silent input and measured output energy/peak.
- Steinberg ADelay reference plugin end-to-end acceptance test, integrated in Linux SDK CI job.
- Input buses correctly marked non-silent, output buffers cleared between blocks, bounded untrusted diagnostics.
- No realtime integration: further compatibility and performance gates remain open.

## 0.3.0-r25

Isolated VST3 probe: 16-block 440 Hz deterministic signal processing; per-block buffer clearing, bounded output energy and non-finite diagnostics. This remains experimental; no realtime integration or validated MIDI/automation/latency compensation.

## 0.3.0-r24

- Added SDK-built isolated VST3 single-block offline smoke-test, explicitly opt-in.
- Bounded silent audio bus buffers, cleanup and finite-output diagnostics.
- No audio-engine integration or realtime plugin support.

## 0.3.0-r23
- Fixed real-SDK VST3 probe linking using official MIT SDK IID implementation units; build validated locally on Linux x86_64.
- SDK-enabled plugin processing, GUI and bus activation remain experimental and disabled in the playback engine.

## 0.3.0-r23
- Fixed real-SDK VST3 probe linking using official MIT SDK IID implementation units; build validated locally on Linux x86_64.
- SDK-enabled plugin processing, GUI and bus activation remain experimental and disabled in the playback engine.

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

- Added opt-in isolated VST3 IComponent lifecycle diagnostic (--lifecycle CID): initialize with null host context, terminate only after successful initialization, always release.
- Kept the previous create-only mode and production playback untouched.
- Some plugins reject a null host context; this diagnostic is not a realtime-host certification.

## 0.3.0-r10

- Optional VST3 SDK-backed audio-component instance creation diagnostic by exact CID; release immediately, no playback activation.
- Validate instance creation request and report results independently of factory enumeration.
- Keep all realtime VST3 processing, GUI, MIDI and automation experimental and disabled.

## 0.3.0-r9

- Added bilingual VST3 manuals (Markdown and PDF) with the exact existing user manual cover page.
- Hardened untrusted native VST3 class metadata against duplicate CIDs and control characters.
- Kept existing playback/rendering unchanged.

## 0.3.0-r6

- Compliance: archive scanner for source/release ZIP and TAR; rejects unreviewed bundled VST3/AU/AAX and traversal paths.
- Packaging behavior unchanged; native audio host remains experimental.

## 0.3.0-r2

- Added transactional native C++20 mono-to-stereo constant-power pan mixer with input validation.
- Preserved Python audio backend and existing VST3 offline path; new mixer primitive is opt-in only.
- Updated Android, iOS, and Windows revision metadata.

## 0.2.0-r302

- Added opt-in compiled PCM accumulation primitive for future native real-time mixer; no changes to current playback engine.
- Tests cover buffer validation and equivalent portable fallback.

## 0.2.0-r301

- Per-category vector icons for insert setup panels, including VST3.
- Optional C++ PCM gain routine; existing Python processing remains default.

## 0.2.0-r300

- Experimental Linux x86_64/arm64 Debian/RPM workflows.
- Optional portable compiled C++ PCM metering library with Python fallback.
- Native Settings VST3 plugin discovery/status and rescan.
- Existing audio engine and APIs unchanged to minimize regressions.
- Complete native VST3 hosting, MIDI, realtime audio, plugin GUIs and compiled web backend NOT YET implemented.

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
- Select/Split/Range/Ripple and track selection no longer rerender the entire project.

## 0.2.0-r292 — Insert setup button legibility

- Explicit readable colors and native WebView text-fill for Save preset & apply, Apply custom and Cancel in insert setup dialogs.

## 0.2.0-r290
- Keep the sticky Chords lane fully transparent: only chord labels appear over the first track, without the dark band. Chord drag/edit and marker behavior are unchanged.

## 0.2.0-r289
- BPM context menu: Manual BPM sets the musical tempo without changing audio playback speed; Reset BPM restores the original detected tempo and original speed.
- Tap Tempo sets manual BPM. Direct input continues to change playback speed.
- Original detected BPM is persisted independently from the musical reference tempo.

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
- Stabilize the asynchronous garbage-collection regression test on GitHub Actions without changing production cleanup behavior.

## 0.2.0-r282
- Compact transport header, sidebar branding, mixer-channel Insert controls.

## 0.2.0-r281

Reduced UI latency with projects containing many audio tracks and stems. Switching the embedded Lyrics/Chords/Markers tab and revealing Plugins no longer triggers a complete timeline render.

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

## 0.2.0-r276 — Singer separation and GitHub CI coverage fix

- Add an experimental SAM Audio multi-singer mode (2–8 singers) to new-song and existing-track stem workflows.
- Each singer receives a solo positive time-span reference; all other singers' reference spans become negative anchors, as supported by SAM Audio.
- Extract all singers or only one selected singer. Song-relative references are validated, and generated tracks begin at timeline offset zero.
- Keep separate singer names, selected model, and last selected singer target; retain existing WAV/FLAC project storage, MTA export and percussive separation workflows.
- Fix the CI `scipy` ModuleNotFoundError: install both SciPy and SoundFile in base/runtime requirements, including the test image.
- Add test coverage for real DSP/ONNX framing, the SAM CLI temporal anchors, singer reference validation and selective track replacement, keeping the 70% coverage gate unchanged.
- No model weights or Hugging Face credentials are bundled. SAM inference with licensed checkpoints and overlapping singers still needs testing in the native runtime.

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

## 0.2.0-r261

- Fixed native backing-vocals AI splitting failures caused by missing or mismatched torchvision::nms C++ operators. Added dependency pins, package collection and build-time smoke checks.

## 0.2.0-r260

- Removed the standalone Project sidebar shortcut; retained Project / File and existing project commands.

## 0.2.0-r259 — model management, sidebar preferences, bilingual UI

- Central model-manager lists Demucs and backing-vocal models, including their filesystem paths and download/delete commands.
- Sidebar sections remember their open/closed state globally across projects.
- Additional IT/EN translations for vocal separation dialogs, download and status messages.
- Background macOS multiprocessing workers request a no-Dock activation policy.

## 0.2.0-r258
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

## 0.2.0-r254
- Fix visible download button for backing-vocal AI models.
- Surface the backing-vocal separation method while processing.
- Include audio-separator CPU dependency in macOS Intel native builds and explain missing engine.

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

## 0.2.0-r248
- Piano / Chord Lab falls back to a draggable and resizable in-app detached window when popup permission is unavailable.
- Enlarged Show Lyrics/Chords/Markers icons fill compact 38px toggle buttons, preserving title tooltips and aria-labels.

## 0.2.0-r247
- Compact icon-only New project, Open, Save, Save as, Setup and Export header actions with accessible labels/tooltips.
- Collapsed-by-default View/Vista menu: Lyrics, Chords, Markers, Piano / Chord Lab, Tracks, Plugins, Mixer.
- Removed redundant Lyrics/Meta and Piano header buttons.

## 0.2.0-r246
- Metronome: standard/zones/adaptive modes and persisted sensitivity.
- Context refresh for click and generated chords; markers overlay and icon toggles.
- Atomic staged metronome WAV replacement.
- Zone refresh currently falls back to atomic whole-track render.

## 0.2.0-r245

- Fix macOS Intel x86_64 CI dependency resolution: librosa 0.11.x with NumPy 1.26.4, while using librosa 1.0.x on other platforms.
- Keep the preceding r243 Chord Lab features unchanged; align Android, iOS, and Windows revision metadata.

## 0.2.0-r243

- Real 2-octave piano keyboard layout (C3–B4) with 7 white and 5 black keys per octave, correctly spaced E–F/B–C boundaries and narrower keys.
- Piano / Chord Lab detachable into a movable, resizable native browser window with ↗, synchronized notes and presets. Popup close restores the docked panel.
- Left-edge panel resizer correctly adjusts the left boundary in the mixer grid.
- Most-used chord suggestions rank project-local manually entered recent chords ahead of raw frequency; recency is stored with the project.
- No changes to the audio engine or other existing project features.

## 0.2.0-r243

- Fix Android AGP 9.4.1 compatibility: GitHub Actions Gradle 9.6.0 (formerly 9.3.1).
- Restore macOS x86_64 Python 3.12 known working NumPy 1.26.4, Numba 0.61.2 and llvmlite 0.44.0 to avoid missing LLVM while preserving other r241 updates.
- Update version metadata and pinned toolchain compatibility tests.

## 0.2.0-r241
- Reconciled dependency PRs #10–#15 and adjusted Android/macOS Intel regression tests.
- Android Gradle Plugin 9.4.1, PyMuPDF 1.28.2, Ruff 0.16.10, Numba 0.68.0, llvmlite 0.50.0, NumPy 2.5.3 (macOS Intel), librosa 1.0.x, SoundFile 0.14.x and PyYAML 6.0.3+.
- Preserves all r240 editor behavior; macOS Intel/native build compatibility must be validated on CI runners before production release.

## 0.2.0-r240
- Timeline Chords: single click selects exclusively, Ctrl/Cmd+click toggles additive selection, clicking outside clears the selection.
- Preserve chord drag and double-click inline editing without replacing captured DOM nodes.


## 0.2.0-r239
- Timeline chord inline editor: close/save X and reliable Enter commit.
- Lyrics/Chords/Markers panel: batch disable, re-enable and delete for multi-selection.
- Open Recent: deduplicated by bound project path and capped at 15 entries.
# MTA Audio Editor 0.2.0-r238

- Piano / Chord Lab dock beside Mixer with live keyboard, chord presets and Shift+click chord recognition.
- Resizable/scrollable panel with persistent visibility and width.

# MTA Audio Editor 0.2.0-r237

This revision fixes chord-extraction defaults and modal sizing, makes selected-range text/music extraction automatic, and adds timeline Chord batch selection/actions with visible shortcuts.


### 0.2.0-r295
- Fix sidebar and Settings freezes with no project open, caused by repeated localization attribute mutations.


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
Initial read-only AI Arranger planning APIs: `GET /api/ai-arranger/catalog`, `POST /api/projects/{pid}/ai-arranger/plan`. `POST /api/projects/{pid}/ai-arranger/generate` explicitly returns HTTP 503 until inference is implemented. Structure and chord preservation are best-effort instructions, not verified generation constraints. No model weights bundled or downloaded.


### r182
Added AI worker status endpoint (explicitly not a proof of inference readiness), hardened output validation and C++20 stereo pan ramp. Real ACE-Step generation and production realtime validation are still pending.

### r183
AI worker model-capability handshake with short timeout and no inference-readiness claim; native C++ peak/RMS meter. AI audio generation and VST3 realtime activation remain unverified.
