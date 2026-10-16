# r210: duplicate tracks, retain project on refresh, diagnose host socket visibility

The user committed the preceding cumulative release and updated both Proxmox
agent and MTA server. The supplied diagnostic ZIP confirms LXC detection and
completed inference at 100%, with gpu_host_agent.reason=not-configured. This
only means no candidate socket was visible to MTA. It does NOT establish that
no bind mount is configured, nor identify why the socket is not visible.

## Socket lifecycle and diagnosis

Both host installers now set RuntimeDirectoryPreserve=yes. Previously restarting
or upgrading mta-gpu-agent could remove/recreate /run/mta-gpu-agent, while an LXC
bind mount kept referring to the old directory inode. Preserve the runtime
directory across service stop/restart; socket files may be recreated inside it.
The optional host agent DEB is now 0.3.0-210.2. Main app remains 0.3.0-r210.

The application ZIP now includes socket_visibility booleans: directory present,
mount present, socket visible, explicit path configured and access denied. It
never exports the token or arbitrary configured paths. Missing socket inside a
mounted directory, access denial and absence of candidates have distinct reasons.
The UI no longer asserts "mount absent" solely because the socket is missing.

After installing the updated DEB, run this READ-ONLY check on Proxmox (CT 130
is the previously tested container):

    python3 /usr/lib/mta-proxmox-gpu-agent/check_mount.py --ct-id 130

The source equivalent is scripts/check_mta_gpu_agent_mount.py. It compares host
and guest directory device/inode identities and socket type. It never prints
credentials or performs a restart, mount/config mutation, or privilege change.

- host-agent-socket-unavailable: inspect the host agent service first.
- guest-directory-unavailable: guest path cannot be inspected; verify its mount.
- different-directory-or-stale-bind-mount: directories differ; inspect the CT
  mount source. If an old runtime-directory bind mount is confirmed, the updated
  agent prevents recurrence, but a planned full stop/start of that CT is required
  to recreate its already-stale bind mount. A web-app restart cannot repair it.
- same-live-directory-and-socket-visible: filesystem visibility agrees; inspect
  application ZIP authentication/access status next if it still cannot connect.

No CT is restarted automatically. RuntimeDirectoryPreserve does not persist /run
across a hypervisor reboot. Existing per-host tokens and tag/ACL policy remain.
No host update or live check was executed by the assistant. Actual GPU counter
availability and attribution remain unverified until the socket is reachable.

## Duplicate track

Track context menu includes "Duplica traccia". It first saves the current edits,
then invokes an authenticated, origin-protected POST under the existing project
publication lock. The server checks workspace quota and duplicates the source
media with exclusive creation, fsync, inode ownership recording and the existing
upload recovery journal. Rollback consults persisted references, including save
failures after atomic metadata publication. It must not delete committed audio.

The new track is inserted immediately after the source, preserving clips, timeline
offsets, effects, volume, pan, mute/solo, colors and audio properties. Track,
clip and insert IDs are new. Its physical MTA export slot is cleared to avoid
assigning the same hardware slot twice. Original source and copy have independent
filenames and editable metadata. The new track is selected. Windows journal
handling skips the unsupported POSIX directory-open/fsync operation only; file
fsync and atomic replacement remain, and Linux directory barriers are unchanged.

## Reload the page

The web application remembers only the active project ID in sessionStorage,
scoped by authenticated user and browser tab. After initialization/refresh it
reopens that project via the existing authorized server API. No project JSON,
audio, credentials or unsaved edit snapshot is stored in browser storage. An
explicit close clears the entry; native startup-project handling is unchanged.
This retains the open project across reloads and loads its latest saved state;
it does not promise recovery of edits that never reached the server.

Tests exercise the actual JS init/resume helpers and duplicate client handler,
account separation, explicit-close clearing, independent copies, save failure
before/after commit, Windows directory guards, socket/mount classification and
service configuration. See validation report for broad regression and limits.

All earlier fixes, including top-aligned tracks and LXC host telemetry, retained.
No Git operations or live host/server changes. Application version stays r210.
Commit suggested since the newly confirmed user commit:
Add track duplication and refresh restoration, preserve Proxmox agent runtime mounts and improve socket diagnostics
