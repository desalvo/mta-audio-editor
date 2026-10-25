# MTA 0.3.0-r210 — complete current web administration acceptance

2026-10-24, Europe/Rome. **PRE-RC. E6 locally verified: 22/42 equal-weight acceptance milestones (52.4%), 0/7 whole macroareas. RC false; switching disabled.** This is not whole-product completion, OS-native/assistive-technology certification or authorization to deploy. No real provider/payment/model/SMTP operation, GitHub/server mutation, commit, push, tag or release.

## Resume and preservation

Input: `MTA-0.3.0-r210-pre-RC-paypal-item-movement-cumulative.zip`, SHA256 `e3858030a43caf314ae40e876b6a517ac9c0f01e02d5cdc31c4617ce1f942c65`, 93,593,153 bytes, 3792 paths. Its complete SHA/CRC and every source-manifest byte/hash/mode matched the local tree before editing. Original offline Git baseline remains `0ad84a5fa0c66d75f75882a0f6e5c6a398470dc6`; no remote checkout/write. All input paths, original protected assets/manuals/licenses and executable modes are preserved.

Resume this cycle from `MTA-0.3.0-r210-pre-RC-admin-accessibility-cumulative.zip` and its adjacent SHA256. Read this document, `RC_CLOSURE_PLAN_R210.md`, `DEVELOPMENT_COMPONENTS_R210.json` and `KNOWN_BLOCKERS_R210.md`. Current inventory/provenance: `validation/r210/admin-preservation.json`, `work-source-manifest.json`, `work-git-comparison.json` and `admin-test-summary.json`. Do not restore an older checkpoint or rerun unaffected baselines. Only one final cumulative ZIP is produced in this cycle.

## Completed scope and actual defects repaired

The current administration consists of `/settings` (also `/admin/users`, with `/admin` redirect), its nine tabs (Web, Storage, Models, Queue, Diagnostics, Users, SMTP, Subscriptions, Legal), `/admin/ai-billing`, `/admin/ai-tokens`, the inline optional-plugin catalogue and the shared floating AI job monitor. Existing read-only regime diagnostics, financial/refund/worker/model-recovery mounts remain functional and retain their backend guards. Future enabled-cutover controls remain separate E4/E5 work.

* Removed the duplicate account-lifecycle forms/IDs from the AI email host. The visible retention inputs now supply the actual saved settings, verified by API/database readback. Kept the email host inside the Users panel. One main landmark and one visible main heading per page; subscription headings no longer introduce a second h1. Decorative logo has an empty alternative.
* Added a localized skip link, tablist/tab/tabpanel relationships, selected state and one tab stop. Left/Right/Home/End invoke the actual existing tab loaders and move focus. No alternate authentication or mutation path is introduced.
* Added real role/quota/rate-date names, including plan + column names for the plan matrix. Search remains disabled until its actual handlers/configuration are ready; failed subscription initialization can retry. Existing user-result keyboard selection loads the actual contract and permission forms.
* Applied a scoped light/dark opaque palette, readable links/badges/disabled controls and visible focus. Corrected inherited dark/gradient styles in expanded subscription and billing forms. Responsive header/form grids wrap; wide tables and technical details scroll inside named keyboard-focusable regions instead of widening the document. Existing owner/editor styling is not globally replaced.
* Fixed persistent initial/retry errors for user/storage/SMTP/Web/model reads; user/model rows clear stale actions. SMTP actions remain disabled until a successful configuration read, with an explicit refresh control. Queue errors are announced; existing diagnostics/legal/social/subscription/billing/token status channels are checked through actual failures and retries.
* Replaced the monitor's ambiguous decorative drag/close glyph text with hidden inline SVG, preserving named controls and drag/arrow behavior. Opening focuses Close; Escape/Close returns to the launcher. Token creation/rotation focuses Copy; hiding clears the secret and returns to the device-name field; completed revocation returns to Refresh. Rotation plus revocation produces two revoked credentials and zero active credentials, verified after completed readback, not stale screen counters.
* Bumped changed shared asset/catalog cache keys. Added nine IT/EN catalogue entries/patterns and preserved the Python/JS catalogue mirror. Runtime dependencies unchanged; axe/Chromium/WeasyPrint are test-only and not shipped in the archive.

## Acceptance matrix and evidence

**330 distinct affected testcases passed, 136 actual Chromium; 44 new cases, all Chromium. Zero current failures/errors/skips.** Counts overlap prior cycles and must not be added to their totals. Exact per-ID latest execution and report SHA256 are in `validation/r210/admin-test-summary.json`; `admin-current-evidence.xml` is a consolidation, not another execution or coverage run.

