# MTA 0.3.0-r208: CI, package iteration and Windows startup

- CI: fix Ruff F401 in `test_r208_ace_cpu_native.py` (unused `os`).
- Server package iteration: RPM `0.3.0-0.208.1.early` and DEB `0.3.0~early.208+pkg1`. Application revision remains **r208**. Existing `0.208.early` RPMs are older; package manager upgrades need newly signed repository publication.
- Windows startup hardening: optional ACE-Step autostart runs in a daemon thread instead of blocking FastAPI startup/pywebview readiness. Failure is logged without preventing UI startup.
- Windows freeze is not yet conclusively diagnosed; run a native Windows smoke/installer test and collect `%LOCALAPPDATA%\MTA Audio Editor` logs if it remains frozen.
- This change is not a substitute for end-to-end RPM/DEB signing, native Windows or GPU hardware tests.
