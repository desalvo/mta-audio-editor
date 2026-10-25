# Worker ownership and epoch integrity — 2026-10-24 — PRE-RC

Resume from `MTA-0.3.0-r210-pre-RC-worker-epoch-integrity-cumulative.zip` and its adjacent SHA256. Read this handoff, `RC_CLOSURE_PLAN_R210.md`, `DEVELOPMENT_COMPONENTS_R210.json` and `KNOWN_BLOCKERS_R210.md`. **22/42 locally accepted criteria (52.4%), 0/7 complete macroareas, RC false, transition_enabled false.** This closes the local stale-owner defect across the existing execution/settlement paths; it does not implement the shared coordinator or distributed drain.

## Recovery and provenance

The preceding Work environment became unavailable before the pull-worker experiment could be saved. Automated workspace maintenance then removed its local files. The interrupted prototype and its reported 65 cases cannot be recovered from this package and are not counted as delivered source or current evidence. There is **no pull backend** in this deliverable. Do not reconstruct its capabilities from earlier chat summaries or mark B4 accepted.

The reliable input was recovered intact from `MTA-0.3.0-r210-pre-RC-admin-accessibility-cumulative.zip`: 96,325,003 bytes, SHA256 `b96f4bf972e83e053093d91da67cbba57e85db94aebc12b6478eb511701a8417`, 4159 entries. SHA and full ZIP CRC were verified before extraction. All input paths, modes, original protected assets/manuals/licenses and Git metadata files are preserved. Offline Git reference remains `0ad84a5fa0c66d75f75882a0f6e5c6a398470dc6`; no clone, GitHub write, real-server change, commit/push/tag/release, payment, SMTP or actual model inference occurred.

## Defects and resulting behavior

Previously, primitive heartbeat/release and actual billing completion checked matching owner tokens without consistently binding the claim to its original fence and current regime revision. A changed claim revision, changed current epoch or inconsistent transition barrier could therefore pass one boundary despite being rejected by another. The separate completion helper also checked the fence's current epoch but omitted the claim's own epoch, while refusing a valid already-closed historical receipt after a later epoch.

`app/regime_worker_claims.py` now supplies a shared `verify_owner` check. Claim retries, heartbeat and release authenticate the original worker/token, job fence kind, claim/fence regime/revision and allowed state pair. Running work and a released claim with an open fence require the current epoch with no transition barrier. There is no lease expiry, new owner grant or automatic takeover. A finished claim with a closed, matching original fence can be recognized after a later epoch, including while later admission is paused; this does not authorize heartbeat, launch or a new charge. Primitive ownership checks intentionally do not replace ledger, accounting or physical-quiescence checks.

`app/ai_billing.py` inherits the strengthened release check inside the actual ledger/resource/claim/fence write transaction. A stale owner causes rollback of all accounting effects. The idempotent terminal path re-reads ledger, loss decision, claim and fence under one `BEGIN IMMEDIATE` and validates the original closed proof before accepting an exact retry. Identical amounts alone cannot authenticate a corrupted receipt. Existing conflicting-status/usage/source/timestamp retries still fail.

`app/deferred_execution_owner.py` applies the same check before its existing ledger-specific running/terminal and publication validation. Stale staged audio remains pending, cannot be published and cannot register a settlement. Frozen valid receipts remain recoverable without inference replay. `app/regime_worker_completion.py` validates the claim's original epoch too, preserves accounting and physical-quiescence barriers, and accepts exact closed historical retries. `app/regime_job_fence.py` also prevents a prematurely released old-epoch claim from closing its still-open economic fence.

The read-only integrity audit checks the current epoch's existence, flags `running_claim_stale_epoch` or `running_claim_transition_barrier`, and reads schema/epoch/claims from one SQLite snapshot. It preserves an existing caller transaction, supports a read-only connection and makes no schema/data changes. Closed consistent historical claims remain valid audit evidence. The existing service-readiness layer already turns every unsafe claim audit into `worker_claim_integrity_unverified`; no switch was enabled or gate relaxed.

## Verified evidence and reproduction

