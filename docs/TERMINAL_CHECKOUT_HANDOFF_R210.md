# MTA 0.3.0-r210 — terminal checkout and reference recovery handoff

Current checkpoint: 2026-10-23, PRE-RC. Version/revision unchanged. Administrative regime switching remains disabled. No GitHub changes, commits, pushes, tags, real-server modifications, real payments or production credentials. Continue locally from this cumulative source; do not overwrite it with an older archive or repository checkout.

## Provenance and acceptance

Resumed from MTA-0.3.0-r210-pre-RC-subscription-recoveries-cumulative.zip, SHA-256 f10e1f5095cf534f2b2aac75379c2af7ae2f333de6188fe3b0a721e7d8f25dc0. The original incoming archive has 3,267 files, SHA-256 603c5a5e650178b912605d4203154ea310b2f387e35c9c4c9e719ee30c1d1817. The reused read-only Git baseline is 0ad84a5fa0c66d75f75882a0f6e5c6a398470dc6. No remote mutation or new remote read was needed.

Acceptance progress remains **19/42 equally weighted RC milestones (45.2%), 0/7 whole macroareas accepted**. This cycle closes useful subsets of A5, whose criterion includes all legacy and uncertain outcomes; A5 remains implementation_pending. Do not increment progress merely for adding functions/tests. Full-product completion is unknown; production validation is 0%. The historical 70% estimate is incomparable.

## Implemented end to end

- app/checkout_terminal_outcomes.py closes a genuinely unpaid original checkout using authenticated provider proof. Stripe accepts an expired session with explicit null intent, or expired/complete unpaid session with a canceled intent, zero received/capturable money and an empty bounded charge history. PayPal accepts only a VOIDED CAPTURE order with one exact local purchase unit and no capture/refund/authorization/unknown payment objects. Canonical reads are repeated to reject changing snapshots. Browser cancellation, failed async notifications, open/processing sessions, 404 and timeout do not establish terminal emptiness.
- Closure is one write transaction: validate local identity/configuration, original commercial DB epoch and matching service-regime.json, confirmed attempted outbox, no drain, no prior wallet/financial movement or contradictory pending evidence; persist immutable terminal receipt and applied normalized financial event; set local order cancelled and clear checkout URL; preserve confirmed creation outbox; close original fence; record an unfunded zero-net position. Rollback, duplicate/concurrent delivery and signed Stripe expiry are tested. Paid notifications arriving afterward remain durable pending conflicts and never credit the wallet.
- app/checkout_reference_recovery.py resolves a lost create response when the operator knows the exact provider ID. It uses authenticated fixed GET endpoints and verifies owner/order/gross/currency/mode/merchant and unique reference, then rechecks local/config/epoch state under lock. It atomically binds the ID to the original attempted uncertain creation and persists immutable reference evidence. A safe provider approval URL is recovered when available. It neither creates a new order nor grants money; positive reconciliation remains separate. Successful repeated binding is idempotent even after later settlement. An unknown ID, absent response or timeout remains unresolved, with no blind redispatch.
- POST /api/admin/service-regime/recover-checkout-reference uses existing administrator authentication and CSRF. The IT/EN operator UI confirms ID verification, displays pending/closed/reconciled outcomes distinctly, and allows ordinary canonical reconciliation after reference binding. It never represents an unfunded terminal position as paid.
- IT/EN owner subscription recovery and credit-shop screens can verify an already approved PayPal order when its approval URL was lost but the authenticated reference is known. Existing owner-scoped capture and explicit amount confirmation remain mandatory. A pending result is never described as paid. Unknown-reference orders stay under review. Credit catalog exposes only the current owner's local order summaries.
- Authorized account erasure/privacy purge and scoped backup discovery now follow financial provider/order references that are not SQLite foreign keys. They include bound financial events/objects/disputes/movements, identifiable unbound pending events, original checkout fences and their FK descendants. Another owner's records and genuinely unattributed pending evidence remain intact. This runs only within the existing authorized lifecycle; accounting protection on ordinary non-privacy purge remains unchanged.

