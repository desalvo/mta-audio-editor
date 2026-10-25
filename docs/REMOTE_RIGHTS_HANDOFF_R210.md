**Current continuation: OPERATOR_REFUNDS_HANDOFF_R210.md. Preserve the historical evidence below; RC false and switching disabled.**

# MTA 0.3.0-r210 — remote transport rights handoff

2026-10-24. PRE-RC. Continuation of FINANCIAL_OUTCOME_HANDOFF_R210.md. **20/42 (47.6%) acceptance milestones, 0/7 whole macroareas; RC false and switching disabled.** F2 coverage expanded; F3/F4 remain pending. No real remote inference, payment, GitHub/server mutation, commit, push, tag or release.

## Authoritative restore and preserved evidence

The local workspace had rolled back. Recovered the saved financial-outcome-integrity cumulative, SHA256 ee1fd7250038ee5be9316d5a6e93d27c4247e5a5a3772c80bb4f77d049a197eb, 93,006,031 bytes, 3585 files. Verified hash, complete ZIP CRC and every source-manifest entry after restoring original modes. The older local tree remains outside the project. All previous validated financial, account, worker and security evidence remains; no full baseline or unrelated financial tests were repeated. Original archive/license/manual/assets and exact Git-tree comparison baseline 0ad84a5fa0c66d75f75882a0f6e5c6a398470dc6 remain preserved without remote Git operations.

## Completed workflow and defects corrected

The existing five routed remote guards could be bypassed by calling the lower transport directly, forwarding raw ACE proxy mutations or running the ACE HTTP adapter as a standalone process. Current model/regime permission is now checked again at those actual boundaries:

- Malformed worker kinds, non-object options and malformed nested model selection are rejected before network I/O (remote-rights-input.xml: 8 passed).
- ai_remote_client.infer_audio checks authorize_remote_execution before source/options serialization and network submission. An earlier decision/context or a direct library call does not grant a reusable permit; current commercial remote denial still applies.
- ai_gateway checks authenticated POST operations before constructing the upstream HTTP client, except the existing query_result polling operation. Native application tokens remain forbidden from proxy POST and must use accounted job endpoints. License/configuration failure returns generic 403 without forwarding bearer credentials, uploading to upstream or creating model work. Existing input-size/auth/path checks remain.
- ace_step_http_worker checks before reading source audio in _run and again before mutation transport in _request. Standalone execution imports the installed packaged policy from its absolute source root, not arbitrary cwd/PYTHONPATH. Loopback HTTP, IPv6 localhost and SSH tunnels are not checkpoint identity and have no commercial exemption. Non-commercial local adapter execution still passes its actual HTTP/subprocess tests; separate worker environments must contain the installed application policy dependencies and fail closed if unavailable.
- Direct ACE gateway requests must remain inside the exact configured path prefix before query/control exemptions are considered. Same-length/sibling prefixes cannot masquerade as polling to bypass the inference guard.
- native_ai_account's device POST helper now accepts only /api/ai-device/start and /poll. It cannot be reused for gateway/inference paths or query aliases. Both legitimate authorization POST paths remain valid.

No runtime dependency/requirements change, automatic local fallback, inference retry or commercial enablement was introduced. Already admitted request status, result retrieval, lists/capabilities/resources and cancellation remain separate from new inference. ACE health, query_result and existing-task control remain available. Their availability still depends on owner authorization, valid identifiers, server response and existing cancellation/receipt semantics; a cancellation request does not prove physical remote worker quiescence. Model policy denial does not erase pending requests or invent a second job.

## Visible native workflow and complete explicit transport review

Native public settings read one private configuration snapshot and return a generic remote_policy state: blocked_unattested in commercial service, model_review_required in non-commercial service and blocked_unverifiable if regime reading fails. No saved token is returned; connection configuration is not execution permission. The shipped openNativeRemoteWorkers dialog shows the corresponding IT/EN message, retaining mode selectors and existing pending/history/recovery controls. Index script version is bumped. This is a diagnostic hint; every actual request still rechecks rights.

The manually reviewed inventory in security/REMOTE_TRANSPORT_REVIEW_R210.json covers **27 explicit transport sites in 19 app Python files**: direct inference, existing-work recovery/metadata, model/source downloads, payment adapters, OAuth/device auth, rights metadata, shared HTTPS and loopback/AF_UNIX telemetry. scripts/check_remote_transport_inventory.py discovers explicit HTTP client/openers and socket constructors including common aliases. It requires exact call shapes, lines/source hashes, checker hash, category and substantial boundary/verification dispositions. A new/missing call, changed reviewed source, changed checker or incomplete disposition fails; it never auto-generates approvals. The machine review is authoritative; the companion Markdown table is readable inventory, not a permission grant.

This is a complete review of the current explicit Python sites identified by this scanner, **not all possible network behavior**. Arbitrary operator executables, native/runtime libraries, dynamically constructed code/networking and exact loaded checkpoint provenance remain separate F4/F3/F6 acceptance. Source hashes and code review are not external worker attestation. The commercial remote path remains denied even when a local model license has a valid review or metering signatures exist. No authenticated model identity/rights exchange was implemented, and no flag can enable it.

