## Confirmed actual Chromium acceptance — 2026-10-27

Run40505295056,job122192943308,on committed **772fbe7508cc08266466a3746bb51f0fe5d0179b** passes the strict real Chromium acceptance: **9 passed,0 failed,0 skipped**. Includes IT/EN desktop/mobile actual UI/API roundtrip,wallet/period preservation,keyboard/audit,committed failure recovery,original-identity retry after lost response/reload,and refusal for unknown financial history. Chromium134.0.6998.35,Python3.12.15. Exact observation/artifact identity:validation/r210/admin-cutover-chromium-confirmed-40505295056.json. The previously pending nine-case browser prerequisite is now satisfied;do not request or repeat it unchanged.

This validates the restricted default-off local-authority maintenance UI/API profile only. It does not resolve general distributed admission/drain,all provider/legacy financial obligations,or broad C2/C3/C5/D6/E4/E5. Original23/42(54.8%),0/7whole macroareas;RC false. No production transition authorized or server changed. Standard CI on the same SHA remains green (run40480180716). Continue on residual implementation,without another validation-only package or unchanged full CI. Earlier pending-Chromium notes below are historical where superseded.

# Administrative cutover continuation — 2026-10-26 — PRE-RC

**The requested original macroarea closure is not yet accepted.** Original score remains23/42(54.8%),0/7 whole macroareas,RC false. D6,C2,C3,C5,E4,E5 remain pending. This continuation delivers an actual, default-off local maintenance API and operator panel; it does not certify broad provider-history/distributed production switching. Do not narrow the original criteria to this profile and mark a macroarea accepted.

## Implemented actual workflow

`app/regime_admin_cutover.py` derives eligibility from `regime_local_readiness.audit` under an exclusive POSIX service lease and `BEGIN IMMEDIATE`. No HTTP `ready`, observation, callback or supplied financial snapshot can authorize a change. A fresh preview binds source,target,revision,original financial snapshot,verified NC statement hashes and execution-journal presence. A changed preview/epoch is refused. Execution requires an active actual administrator,exact body,explicit confirmation and the existing CSRF marker. Request identity is immutable and retries return/recover only the original operation.

The SQLite reservation,conserving commit,original immutable financial receipt and committed admin audit are one transaction. The barrier stays held across the durable mirror replacement. Finalization rechecks original financial continuity and eligibility,then records the finalizing administrator and releases the barrier in one transaction. Failure/crash before or after the mirror replacement requires forward recovery; no rollback to the prior economic epoch or newly invented balance baseline is offered. A second authorized administrator can recover; both original and finalizing identities/timestamps remain in immutable events. Finalized reservations no longer appear as pending.

The service lease covers complete HTTP response/background lifetime and accounting,execution-queue,billing-outbox and publication-outbox connections across processes on the same local authority. A killed process releases its OS lease but cannot clear the persistent committed barrier. During an interrupted managed cutover,ordinary financial/schema writes are denied on new app connections. Existing authentication/schema/session reads and permitted login/session updates remain available for recovery. No PID expiry or stale-lock-file deletion releases a financial barrier.

The deliberately narrow profile requires explicit `MTA_REGIME_CUTOVER=local-authority-v1`,POSIX local storage and the same current build/data root on every authority process. Default is off; native installations cannot enable it. Existing global `all_entry_points_instrumented=False`,combined readiness and offline RC gates are unchanged. This is additional bounded implementation,not an approval of those broader gates.

## Eligibility and refusals

Required account/provider/payment/lifecycle schemas must already exist and pass integrity/FK checks. Preview never creates missing financial history or defaults. Providers must have no configured credentials/enabled PayPal service and no recorded provider/financial history. Imported/ambiguous credits,unknown financial schemas,priced subscription obligations,termination refunds,negative balances,pending account erasure,unresolved operations and contribution histories refuse admission. Do not erase history,clear credentials or rewrite money to make this check pass; use full financial reconciliation when the profile does not apply.

Positive operator grants with their existing administrator basis,free subscription periods,storage debits backed by the retained wallet and verified NC statements are conserved. Settled registered local CPU jobs can be carried only with matching terminal queue receipts,original finished claims/closed fences,settled contracts,known worker measurement and complete queue-to-ledger ownership. Missing/legacy/ambiguous/active workers,unresolved deferred publication/billing journals,GPU/cgroup/pull histories and other unreviewed financial rows remain blocked by this profile. Actual external merchant completeness and every-executor/cross-host readiness are not inferred from these checks.

A preexisting password/local-TOTP administrator is required so recovery does not depend exclusively on external email authentication. No authentication requirement is disabled. The original provider/legacy evidence gaps remain A4/A5/C3 implementation/domain work; they are not reclassified as merely missing CI.