## Validation and exact scope

323 distinct affected cases passed, zero unresolved failures/errors/skips. See validation/r210/terminal-test-summary.json for the latest-result union, keyed by classname/name, and the XML/log evidence. Counts overlap the prior baseline and must not be added to 5,228. Final affected closure run: 134 passed. Real FastAPI/SQLite/Chromium test paths cover IT/EN owner/operator UI, narrow/wide viewports, confirmation rejection/acceptance, lost response -> reference bind -> terminal closure or owner payment, rollback/concurrency, malicious identities/config changes/epoch/mirror/drain, existing money and pending evidence, late positive conflicts and owner-scoped erasure. All provider responses/signatures are isolated fixtures; external provider request count is zero.

Project Ruff (app native tests scripts/k8s-wizard.py), compileall app and syntax checks for the three changed JS files passed. Bandit on the two new modules: zero findings, no new runtime dependencies. A separately broadened Ruff scan of all scripts found 33 existing issues outside the normal project scope (terminal-script-scope-review.log); they are retained for I8 review, not waived or presented as clean. Initial added-test fixture failures are retained and explained in terminal-test-summary.json; final results supersede those cases without weakening enforcement.

Reused baseline: Linux 5,228 passed / 73 skipped; combined coverage 73.6774909797391% against unchanged 70%; C++ 49 passed / 5 opt-in skips; dependency audit 31 packages / zero known vulnerabilities. No complete-tree/coverage recollection after this continuation. Target Python 3.14, Windows/macOS, containers and real provider/model/hardware acceptance remain unverified.

Reproduce the latest affected closure checks with an isolated environment and Playwright Chromium installed:

```bash
MTA_TEST_OFFLINE=1 python -m pytest -q --timeout=45 tests/test_r210_terminal_checkout_e2e.py tests/test_r210_checkout_reference_recovery.py tests/test_r210_terminal_recovery_browser.py tests/test_r210_user_erasure_dump.py tests/test_r210_account_lifecycle.py tests/test_r210_subscription_repayment_e2e.py
python -m ruff check app native tests scripts/k8s-wizard.py
python -m compileall -q app
node --check app/static/regime_admin_panel.js
node --check app/static/subscriptions.js
node --check app/static/credit_shop.js
```

Do not rerun this validated scope without a related code change or unresolved concern. Prior broad 312-case run and final credit owner/catalog 19-case run are retained in the summary rather than repeated.

## Remaining implementation and external blocks

A5 is not complete: no independent proof of non-creation from 404/timeout, no automatic unknown-reference discovery; canceled intents with existing failed-charge histories remain blocked; legacy liabilities, original-subscription permanent risks and operator refund execution still need implementation. A4 provider-wide PayPal dispute/protection/payout completeness and multicapture allocations remain pending. A snapshot cannot prove no future reversal.

Independent work remains I1 shared multi-host coordinator plus actual external-worker quiescence; I3 authenticated remote checkpoint rights; I4 complete guarded cutover in both directions and distributed financial migration; I6 voluntary NC contribution collection; I7 complete account/operator UX and platform acceptance; I8 security baseline and script review. Do not label missing implementation as an external block.

External prerequisites: no isolated configured Stripe/PayPal sandbox merchant/data credentials, no Docker/Podman/Kubernetes runtime, no Windows/macOS/audio/GPU/authorized model/live-plugin environment. Do not touch real services to bypass these restrictions. Keep unknown financial evidence/worker ownership blockers and transition_enabled=false. Read KNOWN_BLOCKERS_R210.md and DEVELOPMENT_COMPONENTS_R210.json before choosing the next independent item. No background continuation is scheduled by this checkpoint.

## Provider semantics used

Primary references: https://docs.stripe.com/api/checkout/sessions/expire ; https://docs.stripe.com/api/payment_intents/cancel ; https://docs.stripe.com/api/events/types ; https://developer.paypal.com/api/orders/v2/ ; https://developer.paypal.com/serversdk/php/api-endpoints/orders/errors . These support provider status semantics; local fixture acceptance is not real provider lifecycle acceptance.
