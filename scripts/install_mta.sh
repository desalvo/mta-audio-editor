#!/usr/bin/env bash
# Standalone, idempotent MTA Audio Editor server installer for Debian/RHEL families.
set -Eeuo pipefail
umask 027
REPO=https://github.com/desalvo/mta-audio-editor.git
CONFIG=${MTA_WIZARD_CONFIG:-/etc/mta/mta-wizard.conf}
APP_DIR=${MTA_APP_DIR:-/opt/mta/application}
VENV=${MTA_APP_VENV:-/opt/mta/venv-mta}
DATA=${MTA_APP_DATA:-/var/lib/mta/projects}
PORT=8080; BIND=network; FIREWALL=no; VERSION=main; ACE_PORT=8001
YES=0; DRY=0; REINSTALL=0; UNINSTALL=0; PURGE=0
O_PORT=''; O_BIND=''; O_FIREWALL=''; O_VERSION=''; O_ACE=''
usage() { cat <<'HELP'
Usage: sudo ./install_mta.sh [--dry-run] [--yes] [--version BRANCH|TAG|SHA] [--port N] [--bind local|network] [--firewall yes|no] [--ace-port N] [--reinstall] [--uninstall] [--purge-data]
Standalone Linux installer: no MTA repository checkout required. Supports Debian 12+, Ubuntu 22.04+, RHEL/Rocky/AlmaLinux/CentOS Stream/Oracle Linux 9+.
Uses /etc/mta/mta-wizard.conf to remember settings; deploys authenticated MTA web app on port 8080 by default.
--uninstall stops/disables service and removes MTA-owned source and Python environment (preserves projects and ACE-Step).
--purge-data with --uninstall also deletes MTA projects ONLY after typing DELETE. Never removes ACE-Step models.
HELP
}
while (($#)); do
 case "$1" in
 --help|-h) usage; exit 0;;
 --yes) YES=1;; --dry-run) DRY=1;; --reinstall) REINSTALL=1;;
 --uninstall) UNINSTALL=1;; --purge-data) PURGE=1;;
 --version|--port|--bind|--firewall|--ace-port)
 k=$1; shift; (($#)) || { echo "Missing value for $k" >&2; exit 2; }
 case "$k" in --version) O_VERSION=$1;; --port) O_PORT=$1;; --bind) O_BIND=$1;; --firewall) O_FIREWALL=$1;; --ace-port) O_ACE=$1;; esac;;
 *) echo "Unknown option: $1" >&2; usage; exit 2;; esac
 shift
done
(( ! PURGE || UNINSTALL )) || { echo '--purge-data requires --uninstall' >&2; exit 2; }
if [[ -f $CONFIG ]]; then
 while IFS='=' read -r key val; do
 case "$key" in
 PORT) [[ $val =~ ^[0-9]{1,5}$ ]] && PORT=$val;;
 BIND) [[ $val == local || $val == network ]] && BIND=$val;;
 FIREWALL) [[ $val == yes || $val == no ]] && FIREWALL=$val;;
 VERSION) [[ $val =~ ^[[:alnum:]_.\/-]+$ ]] && VERSION=$val;;
 ACE_PORT) [[ $val =~ ^[0-9]{1,5}$ ]] && ACE_PORT=$val;;
 esac
 done < "$CONFIG"
