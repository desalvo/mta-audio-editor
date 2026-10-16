# r210: LXC host-agent telemetry and tracks anchored at the top

## Prior hardware evidence preserved

The user already tested AMD-SMI/HIP in an unprivileged Proxmox LXC with Radeon
8060S. AMD-SMI process records used host PIDs and GFX remained 0 ns even during
work; later the CLI was absent inside the container. HIP Events worked but were
not certified for per-job billing. The authenticated Proxmox agent connection
was previously verified for CT 130. Do not treat local AMD-SMI in LXC, device
utilization or a zero GFX counter as verified GPU time.

## Application integration

The previous Arranger collector was not connected to the existing host-agent
client. The new collector recognizes LXC from the container environment marker,
/run/systemd/container or cgroup membership. A configured or automatically
found agent socket also enables the agent path independently of LXC detection.
For a local ACE endpoint it tries the authenticated Proxmox host agent first,
then per-process DRM. It never invokes local AMD-SMI in detected LXC or when
using an explicitly selected host agent. Bare-host AMD-SMI remains optional.

Use the existing socket and token configuration:
MTA_AI_GPU_HOST_AGENT_SOCKET, MTA_AI_GPU_HOST_AGENT_TOKEN_FILE (or existing token).
Automatic socket candidates remain /opt/mta-gpu-agent-host/agent.sock and
/run/mta-gpu-agent/agent.sock, with token beside the socket. No path or token
is auto-copied and no new privilege is granted.

The host reports namespace PID, PID namespace inode and process start ticks.
The client must match all three to the ACE service process. A host PID alone,
a cgroup hint, or a missing namespace record never establishes identity. The
host can report per-process DRM counters (duplicate descriptors deduplicated)
or AMD-SMI GFX ns. DRM totals repeated in GPU records are not summed twice.
A missing counter or persistent zero remains unavailable/unverified.

Status/source continue to be stored in the job and ZIP. ZIP also reports detected
environment and privacy-preserving host-agent availability/capability summary.
Raw host identities, cgroup paths and tokens are not included in this summary.
All new GPU values are gpu_seconds_estimated and non-billable. The ACE service
may serve other work; process sampling is not exclusive per-job certification.
No cgroup CPU accounting, cancellation or billing safety check is relaxed.

## Upgrade and functional check

Both sides need this source update:

1. On the Proxmox hypervisor, install mta-proxmox-gpu-agent_0.3.0-210.1_all.deb
   using `dpkg -i` as usual. This optional agent package version is separate
   from the unchanged MTA application release 0.3.0-r210.
2. Build/install the MTA server RPM from this cumulative project.
3. Use the existing socket/token mount already configured for the LXC. Existing
   per-host credentials and tagged-container ACL handling remain unchanged.
4. Run a short inference and download its diagnostic ZIP. Check
   execution_environment=lxc and gpu_host_agent.available/authenticated=true.
   With an active process, namespace_counter_protocol should be true on the new
   agent; a GPU estimate uses proxmox-host-drm or proxmox-host-amd-smi. Local DRM
   may be used if accessible and host counters are absent.

The previously installed agent remains schema-compatible, but lacks the optional
namespace/counter fields. It can still be recognized as available; the collector
reports host_agent_mapping_unavailable rather than guessing attribution. An
agent running an old in-memory version must load the updated executable via its
normal package/service update. No automatic LXC restart/hotplug, kernel change
or privileged-container conversion is introduced. If the driver exposes no valid
counter even on the host, a numeric GPU-time result is still not guaranteed.

## Tracks at the top

The editor has three children: toolbar, clip browser and editor grid. A later CSS
rule overwrote its three rows with two, assigning the flexible row to the clip
browser and pushing the actual tracks into an implicit bottom row. Restore three
explicit rows and assign each child its row. This works for collapsed/expanded
clip browser, including native web UI. Change the CSS/JS cache URLs while keeping
r210. No artificial scroll reset or track ordering change is used for this fix.

## Validation limits

Host/LXC hardware behavior still needs the functional check above. Unit tests use
namespace/counter fixtures and simulated authenticated responses, including old
agents and cross-namespace rejection. The DEB is built and inspected locally,
not installed on a hypervisor. Layout is rendered with WeasyPrint 70, not a live
browser: in the 600px collapsed fixture, editor-grid top changes from 492px to
82px; track and waveform tops remain equal. A Playwright browser download failed
in this environment, so no browser screenshot/acceptance is claimed.

All previous project files/fixes retained; main version 0.3.0-r210 unchanged.
No Git commit, push, tag, release or live host/server operation performed.
