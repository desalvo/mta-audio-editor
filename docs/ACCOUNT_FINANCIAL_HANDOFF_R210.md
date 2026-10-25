**Continued by OWNER_PAYMENT_RECOVERY_HANDOFF_R210.md. This file retains validated account-context evidence; use the newer handoff for current payment recovery and source security review.**

# MTA 0.3.0-r210 — account financial context development handoff

2026-10-23. PRE-RC. RC false, administrative switching disabled. Formal progress remains 20/42 (47.6%), 0/7 whole macroareas. This completes the personal financial overview and error/recovery display workflow only; D4 remains implementation_pending until complete account/payment/accessibility acceptance. No macroarea is accepted by the tests below alone.

## Restore and authoritative input

Latest input MTA-0.3.0-r210-pre-RC-security-review-cumulative.zip, 3521 files, SHA-256 3293c8977cb0bc447986bffb236193ebc4b0fdca9d186b0ac9c662820d81dc3a. The local environment had rolled back to an older in-progress NC tree. Downloaded the identified saved checkpoint, verified full SHA/CRC and every source manifest entry, retained the older local work tree separately and restored the exact latest package. No prior development or baseline test cycle was repeated. Future resume must use this handoff rather than the older local tree.

Current single cumulative archive: MTA-0.3.0-r210-pre-RC-account-financial-context-cumulative.zip, plus adjacent checksum. Its own hash cannot appear inside the archive. All preceding paths and original protected license/manual/assets must remain; preservation and exact local Git-blob comparison are in docs/validation/r210. No GitHub/server/commit/push/tag/release changes or real payments.

## Implemented behavior

The existing authenticated GET /api/account/limits now returns service_regime and financial_context from the actual owner ledger. New app/account_financial_context.py calls verified private NC overview and immutable worker-loss history. It never mixes allocated cost shares with customer debt or credits. It exposes only personal aggregate amounts/counts/periods, not another account, bank instructions, raw evidence keys or private loss reasons. Query-string user_id cannot choose another owner. The optional aggregate_outstanding_debt_micro stays null because no authoritative combined debt ledger exists.

NC data distinguishes closed allocated shares, reviewed allocated receipts, remaining declared voluntary contributions, transfer reports awaiting verification and excess receipts refundable by the operator. A transfer report does not become an incoming payment. Contributions remain voluntary, do not buy credits and do not restrict access. Commercial wallet balance, subscription identity/funding and permission to show commercial controls remain separate. Historical NC records are readable in commercial mode; existing commercial credit balances can be shown as historical read-only data in NC mode. This view does not certify the external bank movement or execute a transfer/refund.

Account limits opens a DB read snapshot after existing schema setup for the verified financial context and period lookups. Closed NC statement ranges now contribute to closed measured-usage totals, including measured terminal failed/cancelled jobs in those closed periods. Existing commercial invoice ranges and legacy pending-estimate semantics remain compatible; no new invoice, debt or price is inferred from an NC allocation. Legacy issued amounts, when present, are explicitly historical and not proof of payment. Existing resource state/initialization behavior is retained; the whole GET endpoint is not newly claimed as a side-effect-free accounting engine.

Unverifiable journals, invalid ownership or SQLite/regime errors yield generic HTTP 409 without private evidence details. The browser clears stale usage and exposes a retry rather than continuing to display stale amounts as fresh. It rejects a summary user_id that differs from the current account and discards an older account request after identity changes. No sensitive financial state is stored in browser storage.

Account_limits.js renders the new IT/EN financial panel, clear non-debt/non-fiscal explanations and separate wallet/receipt values. It no longer labels an NC cost share as an invoice or a balance due. Account template asset versions changed so old cached renderers are not reused. Existing source CPU/GPU/storage charts remain; the misleading combined-money chart was removed.

Subscriptions.js now removes commercial content in NC mode, validates known service-regime values, disables existing controls during refresh, clears them after failed refresh, and restores them only on a verified successful load. Generation/request counters reject late prior-language responses: an old wallet snapshot cannot replace new controls after changing locale. Commercial navigation points to subscription management. NC navigation remains linked to cost statements. Existing backend commercial guards and explicit cancellation/repayment confirmations are retained.

## User workflow — IT / EN

IT: aprire Account → Limiti e Quote. Nel regime non commerciale leggere separatamente quote allocate, incassi verificati, segnalazioni in attesa e rimborsi dovuti dal gestore; proseguire nel pannello dei consuntivi e bonifici volontari. Le quote non sono un debito e non acquistano crediti. Nel regime commerciale consultare il portafoglio e gestire l'abbonamento nel pannello dedicato. I movimenti e i rimborsi mantengono registri distinti. Se il caricamento fallisce, usare Aggiorna: i vecchi comandi sensibili non restano utilizzabili come se fossero validi. Uno storico mancante o consumi sconosciuti non significano zero.

