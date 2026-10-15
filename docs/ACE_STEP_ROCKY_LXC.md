# MTA + ACE-Step on Rocky Linux 9.8 Proxmox LXC (ROCm Radeon 8060S)

The host passes `/dev/kfd` and `/dev/dri/renderD128` to the LXC. Do not assume fixed device major numbers: this installation observed `511:0` for kfd and `226:128` for the render node. `rocminfo` must report `gfx1151`. An independent smoke test confirmed PyTorch `2.11.0+rocm7.2` matrix multiplication on Radeon 8060S; ACE-Step completed text2music and cover tasks with valid 15s stereo 48kHz/16-bit WAV files. MTA integration **has not** yet been tested end-to-end.

## Reinstalling ACE-Step

Use the single, idempotent installer `scripts/install_ace_step.sh` for fresh installs, upgrades, configuration changes and forced reinstalls (`--reinstall`). It preserves model caches and Python/source backups; the separate reinstall script has been removed.

```bash
sudo ./scripts/install_ace_step.sh --dry-run
sudo ./scripts/install_ace_step.sh
sudo ./scripts/install_ace_step.sh --reinstall
```

See `ACE_STEP_INSTALLATION.md` for port, firewall and persisted settings.

## MTA service in the same LXC

First install MTA source and its own Python runtime, compatible with `requirements.txt` and the target Rocky system. Keep this separate from the ACE-Step Python 3.11 ROCm environment. This service installer deliberately **does not** install MTA's dependencies or choose credentials for you. Create administrator configuration and ensure the MTA app account can write its project directory before enabling it.

```bash
sudo MTA_APP_DIR=/opt/mta/application \
  MTA_APP_PYTHON=/opt/mta/venv-mta/bin/python \
  sudo ./scripts/install_mta.sh
journalctl -u mta-audio-editor -f
```

The installer configures an executable trusted AI worker and loopback endpoint, and writes `/etc/mta/mta.env` only if not already present. Set any administrator credentials and paths required by the application in this environment file. Verify `http://127.0.0.1:8080/api/health` and AI Arranger diagnostics. On a first-time install, ensure filesystem permissions and the app's security configuration are complete before allowing network clients.

## Generic Linux installation (r201)

On supported Debian-family or RHEL-family Linux (physical host, VM with GPU passthrough, or LXC with GPU devices forwarded), run `sudo ./scripts/install_ace_step.sh`. For first use after copying the source via a filesystem that loses executable bits, run `chmod +x scripts/install_ace_step.sh`. The script validates `/dev/kfd` and `/dev/dri/renderD*` and does not install a kernel driver. On LXC, configure device passthrough on the host first.