`validation/r210/worker-epoch-test-summary.json` is the per-case index. **350 distinct affected cases pass; 49 are new. Zero current failures/errors/skips.** Duplicate cases across overlapping recovery reports are counted once. All selected tests enforce offline external-network denial; local worker fixtures generate their own media without ML weights.

| Final report | Passing executions | Boundary |
| --- | ---: | --- |
| worker-epoch-acceptance-final.xml | 49 | New stale-owner matrix, historical/corrupted proofs, atomic accounting rollback, concurrent retry, snapshot/read-only audit, real process death, actual deferred publication/outbox |
| worker-epoch-primitives.xml | 29 | Existing claims, integrity, completion, settlement and real billing transaction |
| worker-epoch-integration-final.xml | 91 | Actual registered subprocesses, Arranger/Remix receipt propagation, frozen recovery, losses and quiescence safety |
| worker-epoch-recovery.xml | 70 | Durable cgroup journal, operator-funded resolution, API authorization/CSRF/private history and frozen results |
| worker-epoch-accounting.xml | 104 | Readiness/inventory/epoch barriers, actual NC ledger, subscriptions, quotas and owner/admin controls |
| worker-epoch-gates.xml | 36 | Unchanged source-bound static-review and transport-inventory checkers |

The new process-death case kills an actual child after its SQLite accounting commit and before acknowledgement. The next process accepts only the exact historical receipt, observes one settlement and does not call the original finalizer again. Its small resource adapter is a fixture, not an actual provider or physical GPU test. The existing actual surviving-worker SIGKILL case also passes; an absent supervisor does not release an uncertain running claim. Synthetic delegated-kernel cases remain synthetic. No multi-host or writable nested-kernel acceptance is claimed.

Use Python 3.12 with the repository's required runtime/test dependencies. Exact test file groups are in the summary's `reports[*].test_files`; run each with `MTA_TEST_OFFLINE=1 python -m pytest --timeout=30 -q ... --junitxml=<new-report>`. The two new files are `tests/test_r210_worker_epoch_ownership.py` and `tests/test_r210_worker_epoch_publication.py`. Full app/native/tests/script Ruff and compileall passed. Bandit 1.9.4 scanned all 279 current app Python files: 168 unchanged unsuppressed findings, 0 HIGH/21 MEDIUM/147 LOW, zero scan errors/suppressions. All five changed app modules have no findings. Exact existing finding dispositions remain unchanged; only the reviewed source inventory/scope was refreshed. Transport inventory remains 29 sites/20 files. Both checkers are unchanged.

`epoch-recovery-initial.xml` records an earlier diagnostic-message mismatch, corrected without changing its assertion. Earlier exploratory runs are superseded by the final reports; initial broad execution encountered missing test-runtime prerequisites, installed only in this environment. The final same integration scope passes all 91 cases. Do not add exploratory attempts or superseded passing runs to the 350 unique total.

Historical full Linux 5228 passed/73 skipped, coverage 73.6774909797391% >=70%, C++ 49 passed/5 skipped, administration E6 browser/axe acceptance and dependency audit are reused. They were not rerun and are not fresh full-source/full-platform CI or a current vulnerability audit. No UI assets or native code changed.

## Continue to the RC

The ordered closure plan remains binding. Next implement I1/B4 with an actual shared authority and cross-host storage/locking, integrate real executor entrypoints and prove duplicate-grant/execution/publication exclusion, partition/crash/reconnect and stale-owner rejection. Reuse this local ownership check, but do not treat it as the coordinator. Then finish all-executor quiescence, distributed admission/drain and the two-way financial cutover/operator workflow. Independently finish global/legacy financial obligations and the authenticated executing-checkpoint rights protocol. Commercial remote inference remains denied.

Real configured payment sandboxes, writable isolated delegated cgroups, multi-host partition targets, container engines and supported OS/GPU/audio/VST environments remain external prerequisites. Missing coordinator, financial, remote-rights and cutover implementation remains missing code, not an external excuse. Keep 22/42 unchanged until complete criterion acceptance passes. The saved package is a durable recovery checkpoint, not an RC declaration or background job.
