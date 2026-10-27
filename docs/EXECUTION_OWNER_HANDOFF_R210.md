# Active execution owner and source lifecycle — 2026-10-26 — PRE-RC

Resume committed baseline **9fc85ce79bee9871696dea9396565395a415aa72** plus the existing cumulative uncommitted patch. The patch now contains both the subscription-evidence workflow and this executor continuation. User commit is deferred. No GitHub/server/provider mutation, commit, staging, push, tag, release or intermediate ZIP. **23/42 original criteria (54.8%),0/7 whole macroareas; RC false;switching disabled.** Read `RC_FINAL_WORK_QUEUE_R210.md` for the remaining integrated exits. Do not restore an older archive or repeat the verified baseline.

## Completed dispatch and source-preparation path

Previously a nonempty `current_job` context allowed nested global execution to reuse its queue slot without checking the durable owner/state again. Server source conversion similarly trusted any stored positive actor, even if the context named an inactive row. These were missing runtime checks, not an externally authenticated user-ID override API.

`ai_global_execution.active_owner()` now requires an existing **running** durable queue row, a positive exact integer actor, the current scheduler PID and matching process incarnation. Linux/Windows unknown incarnation is rejected consistently with the scheduler's admission rules. An expected actor must match exactly. Missing, unstarted, terminal, foreign supervisor/actor and cancelled rows cannot authorize another stage. No owner is inferred from a project, a stale context variable or an old ledger display record. Same-owner nested kinds still share one FIFO slot and each registered stage retains its own licensing/ledger boundary.

The public registered worker route rechecks before nested reuse; the inner dispatcher rechecks again before either local resolution or pull routing. This covers an owner change after outer admission as well as initial mismatch. Server `identity()` uses the same durable check before source preparation. An independent real process cannot reuse its live parent's scheduler context. These checks neither transfer a worker claim nor permit automatic replay.

`run_metered_process` now rejects cancellation or a failed cancellation probe **before Popen**. The native no-wait4 fallback likewise checks before launching its worker. Existing cancellation during execution still terminates/reaps through the original supervisor. The native fallback test simulates that branch on Linux; it is not Windows/macOS installed-runtime evidence.

Server FFmpeg preparation previously used unbounded `subprocess.run` before model admission. It now:

- validates the actual engine and current model policy before preparing input;
- uses the existing no-shell process-group/wait4 supervisor with no stdin, cancellation and the configured inference timeout;
- checks original active queue ownership during preparation and before dispatch;
- limits generated source size, rejects empty/oversized/failed preparation and passes only the remaining wall-clock budget to inference;
- never enters the model or creates a new compute ledger row after failed/cancelled preparation.

Temporary files remain private and are removed on exit. FFmpeg preparation counters are not promoted to a customer invoice: this closes supervision/ownership defects, not complete pipeline billing. Process-group cleanup/direct-child identity is not proof that every escaped or remote worker is quiescent; B2/B5 remain separate acceptance.

## User and operator behavior — IT

Un job annullato non avvia una nuova fase di conversione o inferenza. Se una conversione è già in corso, la supervisione la interrompe e ne scarta il risultato. Una preparazione fallita o troppo grande non avvia il modello. I normali job dello stesso proprietario continuano a condividere lo slot della coda; i risultati e i metadati di pubblicazione restano invariati.

Un contesto storico, concluso, di un altro proprietario o di un altro supervisore richiede verifica: non è un permesso per rieseguire. Non modificare l'identità della coda né liberare claim incerti per aggirare il controllo. Recuperare soltanto gli output già congelati attraverso il percorso originale supportato. Le prove esterne di quiescenza, l'identità del checkpoint e i suoi diritti restano richiesti; il remoto commerciale resta bloccato senza il protocollo previsto.

## User and operator behavior — EN

Cancelled work cannot start another conversion/inference stage. Running preparation is supervised, stopped and discarded on cancellation; failed or oversized preparation does not enter the model. Same-owner nested work keeps its original FIFO slot and the existing output/publication metadata.

A historical, terminal, foreign-owner or foreign-supervisor context requires review and cannot authorize reexecution. Do not rewrite queue identity or release uncertain claims to bypass it. Recover only supported frozen output with its original receipt. External quiescence, executing-checkpoint identity and independent rights evidence remain separate requirements; commercial remote inference remains denied without the required protocol.

## Current validation and preservation

**347 distinct affected cases passed,37 new;zero unresolved failures/errors/skips.** Real scheduler nesting, authenticated token API/ledger/owner privacy, independent-process rejection, subprocess cancellation/reaping, real FFmpeg/raw publication metadata, local/pull/deferred recovery and Studio regression are included. Simulated FFmpeg executables exercise actual process launch/kill/wait for cancellation, failure and output limits; they are not model or GPU tests. Full provider/model network calls: zero. Existing full CI and unchanged financial evidence are preserved without unrelated reruns.

Exact cases/reports/hashes and original fixture failures with their corrections are in `validation/r210/execution-owner-result.json`. Only failed or changed cases were rerun. The checkpoint-metrics fixture now claims a live scheduler row before executing, then records its terminal state for the unchanged final-metrics assertions. The two artifact fixtures use the shared supervised conversion boundary inside an actual scheduler job; their original >64MiB/cache/native assertions remain.

Current complete Bandit: **286 files,165 unsuppressed reviewed findings,0 high/21 medium/144 low**. Three findings disappeared with the removed unsupervised FFmpeg import/call; two existing operator-controlled launch findings were explicitly reviewed at their new locations with cancellation guards. No scanner/checker relaxation or suppression. Current source-bound ledger and raw scan are updated together. The transport inventory is unchanged:30 sites/21 files; no new transport. Ruff app/scripts/tests, changed Python compilation and patch whitespace pass.

## Remaining macroarea boundary and next work

This is a completed common registered-executor/source-preparation path, not complete B2/B5/F3/F4/F6 acceptance. The incomplete work includes all remaining legacy/opaque/native executor ownership and metering, authenticated executing-checkpoint/rights protocol (F3 still needs implementation), independent installed-checkpoint rights review and actual delegated-kernel/multi-host/OS evidence. Do not relabel missing protocol/coverage code as only an external block. Use the accepted coordinator/frozen-output recovery rather than rebuilding B4. Then complete financial conservation and the integrated two-way cutover/backend/UI exits under the unchanged queue.

The earlier financial checkpoint remains intact: original subscription evidence audit/API/IT-EN panel is source-identical to its395-case proof; original split migration still requires unavailable independent historical evidence. Finance counts and executor/gate counts overlap and must not be added as a new full-suite count.

The same cumulative patch applies with `git apply --check` followed by `git apply` on the clean baseline9fc85ce. No new full CI is requested merely because this continuation exists; run the affected scope after commit and the required full integration before RC. Suggested cumulative next commit (all changes after9fc85ce):

`Fix legacy subscription evidence and enforce active AI ownership with supervised source preparation`
