# Export polling / SQLite contention hotfix — 2026-10-26

## Observed defect and correction

The reported GET `/api/media-jobs/{id}`500 originates in `session_user -> init_auth_db -> executescript`,not an encoder exception. The authentication initializer ran CREATE statements and `INSERT OR IGNORE INTO smtp_config` on every request. An existing SQLite writer can therefore make otherwise read-only export polling fail. Normal project-owner access additionally called `account_lifecycle.info`,which initialized its schema/defaults repeatedly. Automatic browser-language persistence could also request the writer slot during API polling.

`auth._auth_schema_ready` now inspects actual required authentication columns,index,SMTP default row and bootstrap condition using SELECTs. A complete existing installation returns without DDL/default insertion/bootstrap writes. Missing tables/columns/index/defaults still take the original initialization/migration path;an empty installation still provisions its configured administrator. No process/path readiness cache can hide a replaced database. Lock/corruption errors are not swallowed as successful initialization.

`account_lifecycle.info` reads an already complete lifecycle schema directly;missing migration columns still invoke the existing initializer. Managed-cutover recovery retains its read-only/schema-preservation boundary. API requests still detect their effective language from headers/preferences,but automatic browser-language persistence occurs on page navigation rather than every background API poll. Explicit profile language changes are retained and tested.

No encoder settings,ledger/money,authentication/ACL requirements,SQLite journal mode or database timeout was changed. This fixes the reproduced unnecessary-writer contention;it does not claim that readers can bypass an externally held EXCLUSIVE/corrupt database or that the actual server deployment has been modified.

## Reproduction and validation

Eleven new regression cases use actual SQLite,real authenticated non-admin project ownership and FFmpeg. A separate connection keeps `BEGIN IMMEDIATE` and an uncommitted write throughout export start,polling and download. The harmless-looking old initializer write is a negative control:it really fails with `database is locked`,while the corrected authentication/lifecycle reads succeed. The fixture uses a short real SQLite busy timeout to expose regressions quickly;it does not mock database operations or encoder results.

Six real exports cover project and individual-track jobs × MP3/WAV/FLAC. Each completes,all polls/downloads return200 under the held writer,and ffprobe verifies the downloaded codec. Polling also carries a different automatic browser-language header,without acquiring the preference writer slot. Unauthenticated access is refused. Additional cases prove missing language/index/SMTP default migration and bootstrap after switching to a different actual database.

58 distinct affected functional tests pass,11 new,zero failures/errors/skips:auth/session/profile/password/social login,language behavior,exports and the actual local cutover/SIGKILL/recovery regression. One current source-security agreement test also passes;59 distinct current cases including that gate. Earlier503 passes are historical evidence for their recorded source/boundaries,not another full-suite run or a count added to this batch. Exact reports/hashes: `validation/r210/export-auth-contention-result.json`.

Ruff app/scripts/tests and changed compilation pass. Bandit293 app sources/165 existing unsuppressed findings(0 HIGH/21 MEDIUM/144 LOW). Relocated findings retain identical statement/context and prior dispositions;no new suppression,scanner/checker change or automatically approved trust boundary. Transport30 sites/21 files;network call ASTs unchanged. Exact current source review: `validation/r210/export-auth-contention-source-gates.json`.

## Delivery and resume

Complete cumulative: `MTA-0.3.0-r210-pre-RC-export-sqlite-hotfix-cumulative.zip`,plus SHA256. It includes this correction and every prior uncommitted change after9fc85ce79bee9871696dea9396565395a415aa72,including the default-off admin cutover/API/UI/opt-in CI work. Use the complete source cumulative;do not copy only a file with new imports onto an older incomplete installation. Original assets,licenses,manuals,historical logs and file modes are preserved;full manifest/CRC/hashes verified.

No commit/staging,push,CI dispatch,provider call or real-server change was performed. Suggested cumulative English commit:

`Fix export polling database contention and harden cumulative cutover, execution and billing recovery`

Original RC acceptance stays23/42(54.8%),0/7 macroareas,RC false. This runtime bug fix does not close the general financial/distributed transition criteria. The existing9-case manual `Optional administrative cutover Chromium` workflow remains pending for the prior new UI;no Chromium rerun or complete30-minute CI was needed to reproduce and verify this SQLite hotfix. Standard CI on the user's eventual commit remains useful integration evidence;actual RC still needs its original remaining criteria.

IT: durante il polling si legge lo schema già completo;non si tenta più una scrittura di inizializzazione o della lingua ad ogni richiesta. Migrazioni e autenticazione restano effettive. EN:polling reads an already complete schema;it no longer requests an initialization or locale write on each request. Real migrations and authentication stay enforced.
