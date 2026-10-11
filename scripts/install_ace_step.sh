#!/usr/bin/env bash
# MTA ACE-Step first-install/reinstall wizard for Debian-family or RHEL-family Linux systems with AMD ROCm.
set -Eeuo pipefail
REPO=https://github.com/ace-step/ACE-Step-1.5.git
PINNED_SHA=dce621408bee8c31b4fcf4811682eb9359e1bc94
DEFAULT_TAG=v0.1.8
BASE=${MTA_BASE:-/opt/mta}
DATA=${MTA_DATA:-/var/lib/mta}
PYTHON=${MTA_PYTHON:-python3.11}
TORCH_VERSION=${MTA_TORCH_VERSION:-2.11.0+rocm7.2}
INDEX=https://download.pytorch.org/whl/rocm7.2
AUTO_YES=0; DRY_RUN=0; VERSION=${MTA_ACE_VERSION:-}; INSTALL_SYSTEMD=1
CONFIG=${MTA_ACE_WIZARD_CONFIG:-/etc/mta/ace-step-wizard.conf}
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
Usage: sudo ./install_ace_step.sh [--yes] [--version v0.1.8|<40-digit-sha>] [--dry-run] [--no-systemd] [--port 8001] [--bind local|network] [--firewall yes|no] [--reinstall] [--uninstall] [--purge-data]
Interactive Debian >=9 / Debian derivatives, Ubuntu >=22.04, or RHEL family >=9 wizard. Requires /dev/kfd and /dev/dri/renderD* accessible on this system.
Installs Python 3.11, venv, AMD ROCm-enabled PyTorch/torchaudio and ACE-Step dependencies.
The AMD kernel driver must be operational on the host (physical machine, VM, or container host). This wizard does not install kernel drivers.
Persistent models in /var/lib/mta/models are never deleted. Existing sources are backed up.
--yes makes no prompt and uses upstream pinned version v0.1.8 unless --version supplied.
--dry-run checks OS and GPU devices and prints saved settings; no modifications.
--port N selects HTTP port (default 8001); --bind local|network selects reachability.
--firewall yes|no controls opening network port (only if --bind network).
--reinstall forces reinstall of ACE-Step and its Python dependencies.
--uninstall stops/disables the ACE-Step service and removes only wizard-managed installation files; keeps models/data.
--purge-data can be used only with --uninstall; also deletes ACE-Step model cache after explicit confirmation.
HELP
}
while (($#)); do
 case "$1" in
  --yes) AUTO_YES=1;;
  --dry-run) DRY_RUN=1;;
  --no-systemd) INSTALL_SYSTEMD=0;;
  --port) shift; [[ $# -gt 0 ]] || exit 2; PORT_OVERRIDE=$1;;
  --bind) shift; [[ $# -gt 0 ]] || exit 2; BIND_OVERRIDE=$1;;
  --firewall) shift; [[ $# -gt 0 ]] || exit 2; FIREWALL_OVERRIDE=$1;;
  --reinstall) REINSTALL=1;;
  --uninstall) UNINSTALL=1;;
  --purge-data) PURGE_DATA=1;;
  --version) shift; [[ $# -gt 0 ]] || { usage; exit 2; }; VERSION=$1;;
  --help|-h) usage; exit 0;;
  *) echo "Unknown argument: $1" >&2; usage; exit 2;;
 esac
 shift
