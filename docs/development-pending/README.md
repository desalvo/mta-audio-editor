# Current status — C2 integrated and accepted — 2026-10-27

The historical patch below has been applied and corrected in the current application. Original C2 is now verified;read ../SERVICE_ADMISSION_DRAIN_R210.md and ../validation/r210/service-admission-result.json. **Do not reapply this patch.** Its old source hashes/preliminary test reports describe the earlier checkpoint only,not current code. Original backup/lifetime/schema/entry/build acceptance is now complete for the supported authority profile;other financial/kernel/target criteria remain open.

## Historical inactive checkpoint (superseded)

# C2 development checkpoint — INACTIVE / NOT ACCEPTED

Saved 2026-10-27 while prioritizing the user-reported export SQLite failure. This is development work to resume,not production code or release evidence. The application contains no service_admission imports/modules from this patch.

`C2_SERVICE_ADMISSION_WIP.patch` records 17 paths relative to the cumulative export-recovery source;its JSON records the exact patch/source hashes and incomplete acceptance work. Apply only in an isolated development copy,review conflicts,and keep ordinary server/provider/GitHub operations unchanged. No new service-admission flag should be enabled on a real server.

Implemented provisionally: durable original-instance/build-bound admission,whole-ASGI lifetime,tracked background work and long-lived capture/VST3 sessions,explicit drain/resume/admin controls,read-only pending audit,HTTPS worker continuation and a new explicit build handoff. No timestamp/PID expiry grants quiescence. Default activation was off. Unknown/lost work remains held. This is a pinned single local authority protocol,not distributed SQLite,HA or proof of cross-host/kernel quiescence.

Preliminary reports are retained under docs/validation/r210:

- service-admission-first.xml:25 passes and one WebSocket fixture annotation failure,corrected later.
- service-admission-and-export-first.xml:55 passes,including26 core admission cases and reused auth/cutover tests.
- service-admission-pull-first.xml:5 passes with actual independent TLS worker processes and dropped claim/completion replies.
- service-admission-regression.xml:95 passes and10 explicit C++20/CMake prerequisite skips;these skips are not successful VST3 acceptance.
- service-admission-initial-regression.xml:zero collected after a misspelled path;not a test pass.

These runs precede the final whole-source fingerprint/upgrade additions. They are NOT current release/criterion acceptance. Original C2 remains implementation_pending. Complete before applying/promoting:

1. Inventory every actual work/admission entry,thread and direct database client;review exceptions with exact source evidence and mutation controls.
2. Test complete capture/VST3 session lifetimes,existing capture finalization and nested predrain work,without claiming hardware/plugin acceptance from fakes.
3. Verify actual main middleware/startup/restart behavior,concurrent multiprocess begin/admission races and all missing/foreign/corrupt identity cases.
4. Verify build mismatch inspection,explicit zero-work upgrade,negative handoff cases and immutable original audit. The latest upgrade code is untested.
5. Review original pending obligations,unknown legacy work,OS lease lifetimes,partial initialization/cleanup and all failure branches. No financial C3 or kernel B2 assumptions.
6. Run the final affected scope,security/source/transport inventories and documented C2 exit criteria. Do not change original wording,denominator,weights or automatic readiness flags to obtain progress.

All source/tests are present in the inert patch. No intermediate package,commit,remote mutation or acceptance promotion was made for this checkpoint.
