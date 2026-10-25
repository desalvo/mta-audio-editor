# MTA 0.3.0-r210 — subscription recovery handoff, 2026-10-23

**Latest checkpoint; PRE-RC.** Resume here, then read DEVELOPMENT_COMPONENTS_R210.json, KNOWN_BLOCKERS_R210.md and TEST_MATRIX_R210.md. This supersedes the previous continuation for the code and validation described below. The version remains 0.3.0-r210, administrative switching is disabled, and no GitHub writes, real-server actions, real payments, commits, tags or releases were made.

## Provenance

Continued the existing local workspace from `MTA-0.3.0-r210-pre-RC-deferred-paypal-history-cumulative.zip`, SHA-256 `34c4031251f11f1c618bc15020ef38c204b26d090e40fb7eb1f0d70ee37bac8e`. No archive download or GitHub access was needed. Original archive and Git baseline remain as documented in DEVELOPMENT_HANDOFF_R210.md. Prior complete Linux/C++/dependency/coverage results were reused; only affected code was retested.

## Functional closure in this cycle

The previously recorded exact PayPal subscription-refund receivables can now be collected through an owner-scoped payment, rather than merely displayed as debt. This closes local checklist criterion D3. Progress is **19/42 equally weighted locally verified milestones (45.2%), 0/7 full macroareas accepted**. The real provider sandbox remains unverified; this is not full financial, commercial billing or RC acceptance.

1. `subscription_receivables.py` reads existing refund-derived receivables without changing their principal. Source rows, checkout targets and nominal allocations are immutable. A payment is bound to exactly one original refund and owner. Its effective coverage comes from its authenticated net payment position, not the browser or the wallet.
2. The account and administrator views expose exact principal, effective repaid amount, residual balance, pending checkout, per-payment allocations and refund liabilities. IT/EN account buttons quote the actual PayPal cent amount and require confirmation. Administrators see actual aggregate debt and refund totals plus per-user recovery history. No fiscal receipt or automatic operator refund is implied.
3. PayPal checkout derives the EUR amount server-side from the exact outstanding micro-EUR amount. The caller must confirm that amount with `expected_due_micro`; no client price is accepted. One pending checkout per source prevents parallel collection. Its target and quote participate in the checkout/fence/outbox transaction. Retries reuse the same identity; a reload resumes the saved provider URL. A missing provider result stays pending for review, with no blind resubmission or fabricated cancellation.
4. Capture rechecks the receivable before collecting an approved payment. Canonical fulfillment atomically records captures, allocates only the outstanding amount, closes the original checkout fence and journals settlement. Already-executed money is retained even if its old quote has become obsolete: the unapplied amount becomes an explicit refund due, not credits or lost cash. Duplicate/concurrent fulfillments create one allocation.
5. The return goes to `/account?paypal_order=<local-id>` and verifies the payment server-side before refreshing debt. A return URL alone grants nothing. Existing debt remains repayable when plan/credit services are disabled; it does not require buying a new plan. New checkout remains commercial-only and owner-authenticated with the existing CSRF protection.
6. A refund, permanent reversal or dispute hold on the repayment reduces its effective coverage and reopens the **same** receivable. It does not recursively create new debt or touch resource credits. Released holds restore coverage. If a second repayment had meanwhile covered the balance, the restored excess becomes an operator refund liability. Allocation priority is frozen by a monotonic transaction timestamp, so equal-second payments cannot reorder coverage.
7. Cents are rounded up only for provider collection. The exact allocation stays in micro-EUR; any excess remains refundable. Refunds consume unallocated surplus first. Global financial reports use residual debt and refund liabilities, and flag missing/mismatched repayment positions as unverifiable. Readiness retains blockers for outstanding debt/refunds and never enables switching.

8. Immutable deletion is compatible with the existing explicitly authorized account-erasure workflow. An active administrator must authorize erasure of a retired non-admin owner. The database permits only that owner’s preselected source/target/allocation keys on that exact connection; ordinary connections deny deletion. The erasure journal retains the authorizing actor for recovery and revalidates active admin status. Accounting detection now includes PayPal orders, reversal receivables and subscription fees. Tests prove both immediate erasure and privacy purge plus later sandbox deletion preserve another owner’s financial records. This is workflow integration, not a blanket GDPR/legal certification.

Affected code: `subscription_receivables`, `paypal_payments`, `resource_accounts`, `resource_routes`, `payment_reconciliation`, `regime_reconciliation`, `auth`, `account_lifecycle`, `account_erasure`, account template, subscription and financial administrator JavaScript. No runtime dependency was added.

## Verification and limits

See `validation/r210/repayment-test-summary.json` and its five XML sources for the distinct affected-case union. It includes actual FastAPI handlers, SQLite accounting, local concurrency/crash boundaries, canonical provider fixture readback, mocked signature verification and real Chromium IT/EN owner/admin interactions at desktop/mobile widths. All provider endpoints were fixtures; no real provider requests or payments were made. The final distinct affected union is **233 passed, zero failures/errors/skips**. The earlier new test failure was an invalid assumption that the entire credit table was empty; it now asserts that all preexisting rows are unchanged.

The full earlier Linux result remains 5,228 passed / 73 skipped with 73.67749% line/branch coverage. It was not rerun and coverage was not recollected for this cycle. C++/GPU/platform/container and unchanged AI ownership checks were not repeated. Whole-project Ruff, changed JavaScript syntax and app compilation pass; the new module has zero Bandit findings. Existing Bandit review items remain open.

This flow collects the existing exact **refund-generated** subscription receivables. Permanent risks on the original subscription payment, ambiguous payout/protection cases, complete multi-capture dispute discovery/allocation, legacy liabilities, all terminal/uncertain outcomes and execution of operator refunds still belong to A4/A5/I5. A held original subscription payment is still reported as risk; it is not silently turned into a collectible refund debt. Actual sandbox lifecycle acceptance is still required (A6). No acceptance criterion for those cases was waived.

## Next actions

- I5: implement provider-wide PayPal dispute/protection/payout discovery and exact allocation; complete permanent original-subscription risk obligations, legacy liabilities, safe terminal/uncertain checkout handling and operator refund settlement. Retain unknown dispatches for authenticated review.
- I1/B2: shared multi-host coordinator and independent proof that external workers have stopped after supervisor loss; no automatic claim takeover.
- I3: authenticated remote checkpoint identity and reviewed rights, plus remaining legacy executor bypass coverage.
- I4: complete distributed admission/drain, financial migration and both-direction operator workflow before enabling administrative switching.
- I6/I7/I8: NC voluntary contribution collection, remaining account/operator/platform acceptance and security review.

External sandbox/container/platform/GPU/audio/VST prerequisites are separate from that unfinished code. The unchanged RC gate remains BLOCKED. The user/operator guide is SUBSCRIPTION_RECOVERIES_IT_EN_R210.md. No background execution is scheduled.
