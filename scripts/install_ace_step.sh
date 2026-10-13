#!/usr/bin/env bash
# MTA ACE-Step first-install/reinstall wizard for Debian-family or RHEL-family Linux systems with AMD ROCm or CPU-only inference.
set -Eeuo pipefail
REPO=https://github.com/ace-step/ACE-Step-1.5.git
PINNED_SHA=dce621408bee8c31b4fcf4811682eb9359e1bc94
DEFAULT_TAG=v0.1.8
BASE=${MTA_BASE:-/opt/mta}
DATA=${MTA_DATA:-/var/lib/mta}
PYTHON=${MTA_PYTHON:-python3.11}
TORCH_VERSION=${MTA_TORCH_VERSION:-2.11.0+rocm7.2}
INDEX=https://download.pytorch.org/whl/rocm7.2
DEVICE=${MTA_ACE_DEVICE:-auto}
AUTO_YES=0; DRY_RUN=0; ACE_VERSION=${MTA_ACE_VERSION:-}; INSTALL_SYSTEMD=1
CONFIG=${MTA_ACE_WIZARD_CONFIG:-/etc/mta/ace-step-wizard.conf}
BENCHMARK_CONCURRENT=0; BENCHMARK_REMOTE_URL=''; BENCHMARK_TOKENS_FILE=''; BENCHMARK_JOBS_PER_USER=2
BENCHMARK=0; BENCHMARK_PROBE_ONLY=0; BENCHMARK_CONFIG=''; BENCHMARK_OUTPUT=''; BENCHMARK_INSTALL_TOOLS=1
PORT_OVERRIDE=''; BIND_OVERRIDE=''; FIREWALL_OVERRIDE=''; REINSTALL=0; UNINSTALL=0; PURGE_DATA=0
PORT=8001; BIND=local; FIREWALL=no; SAVED_VERSION=''
# Read only known, validated keys; never source a root-owned config as shell code.
if [[ -f "$CONFIG" ]]; then
 while IFS='=' read -r key val; do
  case "$key" in
   PORT) [[ $val =~ ^[0-9]{1,5}$ ]] && PORT=$val ;;
   BIND) [[ $val == local || $val == network ]] && BIND=$val ;;
   FIREWALL) [[ $val == yes || $val == no ]] && FIREWALL=$val ;;
   VERSION) [[ $val =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ || $val =~ ^[a-f0-9]{40}$ ]] && SAVED_VERSION=$val ;;
  esac
 done < "$CONFIG"
