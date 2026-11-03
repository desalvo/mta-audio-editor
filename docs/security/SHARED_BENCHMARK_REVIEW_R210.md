# Shared projects, percussion benchmarks and SAM retirement: security delta review

Review date: 2026-11-03. Baseline: `f235f4c3ca67af72006bfc6262474ccb0ff0a705`. This review covers the added collaboration, selected-clip join, direct-percussion validation and retired-separator boundaries. It does not authorize deployment, billing activation, a model checkpoint or a claim of professional audio quality. The four inventory checkers and scanner rules remain unchanged.

The final source-bound census, exact finding identities and source hashes are recorded in `docs/validation/r210/shared-benchmark/review-result.json`, `source-snapshot.json` and the unsuppressed `bandit.json`. Their generation follows runtime freeze and explicit boundary review. A hash refresh alone is not a finding disposition.

## Finding review

The reviewed final design contains 324 application Python sources and 181 Bandit findings: zero HIGH, 21 MEDIUM and 160 LOW. Relative to the preserved 183-finding baseline, six findings disappear with the actual deleted SAM/singer executor code, and four genuinely new LOW findings are reviewed below. 155 finding identities remain exact; 22 moved locators or explicitly reviewed context updates preserve their previous dispositions. Existing dispositions remain unchanged, including repeated AST occurrences; moved line numbers are paired with their previous normalized code rather than approved indiscriminately.

| New finding | Disposition | Reviewed boundary and evidence |
| --- | --- | --- |
| `percussion_metrics.py`, B105, `technical_pass: False` | False positive | A boolean integrity result is not a password. Invalid or unreadable audio fails closed. Bounded metric tests exercise this path; a technical result cannot mint model rights or human quality approval. |
| `project_collaboration.py`, B404 | Reviewed trust boundary | The import supports only a fixed synchronous FFprobe metadata parser inside authenticated attachment upload. There is no new generic command or model executor. |
| `project_collaboration.py`, B607 | Reviewed trust boundary | Literal `ffprobe` resolves via the operator-controlled service PATH. API callers cannot choose its executable or arguments. This trusts the installed native parser and PATH; it is not a native-code sandbox. |
| `project_collaboration.py`, B603 | Reviewed trust boundary | Shell-free fixed argv receives a server-generated private UUID filename. Uploads are capped at 20 MiB and checked against owner quota. The parser permits file/pipe protocols, uses an 8 MiB probe bound, five-second analysis and 15-second timeout. Non-audio, malformed, unsupported or overly long media is rejected before publication. |

The existing B107 at `native_ai_routing.configure` has a changed enclosing body because a retired-kind rejection is added first. Its previous disposition remains justified: an empty default does not supply a credential; remote mode still requires a nonblank bounded personal token, a validated endpoint and private atomic settings. The new guard rejects SAM/singer configuration before those effects.

The removed findings are SAM/singer subprocess imports and invocations in `ai_unified_adapter.py` and `main.py`. Deletion is recorded as historical resolution, not a reclassification or scanner suppression. The retired worker and compatibility bridge are physically absent. Historical diagnostic and ledger records remain readable.

## Admission and execution ownership

The admission census remains 179 sites: 175 previous occurrences retain their dispositions, four retired entry/process sites disappear, and these four new sites are reviewed individually:

| Site | Disposition | Lifetime |
| --- | --- | --- |
| Benchmark CLI `__main__` | Tracked work | All six prepare/inspection/export operations enter `service_admission.operation` after selecting `auth.DATA_ROOT`. There is no CLI run/create/approve command. An actual selected-root drain test proves refusal before benchmark effects. |
| Collaboration `_db` | Request lifetime | The private discussion DB belongs to a participant request, existing project publication or one admitted maintenance cycle. SQL values are bound; storage paths and media IDs are validated. |
| Collaboration `_validate_media` | Request lifetime | Bounded FFprobe parsing finishes within the admitted upload request; it does not detach or infer. |
| Collaboration maintenance thread | Periodic cycle | The sleeping scheduler is untracked; every actual cleanup/outbox pass has common periodic admission and observes shutdown. SSE requests end within 20 seconds and require fresh admission on reconnect. |

The transport census retains all 32 explicit Python HTTP-client call shapes across 21 files. Existing categories, trust boundaries and verification text are preserved; only exact current locators/source bindings change. Metadata queries do not confer remote model attestation or commercial inference authority.

The complete runtime map binds 575 source files. The final execution census is 817 boundaries: 787 preserved occurrences, seven retired SAM-only executors removed and 30 new entries. Those are one selected-clip join HTTP endpoint, one registered inference call in the benchmark runner, 18 admin benchmark HTTP routes, seven participant collaboration routes, two admin collaboration settings routes and one non-inference FFprobe process. The final generated report records the exact locators; an unclassified delta blocks the gate.

Selected-clip joins use existing authenticated project editing, the cross-process publication lock, validated adjacent clips, capacity checks and atomic rollback. No model operation or usage settlement is introduced. Audio sample and API regressions in `tests/test_timeline_join.py` and `tests/test_timeline_cross_track.py` provide the evidence.