EN: open Account → Limits and quotas. In non-commercial service, read allocated shares, reviewed receipts, unverified reports and operator refunds separately, then use the statement/voluntary-transfer panel. Shares are not debt and do not buy credits. In commercial service, inspect the separate wallet and manage the subscription below. Payment/refund records remain distinct. If loading fails, refresh; stale subscription controls are removed. Missing records or unknown usage must not be interpreted as measured zero.

## Verification and reproduction

130 distinct affected final-code cases passed, no failures/errors/skips. 31 are real Chromium cases. Authoritative disjoint execution union:

- account-financial-final.xml: 104 passed across new context/browser tests, personal limits, NC collection/browser and subscription regressions.
- account-financial-review-gate.xml: 17 passed.
- account-financial-repayment.xml: 4 owner repayment browser cases passed (real app/API/ledger, provider fixtures only).
- account-financial-stale-response.xml: 1 late-response wallet browser case passed.
- account-financial-page.xml: 4 full actual /account page mounts passed, IT/EN at 390/1280 px; all actual page assets/scripts and authenticated API requests are exercised.

account-financial-test-summary.json records every exact case. Counts are not added to the retained 5228 baseline. Earlier development runs are superseded: corrected the corruption fixture trigger/hash column, updated the old financial chart fixture to the intentional new UI, and loaded the actual full stylesheet set in the isolated browser fixture. The first legacy repayment attempt skipped before launch because its capability fixture checked Playwright's default path; the final run used the actual available Chromium path and passed all four, with no final skip.

The late-response test delays a real initial account/subscription response, grants fixture credits through actual resource accounting, reloads after locale change, then releases the stale response and verifies the current wallet remains unchanged. This is transport/UI concurrency acceptance, not a regime cutover test. Private API tests reject anonymous reads, ignore another-owner selectors, preserve owner totals and reject tampered receipt evidence with a generic error. NC excess receipts are shown separately from allocated receipts and another user's allocation remains private. Browser cancellation confirmations can be dismissed without POST; confirmed renewal cancellation traverses the actual API and ledger.

Run from project cwd with PYTHONPATH=.:tests. New tests use MTA_TEST_CHROMIUM_EXECUTABLE and test_r210_noncommercial_collection_browser.nc_browser_config. Existing owner repayment tests use Playwright's default launch/capability lookup. In Work, a test-only launcher outside the project may map BrowserType.launch/executable_path to the same supplied actual Chromium path, merging its required --disable-dev-shm-usage, --no-zygote, --single-process, --use-gl=angle, --use-angle=swiftshader, --enable-unsafe-swiftshader arguments. Tests retain the existing container --no-sandbox flag; no --disable-web-security or production browser configuration is introduced. Launch failures are not suppressed. No runtime browser patch is delivered. Use an installed standard Chromium on normal CI.

The rolled-back environment also lost test dependencies. Restored the previously used pytest 9.1.1, Bandit 1.9.4, Ruff 0.16.10, Playwright 1.58.0, FastAPI/httpx and existing optional mido 1.3.3 etc.; no requirements file or runtime dependency was added. Actual Torch/models, real provider credentials and hardware acceptance remain unexecuted. No inference or model weights were downloaded.

Whole app/native/tests/scripts Ruff, app/scripts compilation and both changed JS syntax checks passed. The source-bound security review was explicitly refreshed for app/account_financial_context.py, app/account_limits.py and the authenticated limits route in app/main.py. All existing warning code matched after line shifts; current scan contains 274 app files, 168 reviewed findings, 0 HIGH/21 MEDIUM/147 LOW, no suppressions/skipped checks. Gate passed. The raw current scan is account-financial-bandit.json; ledger current_scan points to it, and the review test now follows that pointer rather than treating the preceding historical scan as current. This is not automatic approval of unrelated changes or a full external-binary/security certification.

Retained without rerun: full Linux 5228 passed/73 skipped, coverage 73.6774909797391% (70% threshold), C++ 49 passed/5 skipped and runtime audit 31 packages/0 known vulnerabilities. Old Torch/delegated-kernel/Windows/macOS/GPU/model/VST prerequisites are not silently waived by this cycle.

## Remaining work

D4 stays partial: complete account payment/credit/uncertain-checkout/recovery and accessibility/platform acceptance still requires work. This cycle does not enable administrative cutover, settle provider-wide unknown histories, migrate balances, supply missing remote model attestations or implement shared coordination. Continue I1/I3/I4/I5/I7 in KNOWN_BLOCKERS_R210.md. The local static-baseline I8 remains reviewed for the exact current snapshot; refresh it after app changes. Keep formal RC false and switching disabled until all criteria pass.

Suggested cumulative commit (not executed): Integrate dual-regime financial and worker recovery with secure regime-aware account controls
