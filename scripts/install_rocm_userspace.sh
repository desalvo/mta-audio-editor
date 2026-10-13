#!/usr/bin/env bash
# ROCm userspace bootstrap for GPU-enabled MTA AI servers; never installs kernel drivers.
set -Eeuo pipefail
MODE=${1:-auto}
[[ $MODE == auto || $MODE == yes || $MODE == no ]] || { echo 'Usage: install_rocm_userspace.sh [auto|yes|no]' >&2; exit 2; }
if [[ $MODE == no ]]; then echo 'ROCm installation disabled.'; exit 0; fi
render_nodes=(/dev/dri/renderD*)
if [[ ! -c /dev/kfd || ! -c ${render_nodes[0]} ]]; then
 if [[ $MODE == yes ]]; then echo 'ROCm requires /dev/kfd and /dev/dri/renderD*. For a VM configure AMD GPU passthrough and host drivers; for LXC pass those devices and allow cgroup access. Kernel drivers must be installed on the host, never inside a container.' >&2; exit 3; fi
 echo 'No accessible AMD compute GPU; skipping ROCm.'; exit 0
fi
# Preserve existing ROCm installations, including installations from other supported distribution channels.
if command -v rocminfo >/dev/null 2>&1 && rocminfo 2>&1 | grep -q 'HSA Agents'; then
 echo 'ROCm runtime detected; preserving installed version.'
else
 [[ ${EUID:-$(id -u)} == 0 ]] || { echo 'ROCm installation needs root.' >&2; exit 3; }
 . /etc/os-release
 # First use already configured, trusted distribution/vendor package repositories.
 if command -v dnf >/dev/null 2>&1; then
  if dnf -q --setopt=timeout=8 --setopt=retries=0 repoquery --available rocm-hip-runtime 2>/dev/null | grep -q rocm-hip-runtime && dnf -q --setopt=timeout=8 --setopt=retries=0 repoquery --available rocminfo 2>/dev/null | grep -q rocminfo; then
   echo 'Trying ROCm userspace from currently enabled DNF repositories.'
   dnf install -y rocm-hip-runtime rocminfo || echo "Existing repositories did not provide a complete ROCm runtime; checking official AMD ROCm repository." >&2
  fi
 elif command -v apt-get >/dev/null 2>&1; then
  if apt-cache show rocminfo >/dev/null 2>&1 && apt-cache show rocm-hip-runtime >/dev/null 2>&1; then
   echo 'Trying ROCm userspace from currently enabled APT repositories.'
   DEBIAN_FRONTEND=noninteractive apt-get install -y rocminfo rocm-hip-runtime || :
  fi
 fi
 if ! command -v rocminfo >/dev/null 2>&1; then
  if [[ ${ID,,} != rocky && ${ID,,} != rhel && ${ID,,} != almalinux && ${ID,,} != centos && ${ID,,} != ol ]]; then
   echo "ROCm packages were unavailable. Use AMD's official ROCm install guide for ${PRETTY_NAME:-$ID}, configure its signed repository, then rerun this wizard: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/" >&2
   exit 3
  fi
  if [[ ${VERSION_ID%%.*} != 9 && ${VERSION_ID%%.*} != 10 ]]; then
   echo "Unsupported EL${VERSION_ID%%.*}; see https://rocm.docs.amd.com/en/latest/install/rocm.html" >&2
   exit 3
  fi
  command -v dnf >/dev/null || exit 3
 # AMD official EL9/EL10 userspace repository; no kernel driver or EL9/EL10 cross-installation.
 ROCM_RELEASE=${MTA_ROCM_RELEASE:-7.2.4}
 [[ $ROCM_RELEASE =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || { echo 'Invalid MTA_ROCM_RELEASE' >&2; exit 3; }
 repo_file=/etc/yum.repos.d/mta-rocm-userspace.repo
 if [[ -f $repo_file ]] && ! grep -Fqx "baseurl=https://repo.radeon.com/rocm/el${VERSION_ID%%.*}/${ROCM_RELEASE}/main" "$repo_file"; then
  echo "Existing $repo_file has a different ROCm OS/release. Refusing to overwrite it; review manually." >&2; exit 3
 fi
 if [[ ! -f $repo_file ]]; then
  cat > "$repo_file" <<REPO
[mta-rocm-userspace]
name=AMD ROCm ${ROCM_RELEASE} (MTA userspace)
baseurl=https://repo.radeon.com/rocm/el${VERSION_ID%%.*}/${ROCM_RELEASE}/main
enabled=1
gpgcheck=1
gpgkey=https://repo.radeon.com/rocm/rocm.gpg.key
REPO
 fi
 echo 'Installing ROCm userspace from AMD official EL repository; never installing amdgpu-dkms or kernel drivers.'
 dnf install -y rocm-hip-runtime rocminfo || { echo 'ROCm installation failed. Check AMD support for this distribution version and selected ROCm release.' >&2; exit 3; }
 fi
 # AMD's official EL10 repositories install tools under /opt/rocm on some layouts.
if ! command -v rocminfo >/dev/null 2>&1; then
 for binary in /opt/rocm/bin/rocminfo /opt/rocm/core-*/bin/rocminfo; do
  if [[ -x $binary ]]; then
   install -d -m 755 /usr/local/bin
   ln -sfn "$binary" /usr/local/bin/rocminfo
   break
  fi
 done
fi
command -v rocminfo >/dev/null 2>&1 || { echo 'rocminfo is still unavailable after installation. Check /opt/rocm/bin and the package transaction.' >&2; exit 3; }
fi
if ! command -v amd-smi >/dev/null 2>&1; then
 if command -v dnf >/dev/null 2>&1; then
  dnf install -y amdrocm-amdsmi || echo 'AMD SMI is unavailable in enabled repositories; ROCm compute can still work. Consult the official AMD ROCm documentation.' >&2
 else
  echo 'AMD SMI missing; install its matching package from the vendor repository if GPU telemetry is required.' >&2
 fi
fi
if ! command -v amd-smi >/dev/null 2>&1; then
 for executable in /opt/rocm/bin/amd-smi /opt/rocm/core-*/bin/amd-smi; do
  if [[ -x $executable ]]; then ln -sf "$executable" /usr/local/bin/amd-smi; break; fi
 done
fi
command -v amd-smi >/dev/null 2>&1 || echo 'Warning: AMD SMI unavailable; GPU accounting/telemetry may need additional configuration.' >&2
rocminfo >/dev/null || { echo 'ROCm runtime cannot access AMD GPU.' >&2; exit 3; }
if command -v amd-smi >/dev/null 2>&1; then amd-smi version >/dev/null || echo 'Warning: AMD SMI failed to initialize.' >&2; fi
echo 'ROCm/AMD SMI userspace verified. GPU billing is NOT enabled by this installer.'
