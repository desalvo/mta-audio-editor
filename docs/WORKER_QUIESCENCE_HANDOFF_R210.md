> Historical checkpoint. Current continuation: DURABLE_WORKER_RECOVERY_HANDOFF_R210.md and DEVELOPMENT_COMPONENTS_R210.json.

# MTA 0.3.0-r210 — worker identity and recursive cleanup handoff

Checkpoint 2026-10-23. PRE-RC; transition_enabled=false. This is the latest continuation; retain NC_COLLECTION_HANDOFF_R210.md for the complete previous feature set. **20/42 equally weighted criteria (47.6%), 0/7 complete macroareas. B2 remains pending.** Whole-product completion is unknown, production validation 0%. No GitHub/server mutations, commit/push/tag/release, real payments or provider requests.

## Resume source and restoration

Resumed MTA-0.3.0-r210-pre-RC-nc-collection-security-cumulative.zip, SHA-256 e5c4f4d12deba28dfe37a36e615019b8ff1927d18ac66ebda20ffb65bacfdb68 (3,421 files, 92,551,102 bytes). Recovered the already saved checkpoint after the environment reset omitted its final documentation. SHA-256 and CRC passed. Source code was byte-identical; 13 documentation/evidence paths were restored after preserving old local copies outside the project. No source work was overwritten. Baseline Git 0ad84a5fa0c66d75f75882a0f6e5c6a398470dc6 remains a reused read-only comparison, not a new remote checkout.

## Corrections implemented

- app/ai_arranger_runtime.py: process identity is tri-state. A nonempty identity identifies the original process, None proves absent/exited, and an empty string means unavailable. Missing/empty boot identity, denied/malformed process data and unsupported probes are unknown. Hidden proc entries require a kernel signal-0 probe returning ESRCH before absence is accepted; permission denial never proves death. Invalid PIDs cannot probe process groups. Linux zombie/dead states are recognized. Unknown identity preserves the original queued/running owner and creates no interrupted receipt.
- Linux/Windows admission waits if the scheduler cannot establish its identity. If identity becomes unavailable before completion, no terminal queue receipt is written and the original running job remains for reconciliation. This favors an unresolved visible blocker over duplicate work. Existing generic native paths retain their PID fallback; full platform acceptance is still open.
- app/deferred_execution_owner.py rejects absent/unknown scheduler identity before acquiring an economic worker claim. Two matching unavailable identities no longer authorize ownership. Existing original-owner publication/billing receipt propagation is retained.
- app/ai_cgroup_metering.py requires cgroup.kill before spawning into an isolated delegated group. Older/unusable delegations fail closed without fallback to partial metering. Cancellation, timeout, descendants surviving the main process, and final cleanup use the kernel recursive kill operation and bounded polling of recursive cgroup.events populated=0. PID enumeration/kill-by-recycled-PID is no longer used for cgroup descendants. Empty nested groups are removed bottom-up. Incomplete cleanup is retained/logged, cannot return a valid measurement, and never changes economic claims. Main-process fallback termination remains bounded; it is not external-worker quiescence proof.

These changes do not add remote killing, operator refund execution, claim takeover, inference replay, automatic settlement or cutover. An interrupted queue receipt indicates lost scheduler ownership, not proof that descendants or remote work stopped. A supervisor killed before its finally block can leave its cgroup/workers active: durable crash-to-cgroup recovery and audited economic resolution are still missing implementation. SQLite is not a multi-host coordinator. Workers escaping the delegated hierarchy and remote tasks require separate authoritative coverage.

## Evidence and limits

116 affected cases passed, 1 explicit prerequisite skip, zero failures/errors in docs/validation/r210/worker-quiescence-final.xml; exact list in worker-quiescence-summary.json. Actual supervisor SIGKILL with a real surviving external child passed: queue is interrupted without replay, original ledger remains running, claim running, fence open and stale recovery blocked. This is a negative safety proof, not successful economic recovery. The execution harness virtualizes PIDs; that experiment obtains its kernel PIDs from /proc/self/stat so the kernel liveness probe addresses the actual processes.

