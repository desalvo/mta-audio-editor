#!/usr/bin/env bash
# Non-destructive EL10 native server installation readiness check.
set -Eeuo pipefail
. /etc/os-release
case "${ID:-}" in rhel|rocky|almalinux|centos|ol) ;; *) echo "Not an explicitly supported EL-family distribution: ${ID:-unknown}" >&2; exit 2;; esac
[[ "${VERSION_ID%%.*}" == 10 ]] || { echo "Expected EL10, got ${VERSION_ID:-unknown}" >&2; exit 2; }
[[ "$(uname -m)" == x86_64 ]] || { echo 'This release repository currently ships x86_64 RPM only' >&2; exit 2; }
command -v dnf >/dev/null || exit 2
printf 'EL10 preflight: distro=%s version=%s architecture=x86_64\n' "$ID" "$VERSION_ID"
for capability in 'python3.12' 'python3.12-pip' '/usr/bin/ffmpeg'; do
  if dnf -q repoquery --whatprovides "$capability" | grep -q .; then
    printf 'Available: %s\n' "$capability"
  else
    printf 'MISSING: %s (enable trusted OS/EPEL repositories before installing)\n' "$capability" >&2
    exit 3
  fi
done
printf 'EL10 preflight: PASS. Run scripts/install_mta.sh --native-server early --dry-run next.\n'