fi
usage() {
 cat <<'HELP'
Usage: sudo ./install_ace_step.sh [--benchmark [--benchmark-config file.toml] [--benchmark-output dir] [--benchmark-probe-only] [--benchmark-no-install-tools]] [--yes] [--version v0.1.8|<40-digit-sha>] [--dry-run] [--no-systemd] [--port 8001] [--bind local|network] [--firewall yes|no] [--reinstall] [--uninstall] [--purge-data]
Interactive Debian >=9 / Debian derivatives, Ubuntu >=22.04, or RHEL family >=9 wizard. Supports CPU-only operation; ROCm acceleration requires /dev/kfd and /dev/dri/renderD*.
Installs a supported Python (3.11; system Python 3.12 on EL10), venv, AMD ROCm-enabled PyTorch/torchaudio and ACE-Step dependencies.
The AMD kernel driver must be operational on the host (physical machine, VM, or container host). This wizard does not install kernel drivers.
Persistent models in /var/lib/mta/models are never deleted. Existing sources are backed up.
--device auto|cpu|rocm chooses inference hardware; auto uses CPU if ROCm devices are unavailable.
CPU-only inference is substantially slower and intended for functional use or small jobs.
--yes makes no prompt and uses upstream pinned version v0.1.8 unless --version supplied.
--dry-run checks OS and GPU devices and prints saved settings; no modifications.
--port N selects HTTP port (default 8001); --bind local|network selects reachability.
--firewall yes|no controls opening network port (only if --bind network).
--reinstall forces reinstall of ACE-Step and its Python dependencies.
--uninstall stops/disables the ACE-Step service and removes only wizard-managed installation files; keeps models/data.
--benchmark runs a GPU diagnostic ACE-Step CLI generation; AMD uses amdgpu_top and NVIDIA uses nvidia-smi.
--benchmark-config FILE supplies ACE-Step CLI TOML; otherwise a minimal instrumental generation is used.
--benchmark-output DIR sets the report directory; --benchmark-probe-only skips inference.
--benchmark-no-install-tools does not attempt to install vendor monitoring tools.
--benchmark-concurrent --benchmark-remote-url HTTPS_URL --benchmark-tokens-file FILE (0600) runs concurrent authenticated AI jobs using separate test-user tokens.
--purge-data can be used only with --uninstall; also deletes ACE-Step model cache after explicit confirmation.
HELP
}
while (($#)); do
 case "$1" in
  --benchmark-concurrent) BENCHMARK_CONCURRENT=1;;
  --benchmark-remote-url) shift; [[ $# -gt 0 ]] || exit 2; BENCHMARK_REMOTE_URL=$1;;
  --benchmark-tokens-file) shift; [[ $# -gt 0 ]] || exit 2; BENCHMARK_TOKENS_FILE=$1;;
  --benchmark-jobs-per-user) shift; [[ $# -gt 0 ]] || exit 2; BENCHMARK_JOBS_PER_USER=$1;;
  --benchmark) BENCHMARK=1;;
  --benchmark-config) shift; [[ $# -gt 0 ]] || exit 2; BENCHMARK_CONFIG=$1;;
  --benchmark-output) shift; [[ $# -gt 0 ]] || exit 2; BENCHMARK_OUTPUT=$1;;
  --benchmark-probe-only) BENCHMARK_PROBE_ONLY=1;;
  --benchmark-no-install-tools) BENCHMARK_INSTALL_TOOLS=0;;
  --yes) AUTO_YES=1;;
  --device) shift; [[ $# -gt 0 ]] || exit 2; DEVICE=$1;;
  --dry-run) DRY_RUN=1;;
  --no-systemd) INSTALL_SYSTEMD=0;;
  --port) shift; [[ $# -gt 0 ]] || exit 2; PORT_OVERRIDE=$1;;
  --bind) shift; [[ $# -gt 0 ]] || exit 2; BIND_OVERRIDE=$1;;
  --firewall) shift; [[ $# -gt 0 ]] || exit 2; FIREWALL_OVERRIDE=$1;;
  --reinstall) REINSTALL=1;;
  --uninstall) UNINSTALL=1;;
  --purge-data) PURGE_DATA=1;;
  --version) shift; [[ $# -gt 0 ]] || { usage; exit 2; }; ACE_VERSION=$1;;
  --help|-h) usage; exit 0;;
  *) echo "Unknown argument: $1" >&2; usage; exit 2;;
 esac
 shift
done
if (( BENCHMARK_CONCURRENT )); then
  [[ -n $BENCHMARK_REMOTE_URL && -n $BENCHMARK_TOKENS_FILE ]] || { echo 'Missing --benchmark-remote-url or --benchmark-tokens-file' >&2; exit 2; }
  exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/benchmark_ai_concurrency.py" \
    --url "$BENCHMARK_REMOTE_URL" --tokens-file "$BENCHMARK_TOKENS_FILE" \
    --jobs-per-user "$BENCHMARK_JOBS_PER_USER" \
    --output "${BENCHMARK_OUTPUT:-./ai-concurrency-report.json}"