| Scope | Current acceptance |
| --- | --- |
| 2 regimes × IT/EN × 390/1280 px × light/dark | 16 complete profiles, 13 surfaces each; 208 full-document axe reports |
| All 9 settings tabs, optional catalogue, Billing, Tokens, open job monitor | Real shipped assets, FastAPI/private APIs and local SQLite; all visible details expanded after content readiness |
| Keyboard semantics, headings, names, IDs, focus, scroll and reflow | Real tab navigation, monitor open/Escape/return; every overflowing named region moves with ArrowRight; no document overflow |
| Visible retention/quota saves and dismissed deletion | 4 browser cases; actual saved values read back, protected identity retained, cancelled deletion sends no DELETE |
| User combobox, selected contract and permissions | 4 browser cases; actual contract forms expanded; permission changes persist through API/readback |
| Token creation → hidden → rotation → hidden → revocation | 4 browser cases; previous credential invalidates, new credential authenticates until revoke, focus remains usable, no raw secret in stored axe reports |
| Users/storage/SMTP failed refresh and recovery | 12 browser cases; persistent named errors, stale rows absent, SMTP commands disabled until read succeeds |
| Other initial failures/retries | 4 composite browser cases; Web/social/models/queue/diagnostics/legal/subscriptions/Billing/Tokens; no uncontrolled exception or non-GET side effect |
| Existing financial/regime/refund/movement/NC mounts | 32 + 14 affected cases; existing owner/NC and financial browser checks retained on the changed shared assets |
| Owner pages, locale, lifecycle, job center, layouts, authorization and review gates | Remaining affected regressions; exact classes/cases in the summary |

All **328 administration axe reports** (208 profiles + 120 mutation/error/recovery states) have zero WCAG2/2.1 A/AA automated violations and zero unresolved supplemental items, with no rule exclusions. The explicit supplemental checks measure 3795 opaque clipped/overlaid text targets against their real computed foreground/background (normal/large-text thresholds), reject gradients/opacity/unknown compositing, and review 89 header-only empty tables using the exact axe snapshot. Empty datasets are not fabricated rows or waived headers. This is scoped current web-administration acceptance, not a general WCAG, screen-reader, OS-native or whole-product certificate.

Earlier `admin-accessibility-0..3.xml` and `admin-workflow-initial.xml` are failing development attempts retained for provenance; final delivery and focus reports supersede them. Response/readback waits corrected tests that had read stale values, including the rotated-token counter. WeasyPrint was initially missing during layout collection; both actual layout cases pass in `admin-layout-capability-correction.xml` after test-only installation. No unresolved skip is hidden. Earlier successful profiles were repeated only after changed palette/catalog/complete-content readiness made that necessary. Unrelated full Linux/C++/coverage/model/provider baselines were not repeated.

## Reproduction and security

Run the new modules from project root:

```sh
MTA_TEST_AXE_CORE=/absolute/test-only/axe.min.js \
MTA_TEST_CHROMIUM_EXECUTABLE=/absolute/test-only/chromium \
python3 scripts/run_r210_browser_acceptance.py -q \
  tests/test_r210_admin_accessibility.py tests/test_r210_admin_workflow_acceptance.py
```

Tools used: Chromium 143.0.7499.0, Playwright 1.58.0, axe-core 4.14.0, pytest 9.1.1, WeasyPrint 70.0 for the two existing layout cases. Missing prerequisites are skips, not acceptance. Existing wrapper supplies container-only no-sandbox/dev-shm/single-process/software-GL flags; no web-security disabling or production browser change. Browser routing accepts only `mta.test` and traverses real private APIs; payment transport is the established fixture. No actual SMTP test/send, plugin/model installation/download or inference is invoked.

App/native/tests/scripts Ruff, app/scripts compilation and changed JS syntax pass. `check_security_review.py` and `check_remote_transport_inventory.py` pass unchanged. Full Bandit 1.9.4 source-bound review: **279 app Python files, 168 unsuppressed reviewed findings, 0 HIGH/21 MEDIUM/147 LOW**; raw scan `admin-acceptance-bandit.json`. Only Python source change is the static i18n catalogue cache key: all finding identities/code match the preceding reviewed scan exactly. Ledger source hash refreshed after that explicit review. Transport inventory remains 29 sites/20 files; no new transport or external execution. UI review covers escaped real data labels, unchanged backend authorization/confirmation, scoped styling, semantic-only scroll enhancement and no secret in stored reports.

Historical available Linux 5228 passed/73 skipped, coverage 73.6774909797391% ≥70%, C++ 49 passed/5 skipped and runtime audit 31 packages/0 then-known vulnerabilities are retained historical evidence. They are not current full-target/global CI or a fresh vulnerability scan.

## Remaining work

E6 is locally verified for the current web administration. E4/E5 and all enabled-cutover behavior remain unimplemented, not excused by accessible diagnostics. All other states/criteria are unchanged: A4/A5 global/ambiguous history, authoritative payout/protection proof, legacy obligations and original permanent subscription fee loss; I1/B4 shared coordination/storage, all-executor ownership and crash/quiescence; C2/C3/C5/C6 distributed drain/liability migration/two-way cutover; F3/F4/F6 remote executing-checkpoint rights exchange, opaque executors and independent rights reviews; D6 balances across enabled cutover. Real sandbox, writable delegated-kernel, multi-host/container/target OS/GPU/audio/VST acceptance need their external prerequisites. `RC_CLOSURE_PLAN_R210.md` orders implementation dependencies and separates them from external blocks. No missing implementation is relabelled “external”.

Suggested cumulative English commit, **not executed**: `Integrate r210 studios, dual-regime accounting, durable recovery, PayPal reconciliation and accessible administration`.
