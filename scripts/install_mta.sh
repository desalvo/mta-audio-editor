#!/usr/bin/env bash
# Standalone, idempotent MTA Audio Editor server installer for Debian/RHEL families.
set -Eeuo pipefail
umask 027
REPO=https://github.com/desalvo/mta-audio-editor.git
CONFIG=${MTA_WIZARD_CONFIG:-/etc/mta/mta-wizard.conf}
APP_DIR=${MTA_APP_DIR:-/opt/mta/application}
VENV=${MTA_APP_VENV:-/opt/mta/venv-mta}
DATA=${MTA_APP_DATA:-/var/lib/mta/projects}
PORT=8080; BIND=network; FIREWALL=no; VERSION=main; ACE_PORT=8001; ACE_URL=
HTTPS=no; TLS_MODE=self-signed; TLS_CERT=; TLS_KEY=; TLS_NAME=localhost
YES=0; DRY=0; REINSTALL=0; UNINSTALL=0; PURGE=0
O_PORT=''; O_BIND=''; O_FIREWALL=''; O_VERSION=''; O_ACE=''; O_ACE_URL=''
O_HTTPS=''; O_TLS_MODE=''; O_TLS_CERT=''; O_TLS_KEY=''; O_TLS_NAME=''
usage() { cat <<'HELP'
Usage: sudo ./install_mta.sh [--dry-run] [--yes] [--version BRANCH|TAG|SHA] [--port N] [--bind local|network] [--firewall yes|no] [--ace-port N] [--ace-url https://host:port] [--https yes|no] [--tls-mode existing|self-signed] [--tls-cert /absolute/path] [--tls-key /absolute/path] [--tls-name DNS-or-IP] [--reinstall] [--uninstall] [--purge-data]
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
 --version|--port|--bind|--firewall|--ace-port|--ace-url|--https|--tls-mode|--tls-cert|--tls-key|--tls-name)
 k=$1; shift; (($#)) || { echo "Missing value for $k" >&2; exit 2; }
 case "$k" in --version) O_VERSION=$1;; --port) O_PORT=$1;; --bind) O_BIND=$1;; --firewall) O_FIREWALL=$1;; --ace-port) O_ACE=$1;; --ace-url) O_ACE_URL=$1;; --https) O_HTTPS=$1;; --tls-mode) O_TLS_MODE=$1;; --tls-cert) O_TLS_CERT=$1;; --tls-key) O_TLS_KEY=$1;; --tls-name) O_TLS_NAME=$1;; esac;;
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
 ACE_URL) ACE_URL=$val;;
 HTTPS) [[ $val == yes || $val == no ]] && HTTPS=$val;;
 TLS_MODE) [[ $val == existing || $val == self-signed ]] && TLS_MODE=$val;;
 TLS_CERT) TLS_CERT=$val;;
 TLS_KEY) TLS_KEY=$val;;
 TLS_NAME) TLS_NAME=$val;;
 esac
 done < "$CONFIG"
