# r210 — live inference status and web-only controls

Version remains 0.3.0-r210. This is cumulative with the uncommitted duplicate/refresh/socket package.

## Changes

- Web AI Arranger never inserts the native ACE-Step configuration/install/start/stop panel, including before a slow status request completes. It does not request the native desktop status API. Native sessions retain the panel.
- Enforce the HTML hidden state against author CSS display rules; apply a pre-stylesheet guard in the editor HTML. An additional native-only class protects the native manual-save navigation action. Web Open Recent and web Settings remain available.
- The POST acknowledgement no longer presents its provisional queue state as current status. Every active status snapshot replaces the bottom result message with current job ID, state, phase and message. A successful poll clears a previous reconnection message.
- Unavailable GPU readings show a known source label (host Proxmox DRM/AMD-SMI or local process DRM/AMD-SMI), if supplied. Unknown source strings are not rendered. A zero counter remains unavailable, unverified and unbillable; no accounting or security checks were relaxed.
- Static resource cache keys refreshed without changing VERSION or REVISION.

## Validation and limits

Regression tests execute the actual modal builder and watcher JavaScript in Node VM, exercise queued/running/reconnect/completed snapshots, and render the production CSS without JavaScript using WeasyPrint. This is not a live-browser or physical-server certification.

The user's latest report confirms audio generation after restarting LXC/agent, but the GPU source and kernel counter behavior cannot be established from the text message alone. No new diagnostics ZIP was present for this cycle. A new run/diagnostics export is required to investigate why the counter remains zero. No new host agent update is required by these frontend changes; the cumulative project preserves agent package sources 0.3.0-210.2 from the previous package.

The cumulative package also preserves track duplication with independent media/IDs, restoration of the active saved web project on refresh, host-agent runtime directory preservation and mount/socket inspection, earlier Windows startup diagnostics, top-aligned tracks, and earlier inference/diagnostics repairs.

No commit, push, tag, release, server change or container restart was performed.
