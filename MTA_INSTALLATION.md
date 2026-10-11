# MTA Audio Editor web installation wizard

`install_mta.sh` is executable and **standalone**: you can download just the script without checking out the complete repository. It fetches the selected MTA source from GitHub and installs runtime dependencies. Read any installer before executing as root.

```bash
curl -fL -o install_mta.sh https://raw.githubusercontent.com/desalvo/mta-audio-editor/main/scripts/install_mta.sh
chmod +x install_mta.sh
./install_mta.sh --dry-run
sudo ./install_mta.sh
```

The wizard recognizes Debian 12+, Ubuntu 22.04+, and Red Hat/Rocky/AlmaLinux/CentOS Stream/Oracle Linux 9+. Other Linux distributions are rejected before changing the system. Works on bare metal, VMs, or LXC with systemd and working networking. A GPU is **not required** for the MTA web server itself; optional AI acceleration requires separately running ACE-Step.

Interactive settings: selected Git ref (`main` default; pin tags or commit hashes for production), HTTP port (8080 default), bind (`network` for browser access from other devices, or `local`), firewall action (`no` default), and optional localhost ACE-Step port (8001 default). Choices survive in `/etc/mta/mta-wizard.conf`, while root-only service credentials are stored in `/etc/mta/mta.env`. An initial administrator login is bootstrapped at first launch; check that root-only file to retrieve the generated password, then change it in the app.

```bash
sudo ./install_mta.sh --yes --version main --port 8080 --bind network --firewall yes
sudo ./install_mta.sh                       # reconfigure/update selected Git ref
sudo ./install_mta.sh --reinstall           # force Python environment reconstruction
sudo ./install_mta.sh --uninstall           # preserve MTA projects and ACE-Step
sudo ./install_mta.sh --uninstall --purge-data # requires typing DELETE to delete MTA projects
```

On completion, a successful local `/api/health` check is required and the wizard prints the local URL plus the host's network URL when applicable. Opening a host firewall rule does *not* open a Proxmox datacenter/VM firewall or external cloud firewall. If the host lacks an available FFmpeg repository, installation stops with diagnostics; configure trusted repositories and retry. TLS/reverse proxy is strongly advised outside trusted private networks. The installer does not expose ACE-Step by default.

Services: `mta-audio-editor.service` (MTA) and, optionally, separately managed `mta-ace-step.service` (AI). Check with `systemctl status mta-audio-editor` and `journalctl -u mta-audio-editor -e`. Run the ACE-Step wizard separately if you want GPU-assisted AI Arranger/Remix; MTA installation itself needs no GPU.

**Important:** end-to-end installation on each OS family has not been exercised in CI. The wizard should be validated first on a disposable VM/LXC snapshot. The installation creates backups of previous wizard-managed source installations; the uninstall operation leaves these backups untouched.