fi
PORT=${O_PORT:-$PORT}; BIND=${O_BIND:-$BIND}; FIREWALL=${O_FIREWALL:-$FIREWALL}; VERSION=${O_VERSION:-$VERSION}; ACE_PORT=${O_ACE:-$ACE_PORT}
# Refuse unsupported OS before checking root or mutating filesystem.
OS_RELEASE=${MTA_OS_RELEASE:-/etc/os-release}
[[ -r $OS_RELEASE ]] || { echo 'Unsupported OS: /etc/os-release not found' >&2; exit 2; }
# shellcheck disable=SC1090
SELECTED_VERSION=$VERSION
. "$OS_RELEASE"
VERSION=$SELECTED_VERSION
OS_ID=${ID,,}; MAJOR=${VERSION_ID%%.*}; LIKE=" ${ID_LIKE:-} "
[[ $MAJOR =~ ^[0-9]+$ ]] || { echo "Unsupported OS version: ${VERSION_ID:-unknown}" >&2; exit 2; }
FAMILY=''
case "$OS_ID" in
 debian|ubuntu|linuxmint|pop) FAMILY=debian;;
 rhel|rocky|almalinux|centos|ol|oracle) FAMILY=rhel;;
 *) if [[ $LIKE == *' debian '* || $LIKE == *' ubuntu '* ]]; then FAMILY=debian;
    elif [[ $LIKE == *' rhel '* || $LIKE == *' centos '* ]]; then FAMILY=rhel; fi;;
esac
[[ -n $FAMILY ]] || { echo "Unsupported OS: $OS_ID" >&2; exit 2; }
if [[ $FAMILY == rhel ]]; then
 (( MAJOR >= 9 )) || { echo "Unsupported RHEL-derived OS release: $VERSION_ID (<9)" >&2; exit 2; }
else
 if [[ $OS_ID == ubuntu || $OS_ID == pop ]]; then
  (( MAJOR >= 22 )) || { echo "Unsupported Ubuntu-derived OS release: $VERSION_ID (<22.04)" >&2; exit 2; }
 else
  (( MAJOR >= 12 )) || { echo "Unsupported Debian-derived OS release: $VERSION_ID (need Python 3.11+)" >&2; exit 2; }
 fi
