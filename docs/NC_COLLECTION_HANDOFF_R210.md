# MTA 0.3.0-r210 — NC collection and script security handoff

Current checkpoint: 2026-10-23, **PRE-RC**. This document and DEVELOPMENT_COMPONENTS_R210.json supersede earlier handoffs for current status. Version/revision remain 0.3.0-r210. Administrative switching is disabled. No commits, pushes, tags, releases, remote GitHub writes, server changes, real bank/provider requests or actual transfers/refunds occurred.

## Provenance and acceptance

Input: MTA-0.3.0-r210-pre-RC-terminal-checkout-recovery-cumulative.zip, SHA-256 `03ccbe220605987f44f347444c3d36ab5f82aab150adb101abea7a7d34d6d6f9`, 3,394 files. Existing cumulative source was resumed without overwrite. Original incoming archive has 3,267 files, SHA-256 `603c5a5e650178b912605d4203154ea310b2f387e35c9c4c9e719ee30c1d1817`. Reused verified Git baseline: `0ad84a5fa0c66d75f75882a0f6e5c6a398470dc6`; no new remote read needed.

**D5 is locally verified for the offered optional bank-transfer workflow with administrator-reviewed external evidence. Progress: 20/42 equally weighted RC criteria = 47.6%, 0/7 full macroareas accepted.** This is not automated bank authentication or real bank validation. D4 remains partial; D6 still requires enabled, fully guarded administrative cutover. Whole-product completion is unknown; production validation is 0%. Historical 70% estimates are incomparable.

## Functional workflow completed

1. Actual measured jobs close into the existing immutable, cent-exact NC allocation. The administrator UI closes periods, including zero costs, with inclusive start/exclusive end and second-level precision. Existing overlap/unsettled/unverified-measurement guards remain. Eligible costs are operator documented, not independently certified by the software.
2. Collection defaults to disabled. An active administrator configures a stable receiving-bank ledger ID and plain-text recipient/bank instructions with revision checking. Keep the same ledger ID for the same real bank account. Each contribution freezes its original instructions, ledger ID, settings revision, statement digest and NC epoch. Later settings changes do not rewrite it.
3. Owners see only their personal shares, amounts, instructions, history and CSV. They choose a positive cent amount within the unreserved share and explicitly confirm. One unresolved contribution per owner/period, atomic reservations, idempotent retries and immutable targets prevent duplicate allocations. No wallet credits, subscription, compulsory debt, entitlement or automatic transfer is created. Unpaid contributions do not restrict ordinary work.
4. An owner transfer report remains pending review and records zero received money. An unsent contribution can close after an explicit declaration that no transfer is in flight; a merely reported transfer cannot be erased as if no money existed. A fully externally returned contribution can close without forced repayment. State persists across reloads; browser storage is not authoritative.
5. An administrator records an actual receipt only after independent bank verification, the actual amount, a transaction reference, a reviewed-document SHA-256 and explicit confirmation. Self-verification is rejected; another administrator must review an administrator's own contribution. References are normalized and hashed with the original ledger ID; the same bank movement cannot fund another account/contribution. Raw transaction references and evidence documents are not persisted by these APIs. A hash anchors reviewed evidence; it does not itself authenticate a bank.
6. Append-only receipts support partial/full amounts and externally executed refunds/reversals against an exact original receipt. Reversal totals cannot exceed that receipt. The form never executes transfers or refunds: it records verified evidence of a movement already performed externally.
7. Actual overpayments are recorded at their full amount. Allocation remains capped at the voluntary target and frozen share; excess is an explicit operator refund liability, never commercial credit or profit. A late incoming transfer after owner closure is entirely refund due and does not revive the target. Pending transfers and excess refund liabilities block combined readiness without enabling switching.
8. IT/EN owner/operator UI covers settings, period close, confirmation, instructions, report/closure, independent evidence review, refunds, history and private CSV. NC mode hides commercial subscription/credit forms and labels owner navigation for cost statements. History remains readable during drain and in a fixture-tested commercial epoch; mutations stay blocked. That fixture does not implement or certify an administrative cutover.

