r199: ACE-Step LXC wizard supports Debian-family and RHEL-family >=9 with early OS rejection and apt/dnf routing.

# ACE-Step guided clean install / reinstall — Rocky Linux 9 Proxmox LXC

`sudo ./scripts/install_ace_step.sh` is the full interactive first-install wizard. The installer is idempotent and also handles upgrades, reconfiguration, and forced reinstall using `--reinstall`. There is no separate reinstall script.

## Host requirements

On the Proxmox HOST, ensure `amdgpu` supports the Radeon 8060S (`gfx1151`). Bind `/dev/kfd` and the appropriate `/dev/dri/renderD*` into the LXC and allow their **actual**, host-specific character-device major/minor IDs in the LXC cgroup. The tested deployment was Rocky Linux 9.8 inside a Proxmox 7.0.14-pve kernel, where `/dev/kfd` had major 511 and renderD128 major 226. Do not assume these IDs on another host. If unprivileged, map render-group permissions correctly. Do not install amdgpu kernel modules or a new kernel in the LXC.

## Fresh installation

Extract the MTA release ZIP and run from its root:

```bash
sudo ./scripts/install_ace_step.sh --dry-run
sudo ./scripts/install_ace_step.sh
```

The wizard installs Rocky packages (git, Python 3.11, compilers), creates `/opt/mta/venv-ace-step`, installs `torch==2.11.0+rocm7.2` and `torchaudio==2.11.0+rocm7.2`, installs ACE-Step's ROCm requirements, verifies Python dependencies, runs an actual GPU matrix calculation and configures `mta-ace-step.service` on `127.0.0.1:8001` (lazy models). These wheel builds provide ROCm user-space dependencies; the LXC must already have working GPU devices from the Proxmox kernel. This wizard deliberately does **not** install a kernel GPU driver.

By default the wizard queries GitHub tags and displays the most recent stable version; default selection is the already audited **v0.1.8**. A different chosen release has not been validated for the tested ROCm stack. Noninteractive mode uses the pinned stable release:

```bash
sudo ./scripts/install_ace_step.sh --yes --version v0.1.8
```

The script will stop on unsuccessful PyTorch/ROCm GPU verification. It preserves `/var/lib/mta/models`, checks official license presence, saves previous source and venv under timestamped backup names, and does not remove MTA projects. Because a fresh install downloads Python dependencies, allow substantial disk space and outbound network connectivity. A Proxmox snapshot before upgrade is recommended.

## Checks and model initialization

```bash
systemctl status mta-ace-step
journalctl -u mta-ace-step -n 100 --no-pager
curl -fsS http://127.0.0.1:8001/health
curl -fsS -X POST http://127.0.0.1:8001/v1/init -H 'Content-Type: application/json' -d '{"model":"acestep-v15-turbo","init_llm":false}'
```

`models_initialized: false` before `/v1/init` is expected; the first model load may download checkpoint files under persistent storage. Successful HTTP initialization is not a substitute for a real Cover/Remix task. Never expose the ACE-Step API externally: remote MTA clients should go through the authenticated MTA API.

## MTA web server

The ACE-Step wizard installs the AI backend only. MTA itself still requires its own Python environment and configuration; after preparing those, use `scripts/install_mta_lxc_service.sh` from the project root. The native realtime C++/VST3 engine is a separate workstream.

## Persistent installation settings, API port, and firewall

The wizard reads and writes its prior choices to `/etc/mta/ace-step-wizard.conf` (mode 0600): `VERSION`, `PORT`, `BIND`, and `FIREWALL`. On each interactive rerun it proposes those values; it preserves models and skips rebuilding an already installed, unchanged environment. Use `--reinstall` to force a fresh environment build while keeping caches.

Default is TCP **8001** on `127.0.0.1` (local), **no firewall port required**. The user can select another unprivileged port (1024–65535). For `--bind network`, the service listens on `0.0.0.0` and the wizard offers to open that TCP port through an **active** `firewalld` or `ufw`; firewall opening is never required in local mode. Network mode provisions an API key in `/etc/mta/ace-step.env` (root-readable) if none exists; clients must use the key. Proxmox host/datacenter firewalls and router/NAT rules are separate and are **not managed** by this script. Avoid network binding unless necessary, and prefer restricted reverse proxy/TLS.

```bash
sudo ./scripts/install_ace_step.sh --dry-run
sudo ./scripts/install_ace_step.sh --port 8001 --bind local
sudo ./scripts/install_ace_step.sh --reinstall
# Advanced: direct LAN access (secure network required)
sudo ./scripts/install_ace_step.sh --port 8001 --bind network --firewall yes
```

The wizard does not manage kernel AMD GPU drivers in a container.

## Generic Linux installation (r201)

On supported Debian-family or RHEL-family Linux (physical host, VM with GPU passthrough, or LXC with GPU devices forwarded), run `sudo ./scripts/install_ace_step.sh`. For first use after copying the source via a filesystem that loses executable bits, run `chmod +x scripts/install_ace_step.sh`. The script validates `/dev/kfd` and `/dev/dri/renderD*` and does not install a kernel driver. On LXC, configure device passthrough on the host first.