## Verification and exact provenance

**213 distinct affected testcases passed, including 4 Chromium dialog cases; no current failures/errors/skips.** validation/r210/remote-rights-test-summary.json lists exact IDs and actual source reports/hashes. Repeated local ACE cases count once using their latest result. remote-rights-current-evidence.xml is a consolidated evidence file, not a fresh suite execution or coverage result.

- remote-rights-existing.xml: 41 passed (routed gates, gateway adapter/proxy and local ACE HTTP/standalone regressions).
- remote-rights-direct.xml: 25 passed (direct commercial/disabled-NC denial, metadata/polling and standalone denial).
- remote-rights-inventory.xml: 17 passed (current inventory, aliases/new transports, source/checker/disposition drift and native path denial).
- remote-rights-recovery-ui.xml: 89 passed (7 new native policy/dialog cases including 4 Chromium, plus affected native routing, transport, history, cancellation and metering-boundary regressions).
- remote-rights-historical.xml: 6 passed (commercial status/recovery/cancel/list/resources/capabilities attempt their own transport without an inference gate or new execution POST).
- remote-rights-loopback.xml: 3 passed; remote-rights-prefix.xml: 4 passed; remote-rights-prefix-positive.xml: 1 passed.
- remote-rights-local-ace.xml: 5 passed after removing the loopback exemption (these repeat five earlier IDs and are not added twice).
- remote-rights-auth-positive.xml: 2 passed; remote-rights-security.xml: 17 passed plus actual source security gate execution.

The standalone denial fixture first lacked an initialized commercial fence; that correctly failed before dispatch. The final fixture initializes the real fence and asserts the subsequent attestation denial before missing-source/DNS processing. No production guard was relaxed to fix the fixture. Final reports above are clean. Transport fakes and ephemeral local test servers were used; no real external inference endpoint, model weights or private remote server was contacted.

Chromium cases execute the exact shipped native dialog function in an isolated modal host and fetch the actual native settings API with the real native-only actor guard, at 390/1280 px in IT/EN. They verify policy text, retained pending/history controls and token privacy. They are not complete editor/OS-native/platform visual acceptance. Existing Chromium 143.0.7499.0 was supplied through MTA_TEST_CHROMIUM_EXECUTABLE and nc_browser_config with the documented container-only no-sandbox/shared-memory/single-process/software-GL flags; no disable-web-security or production browser changes.

Run the affected modules with python3 -m pytest from project root. Test tools were restored after rollback at the previously used pinned versions (pytest 9.1.1, Bandit 1.9.4, Ruff 0.16.10, Playwright 1.58.0 and existing API/test prerequisites); runtime requirements remain unchanged. Whole app/native/tests/scripts Ruff, app/scripts compileall and changed app.js syntax passed. Both python3 scripts/check_security_review.py and python3 scripts/check_remote_transport_inventory.py passed on the delivered source.

The explicit security review covers ai_remote_client.py, ai_gateway.py, ace_step_http_worker.py, native_ai_account.py and native_ai_routing.py. Current raw scan remote-rights-bandit.json: **276 app Python files, 168 visible reviewed findings, 0 HIGH /21 MEDIUM /147 LOW, no suppressions or skipped checks**. Warning code matched the preceding reviewed scan after line shifts; no new warning. The inventory checker is separately reviewed/hash-bound. This does not certify binaries, external models, hardware or deployment security.

Retained without rerun: financial-outcome cycle 243 passing latest cases, prior full Linux 5228 passed/73 skipped, coverage 73.6774909797391% (70% threshold), C++ 49 passed/5 skipped and runtime audit 31 packages/0 known vulnerabilities. Counts overlap and must not be summed. These remain historical baseline evidence rather than complete final-source global CI.

## Remaining implementation and external prerequisites

F3 still needs an authenticated executing-checkpoint/model identity and independently reviewed rights exchange bound to exact admission/execution. F4 still needs all opaque/native/dynamic executor coverage and acceptance; F6 every optional installed checkpoint's independent rights review. Do not equate this transport inventory with completing them. I5 still requires complete provider-wide/legacy obligations, permanent original-subscription loss resolution and actual operator refund workflow; I1 shared coordinator/all-executor/kernel recovery; I4 complete liability migration/cutover; I7 full account/accessibility/native/platform acceptance. Real merchant credentials, isolated writable kernel delegation, authorized model/runtime bundles and target GPU/OS/VST environments remain unavailable, not waived. Continue independent implementation while documenting external blocks.

One remote-rights-transport cumulative ZIP and adjacent SHA256 are delivered with complete source manifest, remote-rights-preservation.json and exact Git-blob comparison. All 3585 input paths and original protected assets/modes are preserved. Output checksum remains adjacent to avoid self-reference. No intermediate ZIP or real-server mutation.

Suggested cumulative English commit, not executed: Integrate r210 studios, dual-regime accounting, safe financial/worker recovery and remote model-rights enforcement
