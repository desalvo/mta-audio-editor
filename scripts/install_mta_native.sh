#!/usr/bin/env bash
# Explicit opt-in: install SERVER from a signed APT/DNF repository.
set -Eeuo pipefail
usage() { echo 'Usage: sudo install_mta_native.sh [early|stable] [--dry-run] [--unattended] [--no-wizard] [--configure-only]' >&2; }
channel=early; dry=0; unattended=0; no_wizard=0; configure_only=0
for arg in "$@"; do
 case "$arg" in early|stable) channel="$arg";; --dry-run) dry=1;; --unattended|--yes) unattended=1;; --no-wizard) no_wizard=1;; --configure-only) configure_only=1;; *) usage; exit 2;; esac
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
wizard="$(dirname "${BASH_SOURCE[0]}")/install_mta_native_wizard.sh"
if (( configure_only )); then
  [[ -f $wizard ]] || { echo 'Native configuration wizard not found' >&2; exit 3; }
  exec bash "$wizard" "$([[ $unattended == 1 ]] && echo --unattended || echo --interactive)"
fi
"$(dirname "${BASH_SOURCE[0]}")/repositories/install_repository.sh" "$channel" "$([[ $unattended == 1 ]] && echo --unattended || echo --interactive)"
if (( ! no_wizard )); then
  [[ -f $wizard ]] || { echo 'Native configuration wizard not found' >&2; exit 3; }
  exec bash "$wizard" "$([[ $unattended == 1 ]] && echo --unattended || echo --interactive)"
fi
