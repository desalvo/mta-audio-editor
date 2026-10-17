# MTA Audio Editor 0.3.0-r210 — Cumulative integration

Base: MTA-r209-fix-windows-test-ruff-f401-cumulative.zip.
Integrated in order: the complete r210 patch (apply.py, apply_all.py, apply_complete.py) plus final-gpu-workaround.

Features: server-side workspace Save As, recent projects for web accounts, AI Arranger modal completion and terminal progress, public /health alias, FastAPI lifespan, PyMuPDF compatible import, persist optional trustworthy worker-reported CPU/GPU seconds, and a best-effort ACE-Step local process estimator (AMD-SMI per-PID GFX ns and /proc CPU time). Process estimates are displayed as approximate, and are never used for billing.

Preserved from r209: Windows native-startup diagnostics, ACE-Step existing-venv initialization, DNF upgrade handling, RPM .2 release ordering, GitHub Pages/GitHub Releases publisher fixes.

Identity updated: REVISION/RELEASE, Android/iOS metadata, Windows version information, browser JavaScript cache key, and static regression assertions. Application VERSION remains 0.3.0. No Git operations performed.

Validation: 17 focused tests passed after final source edits; additional focused batch of 24 passed before platform metadata synchronization; py_compile/compileall passed. The full pytest run exceeded execution time and was NOT validated; CI, RPM/DEB building and real Windows/ROCm tests must be completed before deployment.

Caveats: AMD-SMI process GFX nanoseconds are machine/driver-dependent and can include unrelated activity by the same process. If unsupported, usage stays N/A; not for billing. Review the Save As endpoint with actual persisted media and server-authenticated accounts.
