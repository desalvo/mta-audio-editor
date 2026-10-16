# Validation — r210 live status and web controls

- Targeted: 25 passed, including actual Node modal/watcher execution, CSS hidden/native rendering, duplicate/refresh/socket regressions, zero GPU exclusion and telemetry labels.
- Broad regression: 3204 passed, 4 skipped (optional Steinberg SDK/ADelay), 10 deselected (AF_UNIX integrations unavailable in this execution environment), 4 warnings. Complete output and JUnit included.
- Node syntax: app.js and admin.js passed. Ruff F/S: new regression file passed.
- The modal guard was refined while the broad suite ran; final targeted tests were rerun after the final edit. The additional web/native modal test is covered by that final targeted run.
- Physical ROCm/LXC, slow real browser connection and Windows acceptance have not been executed here. The GPU counter remains unverified; no security or billing checks changed.
- VERSION=0.3.0, REVISION=210. No Git operations or live server operations.
