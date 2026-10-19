#!/usr/bin/env bash
# Post-install native RPM/DEB configurator. No application sources are installed.
set -Eeuo pipefail
mode=${1:---interactive}
[[ $mode == --interactive || $mode == --unattended ]] || { echo 'Use --interactive or --unattended' >&2; exit 2; }
(( EUID == 0 )) || { echo 'Root required' >&2; exit 2; }
[[ -f /etc/mta/mta.env ]] || { echo 'Native server not installed: /etc/mta/mta.env missing' >&2; exit 3; }
command -v systemctl >/dev/null || { echo 'systemd required' >&2; exit 3; }
# Never source an environment file as shell code; update only recognized assignments.
config=/etc/mta/mta.env
# Staged, root-only checkpoint; never mutate the live environment until the final
# service health check succeeds. It survives errors, SIGINT and process termination.
umask 077
checkpoint=/etc/mta/.mta-wizard.pending
if [[ -e $checkpoint && ( ! -f $checkpoint || -L $checkpoint ) ]]; then
  echo 'Unsafe existing wizard checkpoint; refusing to read it.' >&2; exit 4
fi
[[ ! -f $checkpoint ]] || chmod 600 "$checkpoint"
get_setting() { sed -n "s/^${1}=//p" "${work:-$config}" | tail -1; }
save_checkpoint() {
  local temp
  temp=$(mktemp /etc/mta/.mta-wizard.pending.XXXXXXXX)
  chmod 600 "$temp"
  cp "$work" "$temp"
  mv -f "$temp" "$checkpoint"
}
checkpoint_answer() { set_setting "MTA_WIZARD_${1}" "$2"; }

