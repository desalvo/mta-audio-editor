# Original subscription evidence review — 2026-10-26 — PRE-RC

**Current execution queue: RC_FINAL_WORK_QUEUE_R210.md. Commit deferred by the user; all validated application source and395-case evidence are unchanged by this documentation reorganization. Older next_actions/resume pointers have been corrected.**

Resume from committed baseline **9fc85ce79bee9871696dea9396565395a415aa72** plus the current subscription-evidence patch. No commit, push, workflow dispatch, release or real-server/provider mutation was performed here. No new cumulative ZIP. **23/42 criteria (54.8%), 0/7 whole macroareas; RC false; switching disabled.**

## Verified CI baseline

Full manual run [40257635101](https://github.com/desalvo/mta-audio-editor/actions/runs/40257635101) completed successfully on that exact commit. All 12 verification/build jobs passed; all three publication jobs were skipped. Quality selected `full`: **6448 passed, 104 skipped, 75.84% coverage, 1210.94 seconds**. Both the live browser VST3/MIDI integration and numeric MIDI-edit browser case passed. This supersedes the pending-first-full statements in earlier handoffs. Evidence: `validation/r210/ci-full-confirmed-40257635101.json`, relative to this document.

The 104 prerequisite skips remain unaccepted target checks. They include missing axe-core, actual installed models/instruments/voice assets, delegated cgroups, provider sandboxes and target-specific runtimes. Successful container/native builds do not establish Podman/Kubernetes execution, installed native runtime, hardware or whole-product acceptance. No repeat full run was requested for this local batch.

## Defect and completed local workflow

Previously `subscription_original_loss_review` visited only orders with a permanent financial hold. A legacy paid subscription with no immutable original fee/surplus basis could therefore have a verified payment report before any loss occurred. The current audit checks every recognized originally paid subscription, even without a dispute or reversal. Recognition includes paid status, a recorded payment timestamp or local capture records. Historical terminal labels do not hide those records.

`app/subscription_basis_audit.py` validates original owner/period/gross against the immutable basis, exact nonnegative fee/surplus conservation, complete positive capture totals and the matching funded EUR position. It also detects bases attached to absent/non-subscription/unpaid orders. A missing basis, missing prerequisite schema or conflicting evidence never becomes a current-price estimate. The returned `verified` flag covers the complete audited set, independently of page bounds; an empty page beyond the last unresolved item cannot turn the audit green. At most 200 unresolved DTOs are returned per page. The audit uses a read snapshot, performs no DDL/DML and preserves any transaction already owned by the caller.

The actual payment report now includes `subscription_original_basis_review` and the blocking issue `subscription_original_basis_unverified`. Existing combined readiness consequently retains `payment_ledger_unverifiable`. This diagnostic does not authorize a transition. Existing refund/reversal collection, wallet accounting and original payment basis immutability remain unchanged.

The authenticated administrator endpoint `GET /api/admin/service-regime/subscription-evidence?limit=25&offset=0` supplies private paginated order IDs and concrete reasons with `Cache-Control: no-store` and `Pragma: no-cache`. Anonymous and ordinary-owner access are rejected. Schema failures return generic HTTP409. No owner email, provider secret or inferred debt is exposed.

The actual service-regime panel contains an IT/EN **Original subscription evidence** section with explicit readback, unresolved counts, named case list, keyboard-operable paging, retry and stale-result clearing on error. It is diagnostic; no migration or money action is offered.

## Operator procedure — IT

Nelle impostazioni del regime, selezionare **Verifica prove abbonamenti**. Consultare tutti i casi con **Carica altri casi** e ripetere la lettura dopo una correzione verificata. Il rapporto contabile resta bloccato anche se la pagina visualizzata è vuota ma esistono altri casi.

Per un record storico senza base originale servono prove indipendenti, legate allo stesso ordine, proprietario e periodo, della quota realmente applicata e del surplus originale. Il prezzo attuale, lo stato attuale della quota, il solo incasso PayPal e il saldo rimborsi modificabile non provano quella ripartizione. Non modificare direttamente le tabelle immutabili e non creare un debito ipotetico. Lo strumento consegnato identifica e conserva il blocco; non certifica una migrazione in assenza di tali prove.

## Operator procedure — EN

In service-regime settings choose **Check subscription evidence**, inspect every page with **Load more cases**, and refresh after a verified correction. An empty display page does not clear outstanding cases. A legacy original split requires independent historical evidence bound to the same order, owner and period. Today's price, current fee status, a PayPal gross receipt or mutable refund balance cannot establish the original applied fee/surplus. Do not edit immutable tables or invent a receivable. This delivery completes detection and private review; it does not certify missing historical proof.

## Validation and next work

**395 distinct current cases passed,31 new;zero unresolved failures/errors/skips**, across affected finance, new browser workflow and source-bound gates. Current affected regression: **345 passed**, including 27 new audit/API cases and four existing merchant-history browser cases rerun because the shared panel changed. New actual browser workflow: **4 passed**, IT/EN × 390/1280, actual FastAPI/SQLite API, two pages, actual schema failure and restored retry. Provider I/O remains synthetic and external network access is denied during tests. Gates and exact provenance are in `validation/r210/subscription-basis-result.json`; original failure/correction evidence is retained there without changing failed results into passes. Existing full CI is reused for unchanged boundaries.

Ruff across app/scripts/tests, changed Python compilation and shipped JavaScript syntax pass. Fresh complete Bandit scan: 286 source files, the same 168 unsuppressed findings (0 high/21 medium/147 low); all finding identities/dispositions unchanged. The source-bound review and current raw scan were refreshed together. Remote transport inventory remains 30 sites/21 files; no network boundary was added. Gitleaks8.24.3 finds zero secrets in the delivered patch. Whole changed-file scanning also sees five unchanged, previously reviewed public checksum lines in the security ledger; exact baseline bytes match and no new exclusion was added.

**Concrete legacy block:** no independent historical original-split evidence is available in this workspace; existing gross/charge/refund records are insufficient. A4/A5/C3 remain implementation/evidence pending for complete global histories, unique completed payout/protection movements, partial/legacy obligations and unknown checkouts. Do not count this defect repair as a completed original acceptance criterion. Continue the independent every-executor ownership/rights stream (B2/B5/F3/F4/F6), then integrated drain, financial conservation and both real cutovers with their operator UI. Provider sandbox, independent hosts/delegated kernels, installed models/rights and supported OS/GPU/audio/container execution remain explicit external prerequisites. Docker, Podman and kubectl executables are absent in this restored environment; the green Docker CI gate is preserved as separate evidence, not full G5 acceptance.

## Apply the single patch

From a clean checkout of the baseline above:

```bash
git apply --check /path/to/MTA-r210-subscription-evidence-review.patch
git apply /path/to/MTA-r210-subscription-evidence-review.patch
```

The patch includes source, tests, this handoff, updated development status/components/strategy, source-bound security evidence and the verified full-CI record. It does not include generated runtime data or an intermediate ZIP. The old cumulative source manifest remains historical: refresh the complete manifest only when a new cumulative archive is actually needed. The agent has not staged or committed the changes. Suggested next commit line, covering only changes after the declared committed baseline:

`Block unproved legacy subscription bases before losses and add private evidence review`
