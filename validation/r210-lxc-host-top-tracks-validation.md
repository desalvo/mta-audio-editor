# r210 LXC host GPU and top-aligned tracks validation

47 targeted cases passed, 1 deselected, 1 warning in 6.06s; JUnit confirms
47 tests, zero errors/failures/skips for that selection. Includes host namespace
matching, PID/start-time rejection, legacy-agent behavior, skip of local AMD-SMI
in LXC, host DRM descriptor deduplication, malformed identity rejection, ZIP,
process estimates, package metadata and two actual CSS layout renders.

Broad regression exits 0. Progress log contains 3191 passed and 4 skipped case
markers, no failures. The final terminal summary is absent from that broad log;
counts are from its completed progress records. Ten previously known AF_UNIX
cases were explicitly excluded for this environment's socket restriction. The
two CSS regression tests were added after broad collection and pass separately
and in the 47-case final group.

Layout fixture uses shipped CSS through WeasyPrint 70: collapsed browser in
a 600px editor moves editor-grid top from 492px to 82px; track-head and waveform
lane both move from 522px to 112px. Expanded browser also passes. No browser
screenshot claimed; Playwright browser download unavailable.

Ruff F/S and Node syntax checks pass for changed Python and JavaScript.
Host DEB 0.3.0-210.1 built successfully with dpkg-deb and metadata inspected.
No live package install/service restart, LXC mutation or hardware test performed.
Main application remains 0.3.0-r210; source archive retains every file from the
previous cumulative GPU telemetry package.

Hardware follow-up: update Proxmox host agent and MTA RPM, run inference, collect
ZIP. Authentication/identity matching is not per-job GPU billing certification.
