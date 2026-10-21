# Optional plugins and native media imports — r210

## Fixes dated 20 October 2026

The optional VST3 dialog called server administration endpoints in native apps. Native middleware correctly blocked them, after which the dialog tried to parse the denial message as JSON. Native apps now use dedicated local endpoints for the catalog, licenses, installation, progress and uninstallation. These endpoints are unavailable on web servers. Server administration authorization, CSRF protection for mutations and explicit license consent remain enforced.

Unexpected non-JSON responses now display a readable, localized error including the HTTP status. Individual plugin states and activity bars remain available. Actual installation still requires the C++ toolchain and dependencies documented in the catalog.

YouTube import failed on Windows when synchronizing a journal directory using a POSIX operation. Publication and recovery now share a directory synchronization boundary: Windows retains the existing file-content flushes without attempting POSIX directory descriptors; POSIX retains mandatory directory synchronization and propagates failures. Atomic writes, recovery journals, file identity checks, symlink protection and operation-owned cleanup are preserved. This does not claim POSIX directory-fsync power-loss guarantees on Windows.

## Workspace and saved projects

The Windows native workspace under `%LOCALAPPDATA%\MTA Audio Editor` is intentional. It holds working data and caches; the `.maeprojz` archive stays at the user-selected location, such as Documents. Do not move or delete the workspace manually while a project is open. The fixed failure concerned a directory operation, rather than spaces in the path or AppData itself.

## Verification and limitations

API tests cover native catalog/licenses, the real installation job manager with simulated compilation, polling, uninstall validation, consent/CSRF, server roles and the local endpoint boundary. Chromium tests cover endpoint selection, plugin progress/states and non-JSON errors in English and Italian. Media tests use a local YouTube provider producing real WAV data and check publication, saved-project reload and rollback while POSIX directory opens are rejected. These are neither live YouTube downloads nor Windows-kernel plugin builds.

Windows and macOS CI now run the new API/media regressions. For acceptance on Windows: install the updated build, open the VST3 catalog, install a selected plugin after accepting its license, then import authorized YouTube content, save and reopen the project. Collect diagnostics if the build toolchain or remote provider reports another failure.

Remaining AI Vocal Studio, model and hardware work is tracked in [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md).
