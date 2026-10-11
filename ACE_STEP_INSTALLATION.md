# ACE-Step installation wizard (Linux)

The self-contained Bash script `scripts/install_ace_step.sh` may be downloaded and run **without cloning the entire MTA repository**. It uses Git to fetch the selected upstream ACE-Step source at installation time. The script needs network access, root rights for installation, and a supported Linux OS. Always inspect the script before running downloaded code as root.

```bash
curl -fL -o install_ace_step.sh https://raw.githubusercontent.com/desalvo/mta-audio-editor/main/scripts/install_ace_step.sh
chmod +x install_ace_step.sh
./install_ace_step.sh --dry-run
sudo ./install_ace_step.sh
```

Download a pinned commit/tag or a vetted project release rather than an unreviewed moving `main` for production. The script itself is self-contained, but ACE-Step dependencies and GPU drivers are installed separately and require network and supported hardware.

**Supported OS**: Debian 9+ (Python 3.11 must be available), Ubuntu 22.04+, RHEL/Rocky/AlmaLinux/Oracle/CentOS Stream 9+. Non-supported distributions exit before modification. Bare-metal Linux, VMs with GPU passthrough, and LXC containers with AMD devices mounted are supported as installation targets. ROCm kernel devices must already exist, but PyTorch ROCm packages are installed in the application venv.

## Commands

```bash
./install_ace_step.sh --help
./install_ace_step.sh --dry-run
sudo ./install_ace_step.sh
sudo ./install_ace_step.sh --yes --version v0.1.8
sudo ./install_ace_step.sh --reinstall
sudo ./install_ace_step.sh --uninstall
sudo ./install_ace_step.sh --uninstall --purge-data
```

The wizard remembers the last version, API port (default 8001), local vs network binding, and managed firewall state in `/etc/mta/ace-step-wizard.conf`. Rerunning without changing settings avoids reinstalling the venv and downloading checkpoints. Network binding requires an API key and should be protected by TLS/restricted networks. Host-level Proxmox firewalls are separate.

`--uninstall` stops/disables the ACE-Step service, removes only wizard-owned install and settings, and closes only firewall rules recorded as opened by this wizard. It preserves `/var/lib/mta/models`, user projects, any backups, and unrelated MTA applications. `--purge-data` additionally deletes checkpoint and Hugging Face model caches and API temporary audio, and requires typing `DELETE` interactively; it never deletes projects. Use a backup first. `--yes --uninstall` retains models; `--yes --uninstall --purge-data` is explicitly rejected.

**Caution:** the wizard has not yet been validated end-to-end on every distribution it recognizes. Debian 9 and older derivatives may lack Python 3.11 repositories.
