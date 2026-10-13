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
  if [[ ${VERSION_ID:-} != 10* ]] && dnf -q --setopt=timeout=8 --setopt=retries=0 repoquery --available rocm-hip-runtime 2>/dev/null | grep -q rocm-hip-runtime && dnf -q --setopt=timeout=8 --setopt=retries=0 repoquery --available rocminfo 2>/dev/null | grep -q rocminfo; then
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
 # Pin both packages to AMD's configured ROCm repository. EPEL may offer a
 # different rocminfo (e.g. 7.1.0) which cannot satisfy the exact ROCm 7.2.4
 # dependency. Exclude only EPEL's rocminfo for this transaction: keep EPEL
 # available for unrelated dependencies and never permit arbitrary erasures.
 amd_rocm_repo=mta-rocm-userspace
 amd_rocminfo_nevra=$(dnf -q --disablerepo='*' --enablerepo="$amd_rocm_repo" repoquery --available --qf '%{name}-%{epoch}:%{version}-%{release}.%{arch}' rocminfo 2>/dev/null | grep -E '^rocminfo-[0-9]+:' | head -n 1) || true
 if [[ -z $amd_rocminfo_nevra ]]; then
   echo "Official AMD $amd_rocm_repo does not provide rocminfo for EL${VERSION_ID%%.*}/ROCm $ROCM_RELEASE." >&2
   exit 3
 fi
 echo "Pinning AMD ROCm rocminfo: $amd_rocminfo_nevra (not EPEL's package)."
 # EL10: exclude EPEL only while resolving this ROCm transaction. The AMD
 # repository contains both rocm-core and rocm-core-rpath<version>, which
 # claim the same library path: select the standard rocm-core family to
 # prevent a DNF transaction file collision. Do not weaken GPG checking.
 rocm_dnf_options=(--enablerepo="$amd_rocm_repo")
 if [[ ${VERSION_ID%%.*} == 10 ]]; then
   echo 'EL10 ROCm: disabling EPEL for this transaction and excluding the conflicting AMD rocm-core-rpath package.'
   rocm_dnf_options+=(--disablerepo='epel*' --exclude='rocm-core-rpath*')
 else
   rocm_dnf_options+=(--setopt=epel.excludepkgs=rocminfo)
 fi
 if ! dnf install -y "${rocm_dnf_options[@]}" rocm-hip-runtime "$amd_rocminfo_nevra"; then
   echo 'AMD ROCm installation failed. Inspect the complete DNF dependency transaction; no --allowerasing, --skip-broken or --nogpgcheck was used.' >&2
   exit 3
 fi
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
# AMD publishes the CLI/library as amd-smi-lib (not amdrocm-amdsmi) for
# ROCm 7.2.4 on EL10. Install it from the same signed AMD repository used
# for the runtime; never let a similarly named package from EPEL win.
if ! command -v amd-smi >/dev/null 2>&1 && [[ ! -x /opt/rocm/bin/amd-smi ]]; then
 if command -v dnf >/dev/null 2>&1; then
  . /etc/os-release
  if [[ ${VERSION_ID%%.*} == 10 && -f /etc/yum.repos.d/mta-rocm-userspace.repo ]]; then
   echo 'Installing AMD SMI from official AMD ROCm EL10 repository (amd-smi-lib).'
   if dnf -q --disablerepo='*' --enablerepo=mta-rocm-userspace repoquery --available amd-smi-lib 2>/dev/null | grep -q amd-smi-lib; then
    if ! dnf install -y --disablerepo='epel*' --enablerepo=mta-rocm-userspace --exclude='amd-smi-lib-rpath*' amd-smi-lib; then
     echo 'AMD SMI installation failed from the official signed AMD repository; inspect DNF dependencies.' >&2
    fi
   else
    echo 'AMD SMI package amd-smi-lib is not available from the configured AMD repository.' >&2
   fi
  else
   echo 'AMD SMI: install the vendor-provided amd-smi-lib from the matching ROCm repository if available.' >&2
  fi
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