Frozen statement JSON describes creation-time allocation. Its historical `payments_collected=false` field is not a current bank balance. Actual manual receipt status comes from the separate collection journal and `/api/account/noncommercial-contributions`. Statement hashes/exports remain unchanged; new contribution CSV separates actual net, allocation and excess and is explicitly non-fiscal.

## Implementation, authority and recovery

`app/noncommercial_contributions.py` owns `nc_contribution_settings`, `nc_contribution_intents` and `nc_contribution_events`. Partial/missing collection schema fails closed and never recreates lost receipts. Mutations check active roles, original epoch and matching service-regime.json under BEGIN IMMEDIATE. Drain, mirror drift and commercial mode reject mutations. Duplicate identical requests return persisted results; changed targets/evidence under the same key fail. Rollback/concurrent tests prove one economic effect.

Owner routes:

- GET/POST `/api/account/noncommercial-contributions`.
- POST `/api/account/noncommercial-contributions/{id}/events`: `reported` or `cancelled`.
- GET `/api/account/noncommercial-contributions/export-csv?lang=it|en`.

Administrator routes:

- GET `/api/admin/noncommercial-contributions`.
- PUT `/api/admin/noncommercial-contributions/settings`.
- POST `/api/admin/noncommercial-contributions/{id}/events`: `confirmed` or `reversed`.

All mutations reuse authentication/CSRF and exact field allowlists. Request schemas are exercised in `tests/test_r210_noncommercial_collection_e2e.py`; callers cannot select another owner's ID or rewrite a frozen target. The private admin report includes evidence hashes; owner history excludes other accounts and private bank evidence identifiers.

Authorized retired-account privacy erasure covers the new collection rows and fixes the earlier conflict with closed-NC-job delete guards. Connection-local `mta_nc_erasure` permissions require active-administrator authorization and apply only to the retired owner's records. A fresh connection and another owner's records remain denied. Closed-period INSERT/UPDATE guards remain; the frozen multi-account aggregate is not rewritten. Historical account identifiers in that original accounting aggregate retain the existing policy; this is not full privacy/retention certification. Ordinary non-privacy purge still refuses accounting records.

## Independent script hardening

The prior 33 all-scripts Ruff issues are resolved without rule suppressions or new runtime dependencies. Unused bindings/imports were removed. Isolated billing/recovery/installer checks remain active under `python -O`. Repository/JUnit XML uses a bounded reader rejecting DTD/entity processing. Public repository reads require HTTPS without credentials/fragments, reject redirects and bound response size. Installed diagnostics use explicit HTTP(S) connections without following redirects to another host or protocol; local HTTP diagnostics remain supported.

`scripts/repositories/_safe_xml.py` uses standard-library Expat for syntax/namespaces and ElementTree only to construct trees. DTD, entity and external-entity handlers reject those features. Normal namespace/xml:base and repository fixtures pass. Publisher `--help` and shard `--list-only` ran under `python -S`, confirming no new dependency in minimal publishing/CI environments. No publishing workflow or real server was executed or modified.

Bandit raw scan: **zero findings in the NC module; one LOW B405 import warning in the XML helper**. Review: ElementTree's parse/fromstring/XMLParser are never called; Expat performs parsing with explicit DTD/entity rejection and a size bound. The warning is retained, classified as an import-level false positive, and supported by the negative XML tests. It is not suppressed. See `validation/r210/nc-collection-bandit-review.json`. Full historical app security review remains I8.

## Validation and reproduction

**247 distinct affected cases passed, zero failures/errors/skips.** Authoritative union: `validation/r210/nc-collection-test-summary.json`, keyed by classname/name, from:

- `nc-collection-final-regression.xml`: 199 cases.
- `nc-collection-browser-final.xml`: 14 cases.
- `nc-script-security-final.xml`: 34 cases.

