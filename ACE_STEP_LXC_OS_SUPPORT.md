# ACE-Step LXC wizard: Debian and RHEL-based distributions (r199)

Use `sudo ./scripts/install_ace_step.sh --dry-run` to verify OS and exposed GPU devices before installing anything; use `sudo ./scripts/install_ace_step.sh` for interactive installation.

The installer checks `/etc/os-release` **first**, before any package installation, downloads or filesystem modification. Supported: Debian >=9 and Debian derivatives with comparable releases, Ubuntu >=22.04, Red Hat Enterprise Linux >=9 and derivatives (Rocky, AlmaLinux, CentOS Stream, Oracle Linux) >=9. Debian versions 9–11 may not provide Python 3.11 in their standard repositories; the installer will fail clearly when packages cannot be installed. **Debian 12+ / Rocky 9+ are recommended**. Derivative release numbering may differ: check Python and ROCm packages before using unfamiliar derivatives. Any unsupported OS exits with code 2 and an explanation.

The installer selects `apt-get` and Debian Python packages (`python3.11`, `python3.11-venv`, `python3.11-dev`) on Debian-based systems, and `dnf` plus RHEL Python packages on RHEL-family systems. This installs **ROCm-enabled PyTorch in the virtual environment**, not the host `amdgpu` kernel driver: expose `/dev/kfd` and `/dev/dri/renderD*` from Proxmox. The installer checks both before installing.

To install on a new container, first forward GPU devices from the host Proxmox, then extract the release ZIP and run the script. For Debian, choose a release with Python 3.11 available. A valid exit from the OS gate does not guarantee that a given distro has the required packages and ROCm compatibility; a real clean-install test is still required.

## Generic Linux installation (r201)

On supported Debian-family or RHEL-family Linux (physical host, VM with GPU passthrough, or LXC with GPU devices forwarded), run `sudo ./scripts/install_ace_step.sh`. For first use after copying the source via a filesystem that loses executable bits, run `chmod +x scripts/install_ace_step.sh`. The script validates `/dev/kfd` and `/dev/dri/renderD*` and does not install a kernel driver. On LXC, configure device passthrough on the host first.
