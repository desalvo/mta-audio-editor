# r210 — Early desktop rebuild discovery

The Windows/macOS Early updater previously compared only VERSION/REVISION.
A rebuilt r210 therefore appeared equal to the installed r210 even when its
embedded BUILD_INFO was newer.

Early desktop installers now include `-bYYYYMMDDHHMMSS` in their filename.
The build stamp comes from the exact BUILD_INFO bundled into that platform's
application. The publication manifest includes a package-name-to-build map.
Stable package naming and stable update availability rules are unchanged.

The native bridge supplies the installed BUILD_ID. Early discovery selects an
installer for Windows x64, macOS arm64 or macOS x64, and compares release first,
then the validated build stamp when the release is equal. Another platform's
build, GitHub publication dates, and the overall rolling-release name cannot
make an old platform installer look newer. Equal/older builds do not trigger
repeated updates or downgrades. When manifest download fails, the build can
still be read from the matching installer filename.

The update dialog displays installed and offered builds. Invalid/unknown build
identities do not fabricate a same-revision update. Existing release/revision
fallbacks remain available for older package names. The CI publication helper
rejects desktop installers without a matching release/build stamp.

## Deployment and validation

The first rebuilt native application containing this fix must be installed
manually if the installed updater cannot detect same-revision rebuilds.
Subsequent Early rebuilds are discovered automatically. Revision stays
0.3.0-r210; BUILD_INFO continues to be stamped by the native CI jobs.

Unit tests cover newer/equal/older builds, release precedence, Windows/macOS
architecture selection, stale-platform manifests, missing manifests, invalid
build identities, publication metadata, bridge argument forwarding and the
actual JavaScript update dialog. Real Windows/macOS packaging and interactive
installation must still be verified in native CI/on-device. Mobile updaters
and Linux repository/package-manager update handling are outside this desktop
fix and are unchanged.