Synthetic cgroup tests cover nested occupancy with no direct members, recursive kill, polling, missing capability/no launch, cancellation at execution/exit, timeout, incomplete cleanup invalidating a pending measurement, and measured clean completion. They do not prove a delegated kernel. tests/test_r210_real_cgroup_supervisor_loss.py is an explicit opt-in: it creates only its own private subtree below MTA_TEST_CGROUP_PARENT, runs a child in a nested cgroup and separate session, SIGKILLs the supervisor, verifies remaining occupancy, recursively stops it and requires populated=0. It was skipped here because no isolated writable delegation was supplied. A supplied invalid/unusable delegation fails rather than becoming a skip. Even passing it does not implement durable economic claim resolution or certify B2/B4.

App/native/tests/all-scripts Ruff passed; changed files compile. Final affected scope includes deferred Arranger/Remix, claims/integrity, global queue, restart/PID reuse, cgroup worker/preflight/cancellation, legacy supervised lifecycle and job center API. Initial fixture/dependency failures are resolved in the final XML; older logs remain development evidence. One upstream Starlette/httpx deprecation warning remains. No production dependency change. Prior complete Linux 5,228 passed/73 skipped, coverage 73.6774909797391%, native 49 passed/5 opt-in skips and prior NC browser/security evidence were retained without rerunning or adding overlapping counts. Full historical Bandit review remains open; no fresh full security certification is claimed.

## Reproduce only after relevant changes

```bash
MTA_TEST_OFFLINE=1 python -m pytest -q --timeout=45 tests/test_r210_worker_quiescence_safety.py tests/test_r208_queue_runner_identity.py tests/test_r208_restartable_queued_jobs.py tests/test_r207_cgroup_recursive_accounting.py tests/test_r207_cgroup_metering.py tests/test_r208_cgroup_cancellation_settlement.py tests/test_r210_deferred_owner_e2e.py tests/test_regime_worker_claims.py tests/test_regime_worker_claim_integrity_r210.py tests/test_r210_global_ai_execution.py tests/test_r208_cgroup_worker_handoff.py tests/test_r208_worker_preflight_and_cgroup_environment.py tests/test_r208_legacy_supervised_lifecycle.py tests/test_r210_ai_job_center.py tests/test_r210_real_cgroup_supervisor_loss.py
python -m ruff check app native tests scripts
```

For the delegated-kernel acceptance, supply MTA_TEST_CGROUP_PARENT only for an explicitly isolated writable test delegation with cpu/io controllers enabled in its parent; select tests/test_r210_real_cgroup_supervisor_loss.py. Do not point the opt-in test at a service-owned or shared application subtree. This test is not executed against real servers in this checkpoint.

## Remaining work and exact next steps

1. Implement durable original-supervisor-to-cgroup identity binding before launch, prove kernel and worker authority after actual supervisor loss, and provide audited reconciliation that conserves usage/holds without fabricating charges. A cgroup pathname alone, PID age or manual assertion is insufficient. Preserve original claims until the proof and financial handling are implemented.
2. Add an authoritative shared coordinator/storage and partition/fencing acceptance; do not broaden SQLite claims to multi-host certification. Complete every legacy/native/remote executor inventory.
3. Independently continue remaining provider-wide PayPal history/dispute/payout/legacy/subscription-risk/refund handling; remote authenticated checkpoint/rights evidence; full account/accessibility/operator UI; complete distributed two-way cutover while keeping it disabled until accepted; full historical security review. KNOWN_BLOCKERS_R210.md and DEVELOPMENT_COMPONENTS_R210.json remain the explicit checklist.
4. External prerequisites remain isolated provider sandbox credentials/data, writable cgroup/container environment, Windows/macOS/audio/GPU/authorized checkpoints/live plugins. Their absence does not excuse missing implementation. Do not rerun retained baseline suites until changes justify it.

## Nota operativa IT

Identità non leggibile significa stato sconosciuto, non worker terminato. L'interruzione della coda non cancella i claim economici e non autorizza una nuova inferenza. Nei cgroup delegati la terminazione ricorsiva deve arrivare a populated=0; se manca cgroup.kill o la pulizia non è verificabile, nessuna misura viene certificata. Dopo la morte del supervisore il recupero economico completo resta da implementare. Il test sul kernel delegato è predisposto ma non eseguito in questo ambiente. RC non raggiunta, cambio di regime disabilitato. Nessun lavoro prosegue in background al termine del turno.