fi
# Check OS before privilege guard: --dry-run is deliberately usable without sudo.
if (( PURGE_DATA && ! UNINSTALL )); then echo '--purge-data requires --uninstall.' >&2; exit 2; fi
[[ $BASE == /* && $DATA == /* && $BASE != / && $DATA != / ]] || exit 2
# Validate OS before GPU probing, downloading, package operations or writing files.
# MTA_OS_RELEASE permits isolated test fixtures; ignored for actual installs unless root.
OS_RELEASE=${MTA_OS_RELEASE:-/etc/os-release}
[[ -r "$OS_RELEASE" ]] || { echo "Unsupported OS: cannot read $OS_RELEASE" >&2; exit 2; }
# shellcheck disable=SC1090
( . "$OS_RELEASE"; [[ -n ${ID:-} && -n ${VERSION_ID:-} ]] ) || { echo 'Unsupported OS: missing ID/VERSION_ID.' >&2; exit 2; }
. "$OS_RELEASE"
OS_ID=${ID,,}
OS_LIKE=" ${ID_LIKE:-} "
OS_MAJOR=${VERSION_ID%%.*}
[[ $OS_MAJOR =~ ^[0-9]+$ ]] || { echo "Unsupported OS version: ${VERSION_ID:-unknown}" >&2; exit 2; }
OS_FAMILY=''
case "$OS_ID" in
 debian|ubuntu|linuxmint|pop) OS_FAMILY=debian ;;
 rhel|rocky|almalinux|centos|ol|oracle|scientific|redhat) OS_FAMILY=rhel ;;
esac
if [[ -z $OS_FAMILY ]]; then
 case "$OS_LIKE" in
  *' debian '*|*' ubuntu '*) OS_FAMILY=debian ;;
  *' rhel '*|*' centos '*|*' fedora '*) OS_FAMILY=rhel ;;
 esac
fi
case "$OS_FAMILY" in
 debian)
  # Debian numbering != Ubuntu numbering: require a modern baseline there.
  if [[ $OS_ID == ubuntu || $OS_ID == pop ]]; then
   (( OS_MAJOR >= 22 )) || { echo "Unsupported Ubuntu-derived release: $PRETTY_NAME (requires >=22.04)" >&2; exit 2; }
  elif [[ $OS_ID == debian ]]; then
   (( OS_MAJOR >= 9 )) || { echo "Unsupported Debian release: $PRETTY_NAME (requires >=9; Python >=3.11 also required)" >&2; exit 2; }
  else
   (( OS_MAJOR >= 9 )) || { echo "Unsupported Debian derivative: $PRETTY_NAME (requires release >=9 and Python >=3.11)" >&2; exit 2; }
  fi
  command -v apt-get >/dev/null || { echo 'Unsupported Debian derivative: apt-get unavailable.' >&2; exit 2; }
  ;;
 rhel)
  (( OS_MAJOR >= 9 )) || { echo "Unsupported RHEL-family release: $PRETTY_NAME (requires >=9)" >&2; exit 2; }
  command -v dnf >/dev/null || { echo 'Unsupported RHEL derivative: dnf unavailable.' >&2; exit 2; }
  ;;
 *) echo "Unsupported OS: ${PRETTY_NAME:-$OS_ID}; supported Debian family or RHEL family >=9." >&2; exit 2 ;;
esac
# EL10 ships Python 3.12 under python3, not python3.11; respect explicit overrides.
# Never use the system interpreter for pip installations: dependencies live in a venv.
if [[ $OS_FAMILY == rhel && $OS_MAJOR -ge 10 && -z ${MTA_PYTHON:-} ]]; then
 PYTHON=python3
fi
printf 'Supported OS: %s (family=%s, major=%s)\n' "${PRETTY_NAME:-$OS_ID}" "$OS_FAMILY" "$OS_MAJOR"
# Benchmark mode runs independently of the AMD-only ROCm installation path.
# The script lives alongside this wizard and uses an existing ACE-Step installation.
if (( BENCHMARK )); then
 script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
 helper="$script_dir/ace_gpu_benchmark.py"
 [[ -f "$helper" ]] || { echo 'Missing scripts/ace_gpu_benchmark.py alongside wizard.' >&2; exit 2; }
 gpu_vendor=unknown
 if command -v nvidia-smi >/dev/null 2>&1 || [[ -d /proc/driver/nvidia/gpus ]] || grep -qli '0x10de' /sys/class/drm/card*/device/vendor 2>/dev/null; then gpu_vendor=nvidia; fi
 if [[ -c /dev/kfd ]] || grep -qli '0x1002' /sys/class/drm/card*/device/vendor 2>/dev/null; then gpu_vendor=amd; fi
 echo "GPU benchmark mode: detected $gpu_vendor"
 if (( BENCHMARK_INSTALL_TOOLS && ! DRY_RUN )); then
  if [[ $gpu_vendor == amd ]] && ! command -v amdgpu_top >/dev/null; then
   if [[ $EUID -ne 0 ]]; then echo 'amdgpu_top missing: rerun with sudo or use --benchmark-no-install-tools.' >&2; exit 2; fi
   if [[ $OS_FAMILY == debian ]]; then
    apt-get -q update
    DEBIAN_FRONTEND=noninteractive apt-get install -y amdgpu-top || echo 'amdgpu_top unavailable in configured APT repos: install from trusted vendor package.' >&2
   else
    dnf install -y amdgpu_top || echo 'amdgpu_top unavailable in configured DNF repos: install from trusted vendor package.' >&2
   fi
  elif [[ $gpu_vendor == nvidia ]] && ! command -v nvidia-smi >/dev/null; then
   echo 'nvidia-smi is missing: it must match the installed NVIDIA host driver. Attempting distro-provided utilities.' >&2
   if [[ $EUID -ne 0 ]]; then echo 'Rerun with sudo or install matching NVIDIA driver utilities on the host.' >&2; exit 2; fi
   if [[ $OS_FAMILY == debian ]]; then
    pkg=$(apt-cache search '^nvidia-utils-[0-9]+$' | awk '{print $1}' | sort -V | tail -n1)
    if [[ -n $pkg ]]; then DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg" || true; fi
   else
    dnf install -y nvidia-driver-cuda || true
   fi
   command -v nvidia-smi >/dev/null || echo 'nvidia-smi unavailable: configure driver-matched utilities on the VM/LXC or Proxmox host.' >&2
  fi
 fi
 args=(--ace-root "$BASE/ace-step" --python "$BASE/venv-ace-step/bin/python")
 [[ -z $BENCHMARK_CONFIG ]] || args+=(--config "$BENCHMARK_CONFIG")
 [[ -z $BENCHMARK_OUTPUT ]] || args+=(--output-dir "$BENCHMARK_OUTPUT")
 (( ! BENCHMARK_PROBE_ONLY )) || args+=(--probe-only)
 if (( DRY_RUN )); then printf 'DRY RUN: %s %s\n' python3 "$helper"; exit 0; fi
 exec python3 "$helper" "${args[@]}"
fi
# Uninstall is available even if the GPU is no longer connected.
if (( UNINSTALL )); then
 [[ $EUID -eq 0 ]] || { echo 'Run uninstall as root.' >&2; exit 2; }
 echo "Removing wizard-managed ACE-Step service and application; model cache and user data are preserved by default."
 if (( PURGE_DATA )); then
  if (( ! AUTO_YES )); then
   read -r -p 'Permanently delete ACE-Step cached models and generated temporary audio? Type DELETE: ' confirmation
   [[ $confirmation == DELETE ]] || { echo 'Cancelled.'; exit 0; }
  else
   echo 'Data purge cannot run non-interactively. Remove --yes and confirm interactively.' >&2
   exit 2
  fi
 elif (( ! AUTO_YES )); then
  read -r -p 'Uninstall ACE-Step (preserve model cache and user data)? [y/N] ' confirmation
  [[ ${confirmation,,} == y || ${confirmation,,} == yes ]] || { echo 'Cancelled.'; exit 0; }
 fi
 if (( DRY_RUN )); then echo 'Dry-run uninstall: no changes.'; exit 0; fi
 if command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now mta-ace-step.service 2>/dev/null || true
 fi
 unit=/etc/systemd/system/mta-ace-step.service
 if [[ -f $unit ]] && grep -Fq 'ExecStart=' "$unit" && grep -Fq "$BASE/venv-ace-step/bin/python -m acestep.api_server" "$unit"; then
  rm -f "$unit"
  systemctl daemon-reload || true
 fi
 state=/etc/mta/ace-step-firewall.state
 if [[ -f $state ]]; then
  read -r backend old_port < "$state" || true
  if [[ $old_port =~ ^[0-9]{1,5}$ ]]; then
   case "$backend" in
    firewalld) if command -v firewall-cmd >/dev/null && systemctl is-active --quiet firewalld; then firewall-cmd --permanent --remove-port="${old_port}/tcp" && firewall-cmd --reload; fi ;;
    ufw) if command -v ufw >/dev/null; then ufw --force delete allow "${old_port}/tcp"; fi ;;
   esac
  fi
  rm -f "$state"
 fi
 # Restrict destructive paths to the wizard's expected install directories.
 [[ $BASE == /* && $BASE != / && $DATA == /* && $DATA != / ]] || exit 2
 rm -rf -- "$BASE/ace-step" "$BASE/venv-ace-step"
 rm -f -- /etc/mta/ace-step.env "$CONFIG"
 if (( PURGE_DATA )); then rm -rf -- "$DATA/models/checkpoints" "$DATA/models/huggingface" "$DATA/models/tmp/api_audio"; fi
 echo 'ACE-Step uninstalled. All other MTA files and projects were preserved.'
 exit 0
fi
[[ $EUID -eq 0 || $DRY_RUN -eq 1 ]] || { echo 'Run as root on the target Linux system.' >&2; exit 2; }
[[ $DEVICE == auto || $DEVICE == cpu || $DEVICE == rocm ]] || { echo 'Use --device auto|cpu|rocm' >&2; exit 2; }
render_nodes=(/dev/dri/renderD*)
if [[ $DEVICE == auto ]]; then
  if [[ -c /dev/kfd && -c ${render_nodes[0]} ]]; then DEVICE=rocm; else DEVICE=cpu; fi
fi
if [[ $DEVICE == rocm ]]; then
  [[ -c /dev/kfd && -c ${render_nodes[0]} ]] || {
    echo 'ROCm explicitly selected but AMD compute devices are inaccessible. Choose --device cpu or configure host/passthrough devices.' >&2
    exit 3
  }
  printf 'Using ROCm devices: /dev/kfd %s\n' "${render_nodes[*]}"
else
  echo 'WARNING: ACE-Step will run CPU-only. Inference can be much slower than on AMD ROCm GPUs; training on CPU is not recommended.'
fi
# Present existing settings as defaults. A repeated run should be configuration-only
# if the already installed code and virtualenv are usable.
ACE_VERSION=${ACE_VERSION:-$SAVED_VERSION}
PORT=${PORT_OVERRIDE:-$PORT}
BIND=${BIND_OVERRIDE:-$BIND}
FIREWALL=${FIREWALL_OVERRIDE:-$FIREWALL}
[[ $PORT =~ ^[0-9]{1,5}$ ]] && (( 10#$PORT >= 1024 && 10#$PORT <= 65535 )) || { echo 'Invalid port: use 1024..65535.' >&2; exit 2; }
PORT=$((10#$PORT))
[[ $BIND == local || $BIND == network ]] || { echo 'Invalid bind: local or network.' >&2; exit 2; }
[[ $FIREWALL == yes || $FIREWALL == no ]] || { echo 'Invalid firewall option: yes or no.' >&2; exit 2; }
if (( DRY_RUN )); then
 printf 'DRY RUN (no modifications): version=%s, port=%s, bind=%s, firewall=%s, device=%s, base=%s\n' "${ACE_VERSION:-$DEFAULT_TAG}" "$PORT" "$BIND" "$FIREWALL" "$DEVICE" "$BASE"
 exit 0
fi
if (( ! AUTO_YES )); then
 echo 'ACE-Step Linux setup: previous settings appear in brackets. Enter to keep.'
 latest=$(git ls-remote --tags --refs "$REPO" 'refs/tags/v*' 2>/dev/null | sed -nE 's#.*refs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)$#\1#p' | sort -V | tail -n1 || true)
 echo "Latest upstream stable: ${latest:-unavailable}; pinned tested: $DEFAULT_TAG"
 read -r -p "ACE-Step version [${ACE_VERSION:-$DEFAULT_TAG}]: " choice; ACE_VERSION=${choice:-${ACE_VERSION:-$DEFAULT_TAG}}
 read -r -p "API port [$PORT]: " choice; PORT=${choice:-$PORT}
 read -r -p "Reachability local/network [$BIND]: " choice; BIND=${choice:-$BIND}
 if [[ $BIND == network ]]; then
  read -r -p "Open TCP port in container firewall? yes/no [$FIREWALL]: " choice; FIREWALL=${choice:-$FIREWALL}
 else FIREWALL=no; fi
fi
[[ $PORT =~ ^[0-9]{1,5}$ ]] && (( 10#$PORT >= 1024 && 10#$PORT <= 65535 )) || { echo 'Invalid port: 1024..65535.' >&2; exit 2; }
PORT=$((10#$PORT))
[[ $BIND == local || $BIND == network ]] || { echo 'Invalid bind mode.' >&2; exit 2; }
[[ $FIREWALL == yes || $FIREWALL == no ]] || { echo 'Invalid firewall setting.' >&2; exit 2; }
if [[ $BIND == local ]]; then FIREWALL=no; fi
echo "Selected ACE-Step HTTP port: $PORT/tcp; binding=$BIND. Local mode requires NO firewall opening."
if [[ $BIND == network ]]; then
 echo 'WARNING: Network exposure of ACE-Step requires an API key, and preferably a reverse proxy with TLS and access controls.'
fi
if (( ! AUTO_YES )); then
 read -r -p 'Proceed with setup / apply configuration? [y/N] ' answer
 [[ ${answer,,} == y || ${answer,,} == yes ]] || exit 0
fi
# Early idempotent path: identical selected ref and healthy existing environment.
if [[ -z $ACE_VERSION ]]; then ACE_VERSION=$DEFAULT_TAG; fi
CURRENT_REF=''
if [[ -f "$BASE/ace-step/.mta-installed-ref" ]]; then
 CURRENT_REF=$(cat "$BASE/ace-step/.mta-installed-ref")
fi
if [[ $CURRENT_REF == "$ACE_VERSION" && -x "$BASE/venv-ace-step/bin/python" && $REINSTALL == 0 && -f "$BASE/ace-step/.mta-installed-device" && $(cat "$BASE/ace-step/.mta-installed-device") == "$DEVICE" ]]; then
 echo "ACE-Step $ACE_VERSION already installed; retaining existing Python environment and checkpoints."
 SKIP_INSTALL=1
else SKIP_INSTALL=0; fi
if (( ! SKIP_INSTALL )); then
# Debian uses apt; RHEL-family uses dnf. Check availability of the required
# Python first, so unsupported repositories fail with an actionable message.
if [[ $OS_FAMILY == debian ]]; then
 apt-get update
 DEBIAN_FRONTEND=noninteractive apt-get install -y git ca-certificates gcc g++ make "$PYTHON" "${PYTHON}-venv" "${PYTHON}-dev" python3-pip
else
 if [[ $OS_MAJOR -ge 10 && $PYTHON == python3 ]]; then
  dnf install -y git ca-certificates python3 python3-pip gcc gcc-c++ make
 else
  dnf install -y git ca-certificates "$PYTHON" "${PYTHON}-pip" gcc gcc-c++ make
 fi
fi
command -v "$PYTHON" >/dev/null || { echo "Python interpreter $PYTHON unavailable on $PRETTY_NAME. Configure Python 3.11 or 3.12 with MTA_PYTHON." >&2; exit 2; }
PY_VERSION=$($PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
[[ $PY_VERSION == 3.11 || $PY_VERSION == 3.12 ]] || { echo "ACE-Step requires Python 3.11 or 3.12; found $PY_VERSION ($PYTHON)." >&2; exit 2; }
"$PYTHON" -m venv --help >/dev/null 2>&1 || { echo "Python venv unavailable for $PYTHON; install the distribution's matching venv package." >&2; exit 2; }
if [[ $ACE_VERSION =~ ^[0-9a-f]{40}$ ]]; then
 REF=$ACE_VERSION
elif [[ $ACE_VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
 REF=$ACE_VERSION
else
 echo 'Invalid version; use vX.Y.Z or full SHA.' >&2; exit 2
fi
mkdir -p "$BASE" "$DATA/models"/{huggingface,checkpoints,tmp,triton,torchinductor}
# Stage all files before changing an installed working service.
stage=$(mktemp -d "$BASE/.ace-step-wizard.XXXXXXXX")
cleanup(){ [[ ! -d $stage ]] || rm -rf "$stage"; }
trap cleanup EXIT
printf 'Downloading ACE-Step %s...\n' "$REF"
git clone -q --filter=blob:none "$REPO" "$stage/source"
git -C "$stage/source" checkout -q --detach "$REF"
sha=$(git -C "$stage/source" rev-parse HEAD)
[[ $sha =~ ^[0-9a-f]{40}$ && -s $stage/source/LICENSE && -f $stage/source/requirements-rocm-linux.txt ]] || { echo 'Invalid ACE-Step source layout' >&2; exit 4; }
if [[ $ACE_VERSION == "$DEFAULT_TAG" && $sha != "$PINNED_SHA" ]]; then
 echo 'WARNING: pinned release tag no longer matches audited SHA; aborting.' >&2; exit 4
fi
# Keep venv at its final absolute path: Python virtualenvs are not relocatable.
stamp=$(date -u +%Y%m%dT%H%M%SZ)
VENV="$BASE/venv-ace-step"
BACKUP_VENV=''
BACKUP_SOURCE=''
rollback(){
 code=$?
 if (( code != 0 )); then
  if [[ -n "$BACKUP_SOURCE" && -d "$BACKUP_SOURCE" ]]; then
   [[ ! -d "$BASE/ace-step" ]] || mv "$BASE/ace-step" "$BASE/ace-step.failed.$stamp"
   mv "$BACKUP_SOURCE" "$BASE/ace-step"
  fi
  if [[ -n "$BACKUP_VENV" && -d "$BACKUP_VENV" ]]; then
   [[ ! -d "$VENV" ]] || mv "$VENV" "$VENV.failed.$stamp"
   mv "$BACKUP_VENV" "$VENV"
  fi
  echo 'Install failed. Previous installation restored where available.' >&2
 fi
 cleanup
}
trap rollback EXIT
if [[ -d "$VENV" ]]; then
 BACKUP_VENV="$VENV.backup.$stamp"
 mv "$VENV" "$BACKUP_VENV"
fi
"$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install -U pip setuptools wheel
if [[ $DEVICE == rocm ]]; then
  "$VENV/bin/python" -m pip install "torch==$TORCH_VERSION" "torchaudio==$TORCH_VERSION" --index-url "$INDEX"
  "$VENV/bin/python" -m pip install -r "$stage/source/requirements-rocm-linux.txt"
else
  # Install official CPU wheels first. The upstream Python project declares the
  # remaining application dependencies; --no-deps would leave it unusable.
  "$VENV/bin/python" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
  "$VENV/bin/python" -m pip install -e "$stage/source"
fi
"$VENV/bin/python" -m pip check
MTA_EXPECT_ACE_DEVICE="$DEVICE" "$VENV/bin/python" - <<'PYGPU'
import os
import torch, torchaudio
mode = os.environ['MTA_EXPECT_ACE_DEVICE']
if mode == 'rocm':
    if not torch.version.hip or not torch.cuda.is_available():
        raise RuntimeError('ROCm-selected ACE-Step cannot access GPU')
    x = torch.randn((256, 256), device='cuda')
    assert torch.isfinite(x @ x).all().item()
else:
    if torch.version.cuda or torch.version.hip:
        raise RuntimeError('CPU-only ACE-Step unexpectedly installed a GPU torch build')
    assert torch.isfinite(torch.randn((32, 32)) @ torch.randn((32, 32))).all().item()
print('Validated:', mode, torch.__version__, torchaudio.__version__)
PYGPU
if systemctl is-active --quiet mta-ace-step.service; then systemctl stop mta-ace-step.service; fi
if [[ -d "$BASE/ace-step" ]]; then
 BACKUP_SOURCE="$BASE/ace-step.backup.$stamp"
 mv "$BASE/ace-step" "$BACKUP_SOURCE"
fi
mv "$stage/source" "$BASE/ace-step"
printf '%s\n' "$sha" > "$BASE/ace-step/UPSTREAM_COMMIT"
printf '%s\n' "$ACE_VERSION" > "$BASE/ace-step/.mta-installed-ref"
printf '%s\n' "$DEVICE" > "$BASE/ace-step/.mta-installed-device"
[[ -e $BASE/ace-step/checkpoints ]] || ln -s "$DATA/models/checkpoints" "$BASE/ace-step/checkpoints"
fi # new install / forced reinstall
mkdir -p /etc/mta
if [[ ! -f /etc/mta/ace-step.env ]]; then
 cat > /etc/mta/ace-step.env <<ENV
HF_HOME=$DATA/models/huggingface
TRITON_CACHE_DIR=$DATA/models/triton
TORCHINDUCTOR_CACHE_DIR=$DATA/models/torchinductor
ACESTEP_TMPDIR=$DATA/models/tmp
ACESTEP_LM_BACKEND=pt
ACESTEP_USE_FLASH_ATTENTION=false
ACESTEP_NO_INIT=true
ACESTEP_INIT_LLM=false
ENV
 chmod 640 /etc/mta/ace-step.env
fi

# API auth is mandatory for network binding. Preserve an existing API key.
if [[ $BIND == network ]] && ! grep -q '^ACESTEP_API_KEY=.' /etc/mta/ace-step.env; then
 KEY=$("$BASE/venv-ace-step/bin/python" -c 'import secrets; print(secrets.token_hex(32))')
 printf '\nACESTEP_API_KEY=%s\n' "$KEY" >> /etc/mta/ace-step.env
 chmod 600 /etc/mta/ace-step.env
 echo 'Generated API key in /etc/mta/ace-step.env (not printed). Configure clients to provide it.'
fi

# Firewall management: close only a port previously opened by this wizard.
FIREWALL_STATE=/etc/mta/ace-step-firewall.state
old_fw_port=''; old_fw_backend=''
if [[ -r $FIREWALL_STATE ]]; then
 read -r old_fw_backend old_fw_port < "$FIREWALL_STATE" || true
fi
if [[ $FIREWALL == yes && $BIND == network ]]; then
 if command -v firewall-cmd >/dev/null && systemctl is-active --quiet firewalld; then
  fw_backend=firewalld
 elif command -v ufw >/dev/null && ufw status | grep -q '^Status: active'; then
  fw_backend=ufw
 else
  echo 'Requested firewall opening, but no active supported firewall (firewalld/ufw) was found. No firewall rule changed.' >&2
  exit 5
 fi
else fw_backend=''; fi
if [[ -n $old_fw_backend && ( $old_fw_backend != "$fw_backend" || $old_fw_port != "$PORT" ) ]]; then
 case "$old_fw_backend" in
  firewalld) if command -v firewall-cmd >/dev/null && systemctl is-active --quiet firewalld; then firewall-cmd --permanent --remove-port="${old_fw_port}/tcp"; firewall-cmd --reload; fi ;;
  ufw) if command -v ufw >/dev/null; then ufw --force delete allow "${old_fw_port}/tcp"; fi ;;
 esac
 rm -f "$FIREWALL_STATE"
fi
if [[ -n $fw_backend ]]; then
 case "$fw_backend" in
  firewalld) firewall-cmd --permanent --add-port="${PORT}/tcp"; firewall-cmd --reload ;;
  ufw) ufw allow "${PORT}/tcp" ;;
 esac
 printf '%s %s\n' "$fw_backend" "$PORT" > "$FIREWALL_STATE"
 chmod 600 "$FIREWALL_STATE"
fi

if (( INSTALL_SYSTEMD )); then
 HOST=127.0.0.1
 [[ $BIND == network ]] && HOST=0.0.0.0
 UNIT_FILE=/etc/systemd/system/mta-ace-step.service
 NEW_UNIT=$(mktemp)
 cat > "$NEW_UNIT" <<UNIT
[Unit]
Description=MTA ACE-Step inference ($DEVICE)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$BASE/ace-step
EnvironmentFile=/etc/mta/ace-step.env
ExecStart=$BASE/venv-ace-step/bin/python -m acestep.api_server --host $HOST --port $PORT --no-init
Restart=on-failure
RestartSec=10
KillMode=control-group
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
UNIT
 if [[ ! -f "$UNIT_FILE" ]] || ! cmp -s "$NEW_UNIT" "$UNIT_FILE"; then
  mv -f "$NEW_UNIT" "$UNIT_FILE"
  systemctl daemon-reload
  systemctl enable --now mta-ace-step.service
  systemctl restart mta-ace-step.service
 else
  rm -f "$NEW_UNIT"
  systemctl is-active --quiet mta-ace-step.service || systemctl start mta-ace-step.service
 fi
fi
# Persist only validated values; atomic update, private root-owned file.
mkdir -p "$(dirname "$CONFIG")"
TMP_CONF=$(mktemp "${CONFIG}.XXXXXX")
printf 'PORT=%s\nBIND=%s\nFIREWALL=%s\nVERSION=%s\n' "$PORT" "$BIND" "$FIREWALL" "$ACE_VERSION" > "$TMP_CONF"
chmod 600 "$TMP_CONF"
mv -f "$TMP_CONF" "$CONFIG"

printf 'ACE-Step %s ready; listening on %s:%s, firewall=%s.\n' "$ACE_VERSION" "${HOST:-not configured}" "$PORT" "$FIREWALL"
echo "Settings saved in $CONFIG"
echo "Check: systemctl status mta-ace-step; curl http://127.0.0.1:$PORT/health"