## Operator UI and API

The administration includes `regime_cutover_panel.js`:IT/EN destination/preview,explicit confirmation,in-flight protection,private paginated audit,forward recovery and retry of the original request after response loss. Session-local hints retain only the request identity/preview across reload;the server remains authoritative. An uncertain request cannot silently turn into a second transition. A received pre-commit409 plus confirmed missing committed identity allows a fresh preview. Committed entries offer recovery,not abort. The existing broad online diagnostics remain disabled separately.

All APIs require actual administrator authentication:

- `GET /api/admin/service-regime/cutovers/preview?target=NON_COMMERCIAL|COMMERCIAL`
- `POST /api/admin/service-regime/cutovers`:exact keys `request_id,target,expected_revision,preview_sha256,confirm`;confirm must be true and revision an exact integer.
- `GET /api/admin/service-regime/cutovers?limit=25&offset=0`
- `GET /api/admin/service-regime/cutovers/{request_id}`:404 means no committed record for that ID.
- `POST /api/admin/service-regime/cutovers/{request_id}/recover`:exact `expected_revision`(new committed epoch),`confirm:true`.

POSTs carry `X-MTA-Request:1`. Never submit synthetic eligibility/provider evidence. No endpoint contacts providers or starts a model. Provision/review an isolated test deployment before opting in; this archive does not authorize modifying a real server.

## Available validation and remaining acceptance

329 affected billing/regime cases and106 execution/outbox/erasure cases pass;26 final API/strict-browser-gate cases pass. Together with42 final source/RC gate cases,these503 distinct current non-browser cases have zero failures/errors/skips. The final26 include actual two-way API wallet/period/history conservation,real built-in harmony subprocess/CPU/NC statement,actual independent-process lease and API SIGKILL recovery,both mirror failure boundaries,login after interruption,stale preview/epoch,CSRF/roles,unknown financial state refusal,immutable audit and separate recovery administrator. No readiness double authorizes their positive API cases. The real harmony algorithm needs no external model;this is not pretrained model/hardware acceptance.

Initial defects corrected without weakening guards:zero-timeout barrier reads raced ordinary SQLite schema commits (bounded normal busy timeout restored);independent child fixture lacked the parent's queue root;reviewed job diagnostics needed original-ledger orphan checks. Security review metadata was restored to its existing string-path contract;the sole failed gate case then passed. UI source review corrected in-flight recovery controls and response-loss/reload wait ordering. Initial failure XML and final reports are retained. An invalid regression filename selection collected nothing,then was corrected;no pass is attributed to it. The execution environment briefly disconnected;completed329/106 results were recovered,not rerun.

Ruff,changed compilation and JS syntax pass. Bandit293 app files/165 existing unsuppressed findings(0 HIGH/21 MEDIUM/144 LOW);31 findings moved only by line insertion,with exact statement/context/disposition identity preserved. New trust dispositions/suppressions:zero. Transport remains30 sites/21 files;call ASTs/checkers unchanged. Exact reports/current hashes: `validation/r210/admin-cutover-result.json` and `admin-cutover-source-gates.json`. No unchanged full CI was rerun.

Actual Chromium is unavailable here. Nine genuine UI/API IT/EN desktop/mobile,recovery,response-loss/reload and blocked-history cases are prepared. The local runner observed9 prerequisite skips and correctly wrote `accepted:false`/exit1. Collection and strict XML parser tests are not browser passes. Original E4/E5 and the integrated macroarea remain unaccepted; the new administration subsection needs actual UI acceptance. No browser result is fabricated.

## Required next user action for UI acceptance

After applying the cumulative and committing at your chosen checkpoint,run **Optional administrative cutover Chromium**,workflow `.github/workflows/admin-cutover-chromium.yml`,input **admin_cutover_chromium=true**. It is manual-only/defaultfalse,read-only repository permissions,no deployment/publication and no provider/server calls. No workflow was dispatched here.

Require artifact `admin-cutover-chromium-<run_id>/acceptance.json` with `accepted:true,passed:9,skipped:0`,the complete matching pytest report and current source hashes. Any missing,duplicate,foreign,failed,errored or skipped case rejects acceptance. This focused run is sufficient for the new UI boundary; do not repeat the unchanged full30-minute CI just for this check. A passing result still does not resolve full provider/legacy/distributed C2/C3/C5/C6 or declare RC.

IT: mantenere il blocco su prove mancanti o saldi diversi;recuperare in avanti con l’identità originale,senza cancellare storico o reinventare una baseline. La macroarea originale resta aperta finché i criteri integrati non passano.

EN: retain the barrier on missing evidence or financial drift;recover forward using the original identity,without deleting history or adopting a new baseline. The original macroarea stays open until its complete integrated criteria pass.
