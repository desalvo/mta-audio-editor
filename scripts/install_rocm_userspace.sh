#!/usr/bin/env bash
# ROCm userspace bootstrap for GPU-enabled MTA AI servers; never installs kernel drivers.
set -Eeuo pipefail
MODE=${1:-auto}
[[ $MODE == auto || $MODE == yes || $MODE == no ]] || { echo 'Usage: install_rocm_userspace.sh [auto|yes|no]' >&2; exit 2; }
if [[ $MODE == no ]]; then echo 'ROCm installation disabled.'; exit 0; fi
if [[ ! -e /dev/kfd || ! -e /dev/dri/renderD128 ]]; then
 if [[ $MODE == yes ]]; then echo 'ROCm requires accessible /dev/kfd and /dev/dri/renderD*; expose GPU devices from Proxmox host first.' >&2; exit 3; fi
 echo 'No accessible AMD compute GPU; skipping ROCm.'; exit 0
fi
# Preserve existing ROCm installations, including installations from other supported distribution channels.
if command -v rocminfo >/dev/null 2>&1 && rocminfo 2>&1 | grep -q 'HSA Agents'; then
 echo 'ROCm runtime detected; preserving installed version.'
else
 [[ ${EUID:-$(id -u)} == 0 ]] || { echo 'ROCm installation needs root.' >&2; exit 3; }
 . /etc/os-release
 if [[ ${ID,,} != rocky && ${ID,,} != rhel && ${ID,,} != almalinux && ${ID,,} != centos && ${ID,,} != ol ]]; then
  echo 'ROCm bootstrap currently supports Rocky/RHEL-family 9. For this OS configure the official AMD ROCm repository first.' >&2; exit 3
 fi
 [[ ${VERSION_ID%%.*} == 9 ]] || { echo 'Automatic ROCm repository bootstrap supports RHEL-family 9 only.' >&2; exit 3; }
 command -v dnf >/dev/null || exit 3
 # AMD's EL9 userspace repository; allow an administrator to pin another AMD release.
 ROCM_RELEASE=${MTA_ROCM_RELEASE:-7.2.4}
 [[ $ROCM_RELEASE =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || { echo 'Invalid MTA_ROCM_RELEASE' >&2; exit 3; }
 repo_file=/etc/yum.repos.d/mta-rocm-userspace.repo
 if [[ ! -f $repo_file ]]; then
  cat > "$repo_file" <<REPO
[mta-rocm-userspace]
name=AMD ROCm ${ROCM_RELEASE} (MTA userspace)
baseurl=https://repo.radeon.com/rocm/el9/${ROCM_RELEASE}/main
enabled=1
gpgcheck=1
gpgkey=https://repo.radeon.com/rocm/rocm.gpg.key
REPO
 fi
 echo 'Installing ROCm userspace; never installing amdgpu-dkms or kernel drivers.'
 dnf install -y rocm-hip-runtime rocminfo || { echo 'ROCm installation failed. Check AMD support for this distribution version and selected ROCm release.' >&2; exit 3; }
 command -v rocminfo >/dev/null 2>&1 || { echo 'rocminfo is still unavailable after installation.' >&2; exit 3; }
fi
if ! command -v amd-smi >/dev/null 2>&1; then
 if command -v dnf >/dev/null 2>&1; then
  dnf install -y amdrocm-amdsmi || { echo 'AMD SMI not installed; configure matching official AMD ROCm repositories.' >&2; exit 3; }
 else
  echo 'AMD SMI missing; install amdrocm-amdsmi through your supported system package manager.' >&2; exit 3
 fi
fi
if ! command -v amd-smi >/dev/null 2>&1; then
 for executable in /opt/rocm/bin/amd-smi /opt/rocm/core-*/bin/amd-smi; do
  if [[ -x $executable ]]; then ln -sf "$executable" /usr/local/bin/amd-smi; break; fi
 done
fi
command -v amd-smi >/dev/null 2>&1 || { echo 'AMD SMI installed but executable not found.' >&2; exit 3; }
rocminfo >/dev/null || { echo 'ROCm runtime cannot access AMD GPU.' >&2; exit 3; }
amd-smi version >/dev/null || { echo 'AMD SMI cannot initialize.' >&2; exit 3; }
echo 'ROCm/AMD SMI userspace verified. GPU billing is NOT enabled by this installer.'