done
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
printf 'Supported OS: %s (family=%s, major=%s)\n' "${PRETTY_NAME:-$OS_ID}" "$OS_FAMILY" "$OS_MAJOR"
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
render_nodes=(/dev/dri/renderD*)
[[ -c /dev/kfd && -c ${render_nodes[0]} ]] || {
 echo 'ROCm devices unavailable. On bare metal check AMD drivers; in a VM check GPU passthrough; in LXC pass /dev/kfd and /dev/dri/renderD* from the host with correct cgroup permissions.' >&2
 exit 3
}
printf 'Found ROCm devices: /dev/kfd %s\n' "${render_nodes[*]}"
# Present existing settings as defaults. A repeated run should be configuration-only
# if the already installed code and virtualenv are usable.
VERSION=${VERSION:-$SAVED_VERSION}
PORT=${PORT_OVERRIDE:-$PORT}
BIND=${BIND_OVERRIDE:-$BIND}
FIREWALL=${FIREWALL_OVERRIDE:-$FIREWALL}
[[ $PORT =~ ^[0-9]{1,5}$ ]] && (( 10#$PORT >= 1024 && 10#$PORT <= 65535 )) || { echo 'Invalid port: use 1024..65535.' >&2; exit 2; }
PORT=$((10#$PORT))
[[ $BIND == local || $BIND == network ]] || { echo 'Invalid bind: local or network.' >&2; exit 2; }
[[ $FIREWALL == yes || $FIREWALL == no ]] || { echo 'Invalid firewall option: yes or no.' >&2; exit 2; }
if (( DRY_RUN )); then
 printf 'DRY RUN (no modifications): version=%s, port=%s, bind=%s, firewall=%s, base=%s\n' "${VERSION:-$DEFAULT_TAG}" "$PORT" "$BIND" "$FIREWALL" "$BASE"
 exit 0
fi
if (( ! AUTO_YES )); then
 echo 'ACE-Step Linux setup: previous settings appear in brackets. Enter to keep.'
 latest=$(git ls-remote --tags --refs "$REPO" 'refs/tags/v*' 2>/dev/null | sed -nE 's#.*refs/tags/(v[0-9]+\.[0-9]+\.[0-9]+)$#\1#p' | sort -V | tail -n1 || true)
 echo "Latest upstream stable: ${latest:-unavailable}; pinned tested: $DEFAULT_TAG"
 read -r -p "ACE-Step version [${VERSION:-$DEFAULT_TAG}]: " choice; VERSION=${choice:-${VERSION:-$DEFAULT_TAG}}
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
if [[ -z $VERSION ]]; then VERSION=$DEFAULT_TAG; fi
CURRENT_REF=''
if [[ -f "$BASE/ace-step/.mta-installed-ref" ]]; then
 CURRENT_REF=$(cat "$BASE/ace-step/.mta-installed-ref")
fi
if [[ $CURRENT_REF == "$VERSION" && -x "$BASE/venv-ace-step/bin/python" && $REINSTALL == 0 ]]; then
 echo "ACE-Step $VERSION already installed; retaining existing Python environment and checkpoints."
 SKIP_INSTALL=1
else SKIP_INSTALL=0; fi
if (( ! SKIP_INSTALL )); then
# Debian uses apt; RHEL-family uses dnf. Check availability of the required
# Python first, so unsupported repositories fail with an actionable message.
if [[ $OS_FAMILY == debian ]]; then
 apt-get update
 DEBIAN_FRONTEND=noninteractive apt-get install -y git ca-certificates gcc g++ make "$PYTHON" "${PYTHON}-venv" "${PYTHON}-dev" python3-pip
else
 dnf install -y git ca-certificates "$PYTHON" "${PYTHON}-pip" gcc gcc-c++ make
fi
command -v "$PYTHON" >/dev/null || { echo "Python interpreter $PYTHON unavailable on $PRETTY_NAME. Configure a >=3.11 interpreter with MTA_PYTHON." >&2; exit 2; }
if [[ $VERSION =~ ^[0-9a-f]{40}$ ]]; then
 REF=$VERSION
elif [[ $VERSION =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
 REF=$VERSION
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
if [[ $VERSION == "$DEFAULT_TAG" && $sha != "$PINNED_SHA" ]]; then
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
"$VENV/bin/python" -m pip install "torch==$TORCH_VERSION" "torchaudio==$TORCH_VERSION" --index-url "$INDEX"
"$VENV/bin/python" -m pip install -r "$stage/source/requirements-rocm-linux.txt"
"$VENV/bin/python" -m pip check
"$VENV/bin/python" - <<'PYGPU'
import torch, torchaudio
if not torch.__version__.startswith("2.11.0+rocm7.2"):
    raise RuntimeError(f"ACE-Step dependencies replaced pinned PyTorch: {torch.__version__}")
if not torch.version.hip or not torch.cuda.is_available():
    raise RuntimeError('ROCm-enabled PyTorch and GPU access are required')
x = torch.randn((256, 256), device='cuda')
y = x @ x
if not torch.isfinite(y).all().item():
    raise RuntimeError('ROCm GPU computation returned non-finite values')
print('Validated:', torch.__version__, torchaudio.__version__, torch.cuda.get_device_name(0))
PYGPU
if systemctl is-active --quiet mta-ace-step.service; then systemctl stop mta-ace-step.service; fi
if [[ -d "$BASE/ace-step" ]]; then
 BACKUP_SOURCE="$BASE/ace-step.backup.$stamp"
 mv "$BASE/ace-step" "$BACKUP_SOURCE"
fi
mv "$stage/source" "$BASE/ace-step"
printf '%s\n' "$sha" > "$BASE/ace-step/UPSTREAM_COMMIT"
printf '%s\n' "$VERSION" > "$BASE/ace-step/.mta-installed-ref"
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
Description=MTA ACE-Step AMD ROCm inference
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
printf 'PORT=%s\nBIND=%s\nFIREWALL=%s\nVERSION=%s\n' "$PORT" "$BIND" "$FIREWALL" "$VERSION" > "$TMP_CONF"
chmod 600 "$TMP_CONF"
mv -f "$TMP_CONF" "$CONFIG"

printf 'ACE-Step %s ready; listening on %s:%s, firewall=%s.\n' "$VERSION" "${HOST:-not configured}" "$PORT" "$FIREWALL"
echo "Settings saved in $CONFIG"
echo "Check: systemctl status mta-ace-step; curl http://127.0.0.1:$PORT/health"
