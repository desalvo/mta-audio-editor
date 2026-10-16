# r210 duplication, refresh restoration and socket visibility validation

Targeted final suite: 31 passed, 1 warning in 2.01s, including actual JS init
restoration and client save-before-duplicate, independent track/clip/insert IDs,
separate media names, persisted-reference rollback before/after commit, Windows
file journal guards, namespace host telemetry, ZIP/API and mount classification.

Broad regression: 3200 passed, 4 skipped, 10 deselected, 4 warnings in 144.09s.
JUnit retained. Four optional Steinberg SDK cases skip; ten known Unix-socket
cases are deselected due to sandbox restrictions. The last duplicate client JS
test was added after collection and passes separately in the final 31-case run.
Ruff F/S checks and Node syntax checks pass.

DEB mta-proxmox-gpu-agent 0.3.0-210.2 built and metadata inspected locally.
Package includes read-only check_mount.py and RuntimeDirectoryPreserve=yes.
No hypervisor/server installation, CT change or live host test performed.

The user attachment proves socket candidates were not visible to MTA and new
inference completed at 100%; it does not distinguish no mount, stale bind mount
or permission/service issues. The new mounted-directory evidence and read-only
host/guest directory comparison are needed to identify the live cause.
GPU attribution/billing remains unverified and non-billable. Windows executable
and browser acceptance are still not claimed from this Linux test environment.
Main version remains 0.3.0-r210 and all preceding project files are retained.
