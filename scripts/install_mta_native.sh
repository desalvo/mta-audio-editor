#!/usr/bin/env bash
# Explicit opt-in: install SERVER from a signed APT/DNF repository.
set -Eeuo pipefail
usage() { echo 'Usage: sudo MTA_PACKAGES_URL=https://... install_mta_native.sh [early|stable] [--dry-run]' >&2; }
channel=stable; dry=0
for arg in "$@"; do
 case "$arg" in early|stable) channel="$arg";; --dry-run) dry=1;; *) usage; exit 2;; esac
done
export MTA_PACKAGES_URL=${MTA_PACKAGES_URL:-https://desalvo.github.io/mta-audio-editor-packages}
export MTA_REPO_KEY_FINGERPRINT=${MTA_REPO_KEY_FINGERPRINT:-0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7}
[[ ${MTA_PACKAGES_URL:-} == https://* ]] || { echo 'Published HTTPS repository URL required.' >&2; exit 2; }
[[ ${MTA_REPO_KEY_FINGERPRINT:-} =~ ^[[:xdigit:]]{40}$ ]] || { echo 'Trusted GPG key fingerprint required.' >&2; exit 2; }
if [[ -e /opt/mta/application/.git || -f /opt/mta/application/.mta-wizard-managed ]]; then
 echo 'Existing legacy MTA installation: migration is not automatic. No changes made.' >&2; exit 3
fi
if (( dry )); then
 printf 'NATIVE_SERVER channel=%s url=%s action=configure-verified-repository-and-install package=mta-audio-editor-server\n' "$channel" "$MTA_PACKAGES_URL"
 exit 0
fi
(( EUID == 0 )) || { echo 'Root required' >&2; exit 2; }
exec "$(dirname "${BASH_SOURCE[0]}")/repositories/install_repository.sh" "$channel"
