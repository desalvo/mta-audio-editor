# D4 owner account acceptance plan — 2026-10-24 — completed locally

Criterion D4 is now locally verified after the full scoped matrix below passed. This cycle targets the complete browser-facing owner workflow for the already implemented two-regime billing contract, not new provider money rules or enabled cutover.

Required matrix before acceptance: actual /account and /account/credits pages with all shipped assets; IT/EN, 390/1280 px; commercial no-plan/trial/paid-plan/permission-disabled/credits-disabled states and non-commercial current plus historical commercial records; active provider configuration versus unavailable configuration; quota, wallet and non-debt contribution separation; real owner privacy and backend regime guards; trial/renewal/cancellation/overage/storage/report workflows; credit checkout, trusted return/signed funding, pending/error recovery; subscription reversal recovery and refund history using preserved independently validated subflow evidence where unchanged; locale refresh/profile round trip; stale responses, concurrent/double-click and interrupted requests cannot cause duplicate mutation or stale redirects; keyboard/accessible-name/heading/status and no horizontal overflow checks on the complete owner pages. Each new defect must be fixed and validated through actual API/SQLite; payment-provider I/O remains simulated.

Full product-wide accessibility/native/real provider sandbox and enabled administrative cutover remain E6/F5/G6/A6/D6 and are not waived by D4. Acceptance result: all scoped matrix elements passed; D4 verified. Separate enabled-cutover and target/product-wide criteria remain unaccepted. Do not inflate macroarea completion or rerun unrelated baselines.

## Result and traceability

104 new cases (94 browser/10 domain),315 distinct affected cases (160 actual Chromium),zero current failures/errors/skips. Exact per-ID latest execution, source hashes and supersession: validation/r210/account-workflow-test-summary.json. No unrelated baseline rerun.

| Acceptance surface | Current evidence |
| --- | --- |
| 8 states,2 languages,2 widths; actual Account and Credits | test_r210_account_acceptance.py:32 state cases |
| Trial→next plan,overage opt-in/out,storage,interval,cancel without reset; profile locale | test_r210_account_acceptance.py:6 action/profile cases |
| Stripe/PayPal full return/funding,in-flight locale,NC no-capture,pending fee privacy,recovered existing credit | test_r210_account_payment_acceptance.py:24 cases |
| NC statement→pledge→report→reviewed receipt→CSV; outages and concurrent locale | test_r210_account_resilience_acceptance.py:12 cases |
| Actual private refund history and retry in both regimes | test_r210_account_refund_acceptance.py:4 cases |
| Full-page axe/keyboard/names/overflow/opaque contrast | test_r210_account_accessibility_acceptance.py:16 cases |
| Stale/reversed report response and failure recovery | test_r210_account_resource_freshness.py:2 cases |
| Pre-capture epoch/owner/merchant/permission/quote/outbox/evidence drift | test_r210_account_capture_preflight.py:8 cases |
| Existing subscription repayment,owner/admin history,NC collection and refunds | account-owner-regression and account-return-patch reports; latest per-ID green |
| Existing payment/domain contract and source/security/inventory | account-acceptance-domain.xml: 107; account-acceptance-gates.xml: 36 |

Simulated provider I/O only. Original-epoch historical receipt guards retained.16 axe reports have zero violations and zero unresolved supplemental items; no rule exclusions. Full product/native/manual assistive-technology conformance and real sandbox/cutover remain separate.
