# r210 task GPU profiler validation

- Focused final regression: 62 passed, 1 warning. Includes the final cleanup refinement: stop the profiler even when post-generation device synchronization fails.
- Broad regression: 3248 passed, 4 skipped (optional Steinberg SDK/ADelay), 10 deselected (AF_UNIX integrations unavailable in this environment), 4 warnings; 126.97 seconds. The final synchronization cleanup and its extra test were verified by the final focused run after this broad run.
- Ruff F/S and Node syntax checks passed.
- Real standalone worker HTTP round trips cover both missing and present profiler endpoints. Tests keep verified GPU seconds absent. The actual ACE hook is tested against a canonical-module server stub and fake ROCm profiling events; task-ID authorization, malformed reports, interval overlap, storage/expiry and failure paths are covered.
- Upstream v0.1.8 hook/CLI reviewed at dce621408bee8c31b4fcf4811682eb9359e1bc94. No upstream sources are included.
- There is no ROCm GPU here. Functional profiling support on the user's Radeon 8060S/LXC remains unverified until an opt-in real inference. No claim of GPU billing eligibility or full server certification.
- Version 0.3.0-r210 retained; no Git commits/push/tags/releases or live server operations performed.