These overlap the old full baseline and must not be added to its 5,228 passes. Actual API/SQLite tests cover role/CSRF boundaries, concurrency, rollback, corrupt schema, reference reuse, late/excess receipts, owner erasure and readiness. Browser tests cover IT/EN at 390/1280 px, dismissal/acceptance, required evidence checkbox, hostile plain-text markup, exports, zero-cost/second-precision periods, actual template mounts and regime-specific controls.

The restored environment lacked test tools. The normal Playwright browser CDN returned an unavailable page. Local browser acceptance used Chromium 143.0.7499.0 from pinned `@sparticuz/chromium@143.0.4`, Playwright 1.58.0 and explicit executable selection, with normal web security. Binaries/node_modules are not delivered. This does not replace target platform or production acceptance. Real bank/provider requests: zero.

Ruff passed for app/native/tests/**all scripts**. app/scripts compileall and both changed JS syntax checks passed. Both isolated billing/recovery validators passed under `python -O`. Retained evidence: complete Linux 5,228 passed / 73 skipped, combined coverage 73.6774909797391% against 70%, C++ 49 passed / 5 opt-in skips, runtime audit 31 packages / zero known vulnerabilities. None was unnecessarily rerun. Historical full-app Bandit baseline (0 high,22 medium,146 low) is still review debt, not a fresh scan.

Reproduce only after a relevant change:

```bash
MTA_TEST_OFFLINE=1 python -m pytest -q --timeout=45 tests/test_r210_noncommercial_collection_e2e.py tests/test_noncommercial_allocation.py tests/test_noncommercial_statements.py tests/test_noncommercial_closed_period_guard.py tests/test_noncommercial_metered_preview.py tests/test_r210_noncommercial_actual_ledger_e2e.py tests/test_r210_noncommercial_user_statements.py tests/test_r210_noncommercial_service_switch.py tests/test_r210_user_erasure_dump.py tests/test_r210_account_lifecycle.py tests/test_r210_subscriptions.py tests/test_r210_credit_checkout.py tests/test_regime_reconciliation_inventory.py tests/test_regime_readiness_cli_r210.py tests/test_regime_readiness_hardening_r210.py tests/test_r210_subscription_repayment_e2e.py
MTA_TEST_OFFLINE=1 python -m pytest -q tests/test_r210_noncommercial_collection_browser.py tests/test_r210_script_input_security.py tests/test_r209_pages_rpm_distribution.py tests/test_r208_installed_diagnostics.py tests/test_r208_global_regression_certification.py tests/test_r208_native_installer_payload_gate.py
python -m ruff check app native tests scripts
python -m compileall -q app scripts
node --check app/static/noncommercial_contributions.js
node --check app/static/subscriptions.js
PYTHONPATH=. python -O scripts/mta_billing_isolated_validation.py
PYTHONPATH=. python -O scripts/mta_billing_recovery_isolated_validation.py
```

Install normal Playwright Chromium, or set `MTA_TEST_CHROMIUM_EXECUTABLE` to a working existing Chromium binary. A configured missing binary or failed launch fails tests. Early development logs are historical; the final summary supersedes repaired placeholder/schema, erasure, overflow and datetime precision failures.

## Remaining implementation and external prerequisites

I6/D5 is locally closed for this manual method; automated bank feeds/online gateways are neither supplied nor claimed. D4 full account/control acceptance and D6 enabled-cutover balances remain open. Remaining code: I1 shared multi-host coordinator and actual external-worker quiescence; I3 authenticated remote checkpoint/rights evidence; I4 distributed barrier, financial migration and complete two-way administrative cutover/recovery; I5 full PayPal history/dispute/payout/multicapture/legacy/original-subscription risk/operator-refund cases and unknown/failed-charge outcomes; I7 remaining UX/adapter/platform acceptance; I8 full historical security review. These are implementation gaps, not merely external blocks.

External prerequisites: configured isolated Stripe/PayPal sandbox data/credentials, Docker/Podman/Kubernetes runtime, Windows/macOS, physical audio/GPU/authorized models/live plugins. Do not use production to replace them. RC remains false and switching disabled. This is a resumable checkpoint, not the final RC; no background work is scheduled when a turn ends.
