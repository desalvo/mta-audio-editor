# r210 Windows native startup: diagnostic repair and user-writable paths

The supplied native-startup.log reports Uvicorn startup failure (SystemExit 3)
but does not contain the original ASGI lifespan exception. This does not establish
an Intel CPU, RAM, GPU or model incompatibility. Hardware-specific conclusions
remain unverified.

## Changes in this cumulative archive

- Native startup selects <native user data>/diagnostics by default, via
  MTA_DIAGNOSTIC_DIR before importing the application. Windows therefore uses
  LOCALAPPDATA/MTA Audio Editor/diagnostics instead of the Linux server default
  /var/lib/mta/diagnostics. Explicit operator overrides are retained.
- The native server attaches its rotating UTF-8 log file handler directly to
  uvicorn.error. Uvicorn logs the original lifespan traceback there before
  raising SystemExit(3); windowed executables have no stderr to display it.
  Existing logger handlers/level/disabled state are restored on thread exit.
- Existing fail-fast readiness, HTTP health requirement and bounded timeout remain.
  Errors are not bypassed and the application does not pretend to be ready.

## Evidence and limits

A real Uvicorn 0.54.0 startup with an injected PermissionError, and both console
streams absent, now writes the original PermissionError and Application startup
failed into native-startup.log. This reproduces and repairs the loss of error
information; the injected error is not the user's proven original failure.
Native directory default/override, existing readiness checks and diagnostics API
regressions pass (12 cases). Ruff passes for the changed launcher and test file.

An independent subprocess also started the actual app.main application via the
native launcher, with a fresh temporary user directory and stdout/stderr=None:
/api/health reached HTTP 200; shutdown completed without startup exception.
This host is Linux/Python 3.12, not Windows 11 or a frozen PyInstaller executable.
No Windows machine reproduction or hardware certification is claimed.

The user must build/install the updated Windows native executable, then launch
normally. If it still fails, send the newly generated file at
%LOCALAPPDATA%\MTA Audio Editor\logs\native-startup.log; this build records the
previously missing original exception. Do not delete projects or reset user data.

All fixes from MTA-0.3.0-r210-diagnostics-ui-acestep-startup-cumulative.zip remain,
including the diagnostics settings panel, standalone ACE-Step worker startup,
allowlisted failure events, and fail-closed accounting. Version stays 0.3.0-r210.
No Git commit/push/tag/release or live server change performed.

Suggested cumulative commit if no commit was made after the last delivered ZIP:
Fix r210 diagnostics UI and ACE-Step worker startup, capture native lifespan failures and use per-user diagnostic storage