Every benchmark API route requires an active authenticated administrator before effects. Client model IDs select known catalog candidates, never commands or adapters from archive metadata. The queue stores the original authenticated actor; restoration rechecks that actor is an active administrator. The hardcoded adapter requires the active server owner before dispatch through registered, metered inference with current model policy. The cancel route accepts no client job/actor overrides, resolves the stored queue ID under the campaign lock, checks its campaign project ID and operation, and cancels only that original job through the existing queue. Reports read campaign evidence and do not execute a model. This recovered benchmark does not read any resource counters from the ledger: CPU/GPU values that may already exist there, and RAM/VRAM peaks, remain null in the campaign report. The original worker_job_id preserves the link for independent audit; the ledger is not modified and no consumption is invented. Existing model/checkpoint rights controls, cancellation, output checks and registered worker ownership remain authoritative.

## Dataset and campaign archives

ZIP imports are bounded by archive bytes, declared uncompressed bytes, file count and decoded audio working sets. They reject symbolic/special members, unsafe or noncanonical paths, Unicode/control ambiguities, reserved portable names, case aliases and unsupported extensions. Campaign restores accept only regular `.json`, `.md` and `.wav` entries, and guard both the campaigns parent and final directory against symlinks before staging/publication. SHA-256 and finite PCM geometry are rechecked. Invalid imports do not publish a campaign. Seventeen dedicated security cases in `tests/test_r210_shared_benchmark_security.py` exercise names, modes, aliases and the parent-link boundary.

Dataset declarations identify the authenticated importing administrator and record provenance; they are not automated copyright verification. Archive-supplied reviewer identities, professional approvals or verified-rights flags are discarded. Family/split checks prevent duplicate recording families being distributed across train/validation/test. No third-party audio is fetched or redistributed by this change.

Campaign configuration freezes source mode, exact candidate/checkpoint/runtime/pipeline/catalog metadata, input/reference hashes and options. DRUMS and MIX are evaluated separately when both are selected; they are not silently fused. Raw outputs are measured before level-matched listening copies are made. Working-set limits and explicit invalid/unknown states prevent NaN, missing ground truth or unidentifiable bleed becoming an artificial pass. Synthetic controls that reuse a reference are labeled controls, never successful model inference.

Ratings and final approval are bound to current exact result identities and verified output files. Imported ratings are marked unverified; imported final approvals and queue ownership do not become server authority. Reusing or restoring audio does not approve the model. The six real-recording slots remain missing until authorized data is supplied. Professional approval requires a separate explicit human action after the required current listening evaluations.

The offline corpus generator writes original diagnostic data and reports only. It has no server identity, model executor, scheduler or approval authority. Its report keeps neural inference and human approval false. Candidate metadata is pinned by the pipeline hash; executable adapters are selected by a hardcoded allowlist rather than names or commands from that metadata.

## Collaboration privacy and concurrency

All discussion, media, read, leave and stream paths require actual current participants and registered server identities. Administrators who are not participants gain no private dashboard access. Deleted/deleting users and owners are denied; pending mail for revoked/deleted recipients or deleted owners is cancelled. SSE rechecks sessions and membership on each cycle. File responses repeat access checks and use private/no-store/nosniff headers. The final share ending removes media and discussion sidecars; portable export excludes them and portable import ignores supplied sidecars.

Text, filenames, author identity, colors and recipients are bounded or server-derived; the UI uses text nodes and escaped notification content. Attachments use verified image signatures and bounded Pillow dimensions, or the reviewed audio parser. Failed uploads remove their owned temporary data. Media TTL is administrator-configured and expiry unlinks the stored file while retaining the message placeholder until sharing ends.

Mail uses the existing configured SMTP transport and durable per-message/recipient outbox, stable Message-ID and serialized claim. Sending excludes the author and current revoked/deleted recipients, removes subject header line breaks and escapes HTML. Network calls do not hold the edit lock. Recovery is at least once; exactly-once SMTP is not claimed. Tests substitute transport and do not send real email.

Edits publish an atomic revision under the existing cross-process lock. Recipient stale writes are rejected; owner merges require an exact retained base revision. Independent keyed track/clip edits survive; owner priority resolves conflicts on the same changed path. Unkeyed lists remain atomic. Browser dirty state is retained, pending remote state is not applied while the editor is busy, explicit refusal is preserved, and in-flight changes are merged after save. At most one short settlement timer waits while clean/busy; dirty state stops it, callbacks that refuse do not spin, stale pending revisions are cleared and disconnect cancels it. Production-function tests cover the seven final timer cases.

## Limits and final catalog contract

The catalog exposes the current activation boolean, checkpoint revision as version and weight-license status for frontend controls, after administrator authorization. This is presentation metadata only: it does not change rights, core inference, audio request handling or transport authority. The real GET → disable PUT → GET contract test checks the actual API schema.

Evidence is software and fixture based. Reading the available authoritative CPU/GPU ledger counters into benchmark reports is still unimplemented, as are RAM/VRAM peaks; null values are not measured zero. Remaining acceptance includes installed checkpoint inference and real recordings, professional listening, real hardware/GPU accounting, native targets, microphone capture, SMTP and multiple browsers/proxy SSE. Trusted operator PATH and native parsers remain residual boundaries. No RC, financial transition, remote checkpoint attestation or production certification is implied by passing these source gates.