ask() {
  local prompt=$1 def=$2 ans
  if [[ $mode == --unattended ]]; then REPLY=$def; return; fi
  [[ -t 0 ]] || { echo 'Interactive wizard requires a terminal; pass --unattended' >&2; exit 2; }
  read -r -p "$prompt [$def]: " ans
  REPLY=${ans:-$def}
}
set_setting() {
  local key=$1 val=$2 escaped
  [[ $key =~ ^MTA_[A-Z0-9_]+$ ]] || exit 2
  # Strict whitelist; no newline, quotes, backslash, or shell substitutions.
  [[ $val != *$'\n'* && $val != *$'\r'* && $val != *'"'* && $val != *'\\'* && $val != *'`'* && $val != *'$('* ]] || { echo "Unsafe value for $key" >&2; exit 2; }
  if grep -q "^${key}=" "$work"; then
    escaped=${val//&/\\&}; escaped=${escaped//|/\\|}
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$work"
  else
    printf '%s=%s\n' "$key" "$val" >> "$work"
  fi
  save_checkpoint
}
installed() {
  if command -v rpm >/dev/null && rpm -q mta-audio-editor-server >/dev/null 2>&1; then return 0; fi
  if command -v dpkg-query >/dev/null && [[ $(dpkg-query -W -f='${Status}' mta-audio-editor-server 2>/dev/null || :) == 'install ok installed' ]]; then return 0; fi
  return 1
}
installed || { echo 'Install the signed mta-audio-editor-server package first' >&2; exit 3; }
work=$(mktemp /etc/mta/.mta.env.XXXXXXXX)
chmod 600 "$work"
trap 'rm -f "$work"' EXIT
if [[ -f $checkpoint ]]; then
  echo 'Resuming previously saved wizard answers (root-only checkpoint).'
  cp "$checkpoint" "$work"
else
  cp "$config" "$work"
fi
chmod 600 "$work"
port=$(get_setting MTA_PORT); port=${port:-8000}
host=$(get_setting MTA_HOST); host=${host:-127.0.0.1}
admin=$(get_setting MTA_ADMIN_USERNAME); admin=${admin:-admin}
data=$(get_setting MTA_DATA_DIR); data=${data:-/var/lib/mta/projects}
ask 'Server TCP port' "$port"; port=$REPLY
[[ $port =~ ^[0-9]{1,5}$ ]] && (( 10#$port >= 1 && 10#$port <= 65535 )) || { echo 'Invalid TCP port' >&2; exit 2; }
set_setting MTA_PORT "$port"
ask 'Listen address (127.0.0.1/0.0.0.0)' "$host"; host=$REPLY
[[ $host == 127.0.0.1 || $host == 0.0.0.0 ]] || { echo 'Unsupported listen address' >&2; exit 2; }
set_setting MTA_HOST "$host"
ask 'Administrator username' "$admin"; admin=$REPLY
[[ $admin =~ ^[a-zA-Z0-9_.-]{1,64}$ ]] || { echo 'Invalid administrator username' >&2; exit 2; }
set_setting MTA_ADMIN_USERNAME "$admin"
ask 'Projects directory (absolute path)' "$data"; data=$REPLY
[[ $data == /* && $data != / && $data != *'..'* && $data != *[[:space:]]* ]] || { echo 'Unsafe data directory' >&2; exit 2; }
set_setting MTA_DATA_DIR "$data"
# Existing password is preserved. User may explicitly rotate it, never printed on screen.
if [[ $mode == --interactive ]]; then
  read -r -p 'Change the administrator password? [y/N]: ' yn
  if [[ $yn == y || $yn == Y ]]; then
    read -r -s -p 'New administrator password: ' pass; echo
    [[ ${#pass} -ge 12 ]] || { echo 'Password must contain at least 12 characters' >&2; exit 2; }
    set_setting MTA_ADMIN_PASSWORD "$pass"
    unset pass
  fi
fi
# AI execution preference is a native runtime environment setting.
ai=$(get_setting MTA_AI_DEVICE); ai=${ai:-auto}
ask 'AI execution device (auto/cpu/cuda/rocm)' "$ai"; ai=$REPLY
[[ $ai == auto || $ai == cpu || $ai == cuda || $ai == rocm ]] || { echo 'Invalid AI device' >&2; exit 2; }
set_setting MTA_AI_DEVICE "$ai"
public=$(get_setting MTA_PUBLIC_URL)
if [[ $mode == --interactive ]]; then
  ask 'Public HTTPS URL (optional)' "$public"; public=$REPLY
fi
[[ -z $public || $public =~ ^https://[a-zA-Z0-9][a-zA-Z0-9.:-]{1,250}(/)?$ ]] || { echo 'Public URL must be HTTPS' >&2; exit 2; }
[[ -z $public ]] || set_setting MTA_PUBLIC_URL "$public"
# HTTPS: existing certificate or a generated, locally managed self-signed certificate.
cert=$(get_setting MTA_TLS_CERTFILE); key=$(get_setting MTA_TLS_KEYFILE)
https_default=$(get_setting MTA_WIZARD_HTTPS); https_default=${https_default:-no}; [[ -n $cert && -n $key ]] && https_default=yes
ask 'Enable HTTPS (yes/no)' "$https_default"; https=$REPLY
[[ $https == yes || $https == no ]] || { echo 'Invalid HTTPS option' >&2; exit 2; }
checkpoint_answer HTTPS "$https"
if [[ $https == yes ]]; then
  tls_mode=existing; [[ -z $cert || -z $key ]] && tls_mode=self-signed
  echo 'Self-signed certificates are intended for testing or controlled deployments; use a valid CA-signed certificate and private key for public production.'
  tls_mode=$(get_setting MTA_WIZARD_TLS_MODE); tls_mode=${tls_mode:-$tls_mode}
  ask 'TLS certificate mode (existing/self-signed)' "$tls_mode"; tls_mode=$REPLY
  [[ $tls_mode == existing || $tls_mode == self-signed ]] || exit 2
  checkpoint_answer TLS_MODE "$tls_mode"
  if [[ $tls_mode == self-signed ]]; then
    tls_name=$(get_setting MTA_WIZARD_TLS_NAME); tls_name=${tls_name:-$(hostname -f 2>/dev/null || hostname)}
    ask 'TLS certificate DNS name or IP' "$tls_name"; tls_name=$REPLY
    [[ $tls_name =~ ^[a-zA-Z0-9][a-zA-Z0-9.:-]{0,252}$ && $tls_name != *..* ]] || { echo 'Invalid TLS name' >&2; exit 2; }
    checkpoint_answer TLS_NAME "$tls_name"
    # Do not overwrite existing certificate material; deterministic owned location.
    cert=/etc/mta/tls/server.crt; key=/etc/mta/tls/server.key
  else
    ask 'Existing TLS certificate absolute path' "$cert"; cert=$REPLY
    ask 'Existing TLS private key absolute path' "$key"; key=$REPLY
    [[ $cert == /* && $key == /* && -f $cert && -f $key && -r $cert && -r $key ]] || { echo 'TLS files must be existing readable absolute paths' >&2; exit 2; }
    # Verify certificate/key consistency and validity before changing configuration.
    ensure_tls_validation=1
  fi
  for file in "$cert" "$key"; do
    [[ $file == /* && $file != *[[:space:]]* && $file != *'..'* && $file != *'\'* ]] || { echo 'Invalid TLS file path' >&2; exit 2; }
  done
  if [[ ${ensure_tls_validation:-0} == 1 ]]; then
    # openssl package will be provisioned from configured repos below if missing.
    command -v openssl >/dev/null || { echo 'OpenSSL required to validate provided certificate/key' >&2; exit 4; }
    openssl x509 -in "$cert" -noout -checkend 86400 || { echo 'TLS certificate is expired or expires within 24 hours' >&2; exit 4; }
    cert_pub=$(openssl x509 -in "$cert" -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum | cut -d' ' -f1)
    key_pub=$(openssl pkey -in "$key" -pubout -outform DER | sha256sum | cut -d' ' -f1)
    [[ -n $cert_pub && $cert_pub == "$key_pub" ]] || { echo 'TLS certificate and private key do not match' >&2; exit 4; }
  fi
  set_setting MTA_TLS_CERTFILE "$cert"; set_setting MTA_TLS_KEYFILE "$key"
else
  # Clear both together; retaining just one prevents uvicorn startup.
  set_setting MTA_TLS_CERTFILE ''; set_setting MTA_TLS_KEYFILE ''
fi
# Local ACE-Step is an optional separate component, installed from a pinned upstream
# version by the helper INCLUDED in the signed server package. It requires AMD ROCm.
# The native MTA server itself remains owned and upgraded by RPM/DEB.
ace_installer=/usr/lib/mta-audio-editor-server/native-installers/install_ace_step.sh
# New native installations default to local ACE-Step. An explicit selection from a
# root-only wizard checkpoint takes precedence, even after an interrupted setup.
# Existing installations with a recorded wizard choice retain their setting.
ace_mode_default=$(get_setting MTA_WIZARD_ACE_MODE)
ace_mode_default=${ace_mode_default:-local}
ask 'ACE-Step backend (local/remote/disabled)' "$ace_mode_default"; ace_mode=$REPLY
[[ $ace_mode == local || $ace_mode == remote || $ace_mode == disabled ]] || { echo 'Invalid ACE-Step mode' >&2; exit 2; }
checkpoint_answer ACE_MODE "$ace_mode"
if [[ $ace_mode == local ]]; then
  if [[ ! -f $ace_installer || ! -x $ace_installer ]]; then
    echo 'Installed server package is missing its ACE-Step installer.' >&2
    echo 'Upgrade mta-audio-editor-server using the configured signed APT/DNF repository, then rerun --configure-only.' >&2
    echo 'RPM: sudo dnf --refresh upgrade mta-audio-editor-server' >&2
    echo 'DEB: sudo apt-get update && sudo apt-get install --only-upgrade mta-audio-editor-server' >&2
    echo 'Do not run a downloaded, unverified replacement installer.' >&2
    exit 4
  fi
  ace_device=$(get_setting MTA_WIZARD_ACE_DEVICE); ace_device=${ace_device:-auto}
  ask 'ACE-Step execution device (auto/rocm/cpu)' "$ace_device"; ace_device=$REPLY
  [[ $ace_device == auto || $ace_device == rocm || $ace_device == cpu ]] || { echo 'Invalid ACE-Step device' >&2; exit 2; }
  checkpoint_answer ACE_DEVICE "$ace_device"
  if [[ $ace_device == auto ]]; then
    render_nodes=(/dev/dri/renderD*)
    if [[ -c /dev/kfd && -c ${render_nodes[0]} ]]; then ace_device=rocm; else ace_device=cpu; fi
  fi
  if [[ $ace_device == rocm ]]; then
    rocm_installer=/usr/lib/mta-audio-editor-server/native-installers/install_rocm_userspace.sh
    [[ -r $rocm_installer ]] || { echo 'ROCm bootstrap missing from signed server package.' >&2; exit 4; }
    if ! command -v rocminfo >/dev/null 2>&1 || ! rocminfo >/dev/null 2>&1; then
      if ! bash "$rocm_installer" yes; then
        echo 'ROCm installation unavailable; see the diagnostic instructions above.' >&2
        if [[ $mode == --interactive ]]; then
          ask 'Continue installing ACE-Step on CPU instead (yes/no)' yes; [[ $REPLY == yes ]] || exit 4
          ace_device=cpu
        else
          echo 'Falling back automatically to CPU-only ACE-Step.'
          ace_device=cpu
        fi
      fi
    fi
  fi
  if [[ $ace_device == cpu ]]; then
    echo 'WARNING: CPU-only ACE-Step inference is supported but significantly slower than GPU inference.'
  fi
  ace_port=$(get_setting MTA_WIZARD_ACE_PORT); ace_port=${ace_port:-8001}
  ask 'ACE-Step service TCP port' "$ace_port"; ace_port=$REPLY
  [[ $ace_port =~ ^[0-9]{4,5}$ ]] && (( 10#$ace_port >= 1024 && 10#$ace_port <= 65535 )) || { echo 'Invalid ACE-Step port' >&2; exit 2; }
  checkpoint_answer ACE_PORT "$ace_port"
  # Explicitly keep the inference service loopback-only; never expose its API.
  echo 'Installing locally managed ACE-Step on loopback; models remain persistent.'
  bash "$ace_installer" --yes --device "$ace_device" --port "$ace_port" --bind local --firewall no
  systemctl is-active --quiet mta-ace-step.service || { echo 'ACE-Step service failed to start' >&2; exit 4; }
  set_setting MTA_ACE_STEP_URL "http://127.0.0.1:${ace_port}"
  set_setting MTA_ACE_STEP_TRUSTED_HOST '127.0.0.1'
  # Local trusted transport does not use the remote secret.
  set_setting MTA_ACE_STEP_TOKEN ''
  # The native server needs an explicit trusted worker opt-in in addition to the ACE URL.
  worker=/usr/lib/mta-audio-editor-server/app/ace_step_http_worker.py
  [[ -f $worker && ! -L $worker ]] || { echo 'Trusted ACE-Step worker missing from signed server RPM/DEB.' >&2; exit 4; }
  chmod 755 "$worker"
  set_setting MTA_AI_WORKER_EXECUTABLE "$worker"
  set_setting MTA_AI_WORKER_ENABLED true
fi
if [[ $ace_mode == disabled ]]; then
  # No ACE-Step installation or changes to an existing managed service.
  set_setting MTA_ACE_STEP_URL 'http://127.0.0.1:8001'
  set_setting MTA_ACE_STEP_TRUSTED_HOST '127.0.0.1'
  set_setting MTA_AI_WORKER_ENABLED false
  set_setting MTA_AI_WORKER_EXECUTABLE ''
  echo 'ACE-Step disabled for this setup; existing local service is untouched.'
fi
if [[ $ace_mode == remote ]]; then
# Remote ACE-Step backend. Do not store an unverified or HTTP remote endpoint.
remote=$(get_setting MTA_ACE_STEP_URL)
remote=${remote:-http://127.0.0.1:8001}
ask 'ACE-Step backend URL (local HTTP or remote HTTPS)' "$remote"; remote=$REPLY
if [[ $remote =~ ^https://([a-zA-Z0-9][a-zA-Z0-9.-]{0,251})(:([0-9]{1,5}))?/?$ ]]; then
  remote_host=${BASH_REMATCH[1]}; remote_port=${BASH_REMATCH[3]:-443}
  (( 10#$remote_port >= 1 && 10#$remote_port <= 65535 )) || exit 2
elif [[ $remote =~ ^http://(127\.0\.0\.1|localhost)(:([0-9]{1,5}))?/?$ ]]; then
  remote_host=${BASH_REMATCH[1]}; remote_port=${BASH_REMATCH[3]:-80}
  (( 10#$remote_port >= 1 && 10#$remote_port <= 65535 )) || exit 2
else
  echo 'Remote ACE-Step requires HTTPS (only localhost may use HTTP).' >&2; exit 2
fi
set_setting MTA_ACE_STEP_URL "${remote%/}"
set_setting MTA_ACE_STEP_TRUSTED_HOST "$remote_host"
worker=/usr/lib/mta-audio-editor-server/app/ace_step_http_worker.py
[[ -f $worker && ! -L $worker ]] || { echo 'Trusted ACE-Step worker missing from signed server RPM/DEB.' >&2; exit 4; }
chmod 755 "$worker"
set_setting MTA_AI_WORKER_EXECUTABLE "$worker"
set_setting MTA_AI_WORKER_ENABLED true
if [[ $mode == --interactive ]]; then
  read -r -p 'Set/change ACE-Step access token? [y/N]: ' yn
  if [[ $yn == y || $yn == Y ]]; then
    read -r -s -p 'ACE-Step token (not echoed): ' token; echo
    [[ -n $token && $token != *[[:space:]]* ]] || { echo 'Invalid token' >&2; exit 2; }
    set_setting MTA_ACE_STEP_TOKEN "$token"; unset token
  fi
fi
fi # remote ACE-Step configuration
# Allowlisted optional packages are resolved exclusively through already trusted repositories.
# These may be needed by chosen server features or future native server addons.
ensure_system_package() {
  local pkg=$1
  case "$pkg" in openssl|curl|ffmpeg|firewalld) ;; *) echo "Disallowed package: $pkg" >&2; return 2;; esac
  if command -v rpm >/dev/null && rpm -q "$pkg" >/dev/null 2>&1; then return 0; fi
  if command -v dpkg-query >/dev/null && [[ $(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null || :) == 'install ok installed' ]]; then return 0; fi
  if [[ $mode == --interactive ]]; then
    local yesno
    read -r -p "Install missing system package $pkg from configured repositories? [y/N]: " yesno
    [[ $yesno == y || $yesno == Y ]] || { echo "Declined dependency $pkg" >&2; return 4; }
  fi
  if command -v dnf >/dev/null; then
    dnf install -y "$pkg"
  elif command -v apt-get >/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y "$pkg"
  else echo 'No supported package manager' >&2; return 3; fi
}
if [[ $mode == --interactive ]]; then
  read -r -p 'Install optional system tools (curl and OpenSSL), if missing? [y/N]: ' extra
  if [[ $extra == y || $extra == Y ]]; then
    ensure_system_package curl
    ensure_system_package openssl
  fi
fi
# Firewall changes are explicitly opted in. Unattended defaults to no change.
firewall_action=no
if [[ $host == 0.0.0.0 ]]; then
  ask 'Open server TCP port in host firewall (yes/no)' "$(get_setting MTA_WIZARD_FIREWALL | sed 's/^$/no/')"; firewall_action=$REPLY
  [[ $firewall_action == yes || $firewall_action == no ]] || exit 2
  checkpoint_answer FIREWALL "$firewall_action"
fi
if [[ $firewall_action == yes ]]; then
  if command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld.service; then
    firewall_backend=firewalld
  elif command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -qi '^Status: active'; then
    firewall_backend=ufw
  else
    echo 'No supported active host firewall found; refusing to enable or replace firewall policy.' >&2
    exit 4
  fi
fi
billing_enabled=$(get_setting MTA_WIZARD_BILLING); billing_enabled=${billing_enabled:-yes}
if [[ $mode == --interactive ]]; then
  ask 'Enable scheduled AI billing closure (yes/no)' "$billing_enabled"; billing_enabled=$REPLY
fi
[[ $billing_enabled == yes || $billing_enabled == no ]] || { echo 'Invalid billing option' >&2; exit 2; }
checkpoint_answer BILLING "$billing_enabled"
if [[ $https == yes && $tls_mode == self-signed ]]; then
  ensure_system_package openssl
  install -d -m 700 /etc/mta/tls
  if [[ ! -f $cert || ! -f $key ]]; then
    if [[ $tls_name =~ ^[0-9.]+$ || $tls_name == *:* ]]; then san="IP:$tls_name"; else san="DNS:$tls_name"; fi
    tls_tmp=$(mktemp -d /etc/mta/tls/.new.XXXXXXXX)
    chmod 700 "$tls_tmp"
    if ! openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
      -subj "/CN=$tls_name" -addext "subjectAltName=$san" \
      -keyout "$tls_tmp/server.key" -out "$tls_tmp/server.crt" >/dev/null 2>&1; then
      rm -rf "$tls_tmp"; echo 'TLS certificate generation failed' >&2; exit 4
    fi
    chmod 600 "$tls_tmp/server.key"; chmod 644 "$tls_tmp/server.crt"
    # Replace the pair only when one/both are absent; existing pair is preserved.
    install -m 600 "$tls_tmp/server.key" "$key"
    install -m 644 "$tls_tmp/server.crt" "$cert"
    rm -rf "$tls_tmp"
  fi
fi
# Every signed-package wizard path (including --no-wizard) provisions all AI engines.
# Keep heavy inference dependencies out of package-manager maintainer scripts.
ai_installer=/usr/lib/mta-audio-editor-server/native-installers/install_ai_engines.py
[[ -f $ai_installer && ! -L $ai_installer ]] || { echo 'All-engine installer missing: upgrade the signed MTA package.' >&2; exit 4; }
/opt/mta/server-venv/bin/python "$ai_installer" --python /opt/mta/server-venv/bin/python --env-file "$work" --device "${ace_device:-$ai}"
# Optional source builds are explicit; core/server updates never install plugins silently.
if [[ -n ${MTA_INSTALL_OPTIONAL_VST3:-} ]]; then
 if command -v apt-get >/dev/null; then
  apt-get install -y git build-essential cmake pkg-config libx11-dev libxext-dev libgl1-mesa-dev libxrandr-dev libxinerama-dev libxcursor-dev libfreetype-dev libasound2-dev libjack-jackd2-dev lv2-dev
 elif command -v dnf >/dev/null; then
  dnf install -y git gcc gcc-c++ make cmake pkgconf-pkg-config libX11-devel libXext-devel mesa-libGL-devel libXrandr-devel libXinerama-devel libXcursor-devel freetype-devel alsa-lib-devel jack-audio-connection-kit-devel lv2-devel
 fi
 MTA_DATA_DIR="$data" PYTHONPATH=/usr/lib/mta-audio-editor-server /opt/mta/server-venv/bin/python -m app.optional_plugins --plugins "$MTA_INSTALL_OPTIONAL_VST3" --accept-licenses
fi
# Retain complete AI bindings if a later step fails and the wizard is resumed.
save_checkpoint
install -d -m 755 "$data"
# Back up configuration and roll back if the service cannot start with new values.
backup=$(mktemp /etc/mta/.mta.env.backup.XXXXXXXX)
chmod 600 "$backup"; cp -p "$config" "$backup"
# Checkpoint metadata is wizard-only and must not enter the service environment.
sed -i '/^MTA_WIZARD_[A-Z_]*=/d' "$work"
chown --reference="$config" "$work"
mv -f "$work" "$config"
trap - EXIT
chmod 600 "$config"
if ! systemctl restart mta-server.service || ! systemctl is-active --quiet mta-server.service; then
  cp -p "$backup" "$config"
  systemctl restart mta-server.service || :
  rm -f "$backup"
  echo 'Server failed to restart; restored previous configuration. Inspect journalctl -u mta-server.service' >&2
  exit 4
fi
rm -f "$backup"
# Only collect after successful restart. Pending checkpoint deliberately protects
# all runtimes until final setup completion.
if [[ $billing_enabled == yes ]]; then
  systemctl enable --now mta-billing-scheduler.timer
else
  systemctl disable --now mta-billing-scheduler.timer
fi
if [[ $firewall_action == yes ]]; then
  if [[ $firewall_backend == firewalld ]]; then
    firewall-cmd --permanent --add-port="${port}/tcp" && firewall-cmd --reload
  else
    ufw allow "${port}/tcp"
  fi
fi
rm -f "$checkpoint"
/opt/mta/server-venv/bin/python "$ai_installer" --cleanup --env-file "$config" || echo 'AI runtime cleanup deferred; server remains configured.' >&2
echo "Native server configured on ${host}:${port} (HTTPS: ${https}); future upgrades are managed by APT/DNF."