fi
PORT=${O_PORT:-$PORT}; BIND=${O_BIND:-$BIND}; FIREWALL=${O_FIREWALL:-$FIREWALL}; VERSION=${O_VERSION:-$VERSION}; ACE_PORT=${O_ACE:-$ACE_PORT}; ACE_URL=${O_ACE_URL:-$ACE_URL}
HTTPS=${O_HTTPS:-$HTTPS}; TLS_MODE=${O_TLS_MODE:-$TLS_MODE}; TLS_CERT=${O_TLS_CERT:-$TLS_CERT}; TLS_KEY=${O_TLS_KEY:-$TLS_KEY}; TLS_NAME=${O_TLS_NAME:-$TLS_NAME}
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
# Parse remote HTTPS URL without loading arbitrary shell configuration.
if [[ -n $ACE_URL ]]; then
 if [[ ! $ACE_URL =~ ^https://([a-zA-Z0-9][a-zA-Z0-9.-]{0,251}):([0-9]{1,5})$ ]]; then
  echo 'Invalid remote ACE-Step URL: use https://hostname:port (TLS required).' >&2; exit 2
 fi
 ACE_REMOTE_HOST=${BASH_REMATCH[1]}; ACE_REMOTE_PORT=${BASH_REMATCH[2]}
 (( 10#$ACE_REMOTE_PORT >= 1 && 10#$ACE_REMOTE_PORT <= 65535 )) || { echo 'Invalid ACE-Step remote port' >&2; exit 2; }
fi
[[ $HTTPS == yes || $HTTPS == no ]] && [[ $TLS_MODE == existing || $TLS_MODE == self-signed ]] || { echo 'Invalid HTTPS mode' >&2; exit 2; }
# Cert and key must be ordinary absolute paths, safe for systemd EnvironmentFile.
for tls_path in "$TLS_CERT" "$TLS_KEY"; do
 [[ -z $tls_path || ( $tls_path == /* && $tls_path != *[[:space:]]* && $tls_path != *'..'* && $tls_path != *'\'* ) ]] || { echo 'Invalid TLS path' >&2; exit 2; }
done
[[ $TLS_NAME =~ ^[a-zA-Z0-9][a-zA-Z0-9.:-]{0,252}$ ]] || { echo 'Invalid TLS certificate name' >&2; exit 2; }
if [[ $HTTPS == yes && $TLS_MODE == existing ]]; then
 [[ -n $TLS_CERT && -n $TLS_KEY ]] || { echo 'Existing TLS mode requires --tls-cert and --tls-key' >&2; exit 2; }
fi
[[ $BIND == local || $BIND == network ]] && [[ $FIREWALL == yes || $FIREWALL == no ]] || { echo 'Invalid network settings' >&2; exit 2; }
[[ $VERSION =~ ^[a-zA-Z0-9][a-zA-Z0-9._/-]{0,120}$ ]] && [[ $VERSION != *'..'* ]] || { echo 'Invalid Git reference' >&2; exit 2; }
if (( DRY )); then printf 'OS=%s %s; source=%s ref=%s; port=%s bind=%s firewall=%s; ACE port=%s; HTTPS=%s mode=%s; uninstall=%s\n' "$OS_ID" "$VERSION_ID" "$REPO" "$VERSION" "$PORT" "$BIND" "$FIREWALL" "$ACE_PORT" "$HTTPS" "$TLS_MODE" "$UNINSTALL"; exit 0; fi
(( EUID == 0 )) || { echo 'Run as root: sudo ./install_mta.sh' >&2; exit 2; }
command -v systemctl >/dev/null || { echo 'systemd is required' >&2; exit 2; }
ask() { local prompt=$1 current=$2 answer; if (( YES )); then REPLY=$current; else read -r -p "$prompt [$current]: " answer; REPLY=${answer:-$current}; fi; }
if (( ! UNINSTALL )); then
 ask 'MTA Git tag/branch/commit' "$VERSION"; VERSION=$REPLY
 ask 'Web TCP port' "$PORT"; PORT=$REPLY
 ask 'Web binding (network/local)' "$BIND"; BIND=$REPLY
 ask 'Enable HTTPS for the MTA web interface (yes/no)' "$HTTPS"; HTTPS=$REPLY
 if [[ $HTTPS == yes ]]; then
  ask 'TLS certificate mode (existing/self-signed)' "$TLS_MODE"; TLS_MODE=$REPLY
  if [[ $TLS_MODE == existing ]]; then
   ask 'TLS certificate absolute path' "$TLS_CERT"; TLS_CERT=$REPLY
   ask 'TLS private key absolute path' "$TLS_KEY"; TLS_KEY=$REPLY
  else
   ask 'Self-signed certificate DNS name or IP' "$TLS_NAME"; TLS_NAME=$REPLY
  fi
 fi
 ask 'Manage host firewall (yes/no)' "$FIREWALL"; FIREWALL=$REPLY
 ask 'ACE-Step port on localhost' "$ACE_PORT"; ACE_PORT=$REPLY
 ask 'Remote ACE-Step HTTPS URL (blank = local ACE-Step)' "$ACE_URL"; ACE_URL=$REPLY
 check_args=(--dry-run --version "$VERSION" --port "$PORT" --bind "$BIND" --firewall "$FIREWALL" --ace-port "$ACE_PORT")
 check_args+=(--https "$HTTPS" --tls-mode "$TLS_MODE" --tls-name "$TLS_NAME")
 [[ -z $TLS_CERT ]] || check_args+=(--tls-cert "$TLS_CERT")
 [[ -z $TLS_KEY ]] || check_args+=(--tls-key "$TLS_KEY")
 [[ -z $ACE_URL ]] || check_args+=(--ace-url "$ACE_URL")
 "$0" "${check_args[@]}" >/dev/null || exit 2
 if [[ -n $ACE_URL ]]; then ACE_REMOTE_HOST=${ACE_URL#https://}; ACE_REMOTE_HOST=${ACE_REMOTE_HOST%:*}; fi
fi
SERVICE=/etc/systemd/system/mta-audio-editor.service
ENVFILE=/etc/mta/mta.env
if (( UNINSTALL )); then
 echo 'Uninstalling MTA web service; preserving ACE-Step and model cache.'
 systemctl disable --now mta-ai-billing.timer 2>/dev/null || true
 rm -f /etc/systemd/system/mta-ai-billing.timer /etc/systemd/system/mta-ai-billing.service
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
MTA_ACE_STEP_URL=${ACE_URL:-http://127.0.0.1:$ACE_PORT}
MTA_ACE_STEP_TRUSTED_HOST=${ACE_REMOTE_HOST:-}
HF_HOME=/var/lib/mta/models/huggingface
EOT
 echo "Initial admin account: admin; initial password stored in $ENVFILE (root-only)."
else
 sed -i -E "/^MTA_ACE_STEP_URL=/d; /^MTA_ACE_STEP_TRUSTED_HOST=/d" "$ENVFILE"
 printf 'MTA_ACE_STEP_URL=%s\nMTA_ACE_STEP_TRUSTED_HOST=%s\n' "${ACE_URL:-http://127.0.0.1:$ACE_PORT}" "${ACE_REMOTE_HOST:-}" >> "$ENVFILE"
fi
chmod 600 "$ENVFILE"
if [[ -n $ACE_URL ]]; then
 echo 'Remote ACE-Step HTTPS configured. Set MTA_ACE_STEP_TOKEN securely in /etc/mta/mta.env before starting AI jobs.'
 echo 'Remote endpoint must provide a valid trusted TLS certificate and API key protection.'
fi
# Bind to loopback unless network access explicitly selected.
HOST=127.0.0.1; [[ $BIND == network ]] && HOST=0.0.0.0
if [[ $HTTPS == yes ]]; then
 command -v openssl >/dev/null || { echo 'OpenSSL is required for HTTPS' >&2; exit 3; }
 if [[ $TLS_MODE == self-signed ]]; then
  mkdir -p /etc/mta/tls
  chmod 700 /etc/mta/tls
  TLS_CERT=/etc/mta/tls/server.crt; TLS_KEY=/etc/mta/tls/server.key
  if [[ ! -f $TLS_CERT || ! -f $TLS_KEY ]]; then
   temp_tls=$(mktemp -d /etc/mta/tls/.generate.XXXXXXXX)
   trap 'rm -rf -- "$TEMP" "$temp_tls"' EXIT
   san_type=DNS; [[ $TLS_NAME =~ ^[0-9.]+$ || $TLS_NAME == *:* ]] && san_type=IP
   openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
    -subj "/CN=$TLS_NAME" -addext "subjectAltName=$san_type:$TLS_NAME" \
    -keyout "$temp_tls/key" -out "$temp_tls/cert" >/dev/null 2>&1
   install -m 600 "$temp_tls/key" "$TLS_KEY"
   install -m 644 "$temp_tls/cert" "$TLS_CERT"
   rm -rf -- "$temp_tls"
  fi
 fi
 [[ -f $TLS_CERT && -f $TLS_KEY && ! -L $TLS_CERT && ! -L $TLS_KEY ]] || { echo 'TLS files missing or symlinked' >&2; exit 3; }
 openssl x509 -in "$TLS_CERT" -noout -checkend 0 >/dev/null || { echo 'TLS certificate expired or invalid' >&2; exit 3; }
 openssl pkey -in "$TLS_KEY" -noout >/dev/null 2>&1 || { echo 'Invalid TLS private key' >&2; exit 3; }
 cert_pub=$(openssl x509 -in "$TLS_CERT" -pubkey -noout | openssl pkey -pubin -outform DER | openssl dgst -sha256)
 key_pub=$(openssl pkey -in "$TLS_KEY" -pubout -outform DER | openssl dgst -sha256)
 [[ $cert_pub == "$key_pub" ]] || { echo 'TLS certificate/key mismatch' >&2; exit 3; }
 chmod 600 "$TLS_KEY"
 # Paths are validated; only add TLS variables when requested.
 sed -i -E '/^MTA_TLS_CERTFILE=/d; /^MTA_TLS_KEYFILE=/d' "$ENVFILE"
 printf 'MTA_TLS_CERTFILE=%s\nMTA_TLS_KEYFILE=%s\n' "$TLS_CERT" "$TLS_KEY" >> "$ENVFILE"
else
 sed -i -E '/^MTA_TLS_CERTFILE=/d; /^MTA_TLS_KEYFILE=/d' "$ENVFILE"
fi
cat >/etc/mta/mta-wizard.conf.tmp <<EOT
VERSION=$VERSION
PORT=$PORT
BIND=$BIND
FIREWALL=$FIREWALL
ACE_PORT=$ACE_PORT
ACE_URL=$ACE_URL
HTTPS=$HTTPS
TLS_MODE=$TLS_MODE
TLS_CERT=$TLS_CERT
TLS_KEY=$TLS_KEY
TLS_NAME=$TLS_NAME
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
cat > /etc/systemd/system/mta-ai-billing.service <<EOT
[Unit]
Description=MTA AI billing UTC period closer
After=mta-audio-editor.service
[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENVFILE
ExecStart=$VENV/bin/python -m app.ai_billing_scheduler
NoNewPrivileges=true
EOT
cat > /etc/systemd/system/mta-ai-billing.timer <<'EOT'
[Unit]
Description=Run MTA AI billing closure daily (UTC)
[Timer]
OnCalendar=*-*-* 02:15:00 UTC
Persistent=true
Unit=mta-ai-billing.service
[Install]
WantedBy=timers.target
EOT
systemctl daemon-reload
systemctl enable --now mta-ai-billing.timer
systemctl enable --now mta-audio-editor.service
systemctl restart mta-audio-editor.service
if [[ $BIND == network && $FIREWALL == yes ]]; then
 if command -v firewall-cmd >/dev/null && systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port="${PORT}/tcp"; firewall-cmd --reload
 elif command -v ufw >/dev/null && ufw status | grep -q '^Status: active'; then
  ufw allow "${PORT}/tcp"
 else echo "Firewall not managed or inactive. Allow TCP/$PORT in external hypervisor/cloud firewall if required."; fi
fi
WEB_SCHEME=http; [[ $HTTPS == yes ]] && WEB_SCHEME=https
ok=0
for i in $(seq 1 25); do
 if curl --insecure --fail --silent --max-time 3 "$WEB_SCHEME://127.0.0.1:$PORT/api/health" >/dev/null; then ok=1; break; fi
 sleep 1
done
if (( ! ok )); then
 echo 'MTA web health check failed. Inspect: journalctl -u mta-audio-editor -n 100' >&2
 systemctl status --no-pager mta-audio-editor.service || :
 exit 4
fi
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "MTA web health OK. Local URL: $WEB_SCHEME://127.0.0.1:$PORT/"
[[ $BIND == network && -n $IP ]] && echo "Network URL: $WEB_SCHEME://$IP:$PORT/ (requires reachable network/firewall)"
echo "Administrator initial credential is stored in $ENVFILE; protect it and change after login."