fi
[[ $APP_DIR == /* && $VENV == /* && $DATA == /* && $APP_DIR != / && $VENV != / && $DATA != / ]] || { echo 'Unsafe paths' >&2; exit 2; }
[[ $PORT =~ ^[0-9]+$ && $ACE_PORT =~ ^[0-9]+$ ]] && (( PORT>=1 && PORT<=65535 && ACE_PORT>=1 && ACE_PORT<=65535 )) || { echo 'Invalid port' >&2; exit 2; }
[[ $BIND == local || $BIND == network ]] && [[ $FIREWALL == yes || $FIREWALL == no ]] || { echo 'Invalid network settings' >&2; exit 2; }
[[ $VERSION =~ ^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,120}$ ]] && [[ $VERSION != *'..'* ]] || { echo 'Invalid Git reference' >&2; exit 2; }
if (( DRY )); then printf 'OS=%s %s; source=%s ref=%s; port=%s bind=%s firewall=%s; ACE port=%s; uninstall=%s\n' "$OS_ID" "$VERSION_ID" "$REPO" "$VERSION" "$PORT" "$BIND" "$FIREWALL" "$ACE_PORT" "$UNINSTALL"; exit 0; fi
(( EUID == 0 )) || { echo 'Run as root: sudo ./install_mta.sh' >&2; exit 2; }
command -v systemctl >/dev/null || { echo 'systemd is required' >&2; exit 2; }
ask() { local prompt=$1 current=$2 answer; if (( YES )); then REPLY=$current; else read -r -p "$prompt [$current]: " answer; REPLY=${answer:-$current}; fi; }
if (( ! UNINSTALL )); then
 ask 'MTA Git tag/branch/commit' "$VERSION"; VERSION=$REPLY
 ask 'Web TCP port' "$PORT"; PORT=$REPLY
 ask 'Web binding (network/local)' "$BIND"; BIND=$REPLY
 ask 'Manage host firewall (yes/no)' "$FIREWALL"; FIREWALL=$REPLY
 ask 'ACE-Step port on localhost' "$ACE_PORT"; ACE_PORT=$REPLY
 exec "$0" --dry-run --version "$VERSION" --port "$PORT" --bind "$BIND" --firewall "$FIREWALL" --ace-port "$ACE_PORT" >/dev/null || exit 2
fi
SERVICE=/etc/systemd/system/mta-audio-editor.service
ENVFILE=/etc/mta/mta.env
if (( UNINSTALL )); then
 echo 'Uninstalling MTA web service; preserving ACE-Step and model cache.'
 systemctl disable --now mta-audio-editor.service 2>/dev/null || true
 if [[ -f $SERVICE ]] && grep -q '^Description=MTA Audio Editor' "$SERVICE"; then rm -f "$SERVICE"; fi
 systemctl daemon-reload
 if [[ -f "$CONFIG" ]]; then rm -f "$CONFIG"; fi
 if [[ -f "$ENVFILE" ]] && grep -q '^MTA_DATA_DIR=' "$ENVFILE"; then rm -f "$ENVFILE"; fi
 if [[ -d $APP_DIR && -f $APP_DIR/.mta-wizard-managed ]]; then rm -rf -- "$APP_DIR"; fi
 if [[ -d $VENV && -f $VENV/.mta-wizard-managed ]]; then rm -rf -- "$VENV"; fi
 if (( PURGE )); then
  if (( YES )); then echo 'Refusing noninteractive project data deletion' >&2; exit 2; fi
  read -r -p "Type DELETE to permanently erase MTA projects at $DATA: " answer
  [[ $answer == DELETE ]] && rm -rf -- "$DATA" || echo 'Projects preserved.'
 fi
 echo 'MTA uninstalled. ACE-Step and all AI checkpoints untouched.'; exit 0
fi
if [[ $FAMILY == debian ]]; then
 command -v apt-get >/dev/null || { echo 'apt-get missing' >&2; exit 2; }
 DEBIAN_FRONTEND=noninteractive apt-get update
 DEBIAN_FRONTEND=noninteractive apt-get install -y git ca-certificates python3 python3-venv python3-pip ffmpeg curl
else
 command -v dnf >/dev/null || { echo 'dnf missing' >&2; exit 2; }
 dnf install -y git ca-certificates python3.11 python3.11-pip ffmpeg curl || { echo 'Install ffmpeg from trusted repository and retry; no third-party repository will be added automatically' >&2; exit 3; }
fi
PY=python3
if command -v python3.11 >/dev/null; then PY=python3.11; fi
"$PY" -c 'import sys; assert sys.version_info >= (3,11), "Python >=3.11 required"' || exit 3
# Do not destroy existing working code before a replacement is checked out.
mkdir -p "$(dirname "$APP_DIR")" "$(dirname "$VENV")" /etc/mta "$DATA"
TEMP=$(mktemp -d "$(dirname "$APP_DIR")/.mta-stage.XXXXXXXX")
trap 'rm -rf -- "$TEMP"' EXIT
if [[ -d $APP_DIR/.git && $REINSTALL == 0 ]] && [[ $(git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || :) == $(cat /etc/mta/mta-installed-sha 2>/dev/null || :) ]] && [[ $(cat /etc/mta/mta-installed-ref 2>/dev/null || :) == "$VERSION" ]] && [[ -x $VENV/bin/python ]]; then
 echo 'MTA application and dependencies already installed; configuring service only.'
else
 git clone --quiet "$REPO" "$TEMP/source"
 git -C "$TEMP/source" checkout --quiet "$VERSION"
 [[ -f $TEMP/source/app/main.py && -f $TEMP/source/requirements.txt ]] || { echo 'Invalid MTA source' >&2; exit 3; }
 if [[ -d $APP_DIR && ! -f $APP_DIR/.mta-wizard-managed ]]; then echo "Refusing to replace unmanaged application directory $APP_DIR" >&2; exit 3; fi
 if [[ -d $VENV && ! -f $VENV/.mta-wizard-managed ]]; then echo "Refusing to replace unmanaged Python environment $VENV" >&2; exit 3; fi
 if [[ -d $APP_DIR ]]; then mv "$APP_DIR" "${APP_DIR}.backup.$(date -u +%Y%m%dT%H%M%SZ)"; fi
 mv "$TEMP/source" "$APP_DIR"
 touch "$APP_DIR/.mta-wizard-managed"
 if [[ -d $VENV ]]; then rm -rf -- "$VENV"; fi
 "$PY" -m venv "$VENV"
 touch "$VENV/.mta-wizard-managed"
 "$VENV/bin/python" -m pip install --upgrade pip
 "$VENV/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
 "$VENV/bin/python" -c 'import fastapi, uvicorn, numpy; from app import main' 2>/dev/null || (cd "$APP_DIR" && "$VENV/bin/python" -c 'import app.main')
 chmod 755 "$APP_DIR/app/ace_step_http_worker.py"
 git -C "$APP_DIR" rev-parse HEAD > /etc/mta/mta-installed-sha
 printf '%s\n' "$VERSION" > /etc/mta/mta-installed-ref
fi
if [[ ! -f $ENVFILE ]]; then
 PASS=$("$PY" -c 'import secrets; print(secrets.token_urlsafe(24))')
 cat > "$ENVFILE" <<EOT
MTA_ADMIN_USERNAME=admin
MTA_ADMIN_PASSWORD=$PASS
MTA_DATA_DIR=$DATA
MTA_AI_WORKER_ENABLED=true
MTA_AI_WORKER_EXECUTABLE=$APP_DIR/app/ace_step_http_worker.py
MTA_ACE_STEP_URL=http://127.0.0.1:$ACE_PORT
HF_HOME=/var/lib/mta/models/huggingface
EOT
 echo "Initial admin account: admin; initial password stored in $ENVFILE (root-only)."
else
 sed -i -E "s#^MTA_ACE_STEP_URL=.*#MTA_ACE_STEP_URL=http://127.0.0.1:$ACE_PORT#" "$ENVFILE"
fi
chmod 600 "$ENVFILE"
# Bind to loopback unless network access explicitly selected.
HOST=127.0.0.1; [[ $BIND == network ]] && HOST=0.0.0.0
cat >/etc/mta/mta-wizard.conf.tmp <<EOT
VERSION=$VERSION
PORT=$PORT
BIND=$BIND
FIREWALL=$FIREWALL
ACE_PORT=$ACE_PORT
EOT
chmod 600 /etc/mta/mta-wizard.conf.tmp
mv /etc/mta/mta-wizard.conf.tmp "$CONFIG"
cat > "$SERVICE" <<EOT
[Unit]
Description=MTA Audio Editor web server
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENVFILE
Environment=MTA_HOST=$HOST
Environment=MTA_PORT=$PORT
ExecStart=$VENV/bin/python -m app.main
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
EOT
systemctl daemon-reload
systemctl enable --now mta-audio-editor.service
systemctl restart mta-audio-editor.service
if [[ $BIND == network && $FIREWALL == yes ]]; then
 if command -v firewall-cmd >/dev/null && systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port="${PORT}/tcp"; firewall-cmd --reload
 elif command -v ufw >/dev/null && ufw status | grep -q '^Status: active'; then
  ufw allow "${PORT}/tcp"
 else echo "Firewall not managed or inactive. Allow TCP/$PORT in external hypervisor/cloud firewall if required."; fi
fi
ok=0
for i in $(seq 1 25); do
 if curl --fail --silent --max-time 3 "http://127.0.0.1:$PORT/api/health" >/dev/null; then ok=1; break; fi
 sleep 1
done
if (( ! ok )); then
 echo 'MTA web health check failed. Inspect: journalctl -u mta-audio-editor -n 100' >&2
 systemctl status --no-pager mta-audio-editor.service || :
 exit 4
fi
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "MTA web health OK. Local URL: http://127.0.0.1:$PORT/"
[[ $BIND == network && -n $IP ]] && echo "Network URL: http://$IP:$PORT/ (requires reachable network/firewall)"
echo "Administrator initial credential is stored in $ENVFILE; protect it and change after login."
