#!/usr/bin/env bash
# Repo bootstrap for released SERVER packages; never installs desktop package as server.
set -Eeuo pipefail
MTA_PACKAGES_URL=${MTA_PACKAGES_URL:-https://desalvo.github.io/mta-audio-editor-packages}
MTA_REPO_KEY_FINGERPRINT=${MTA_REPO_KEY_FINGERPRINT:-0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7}
CHANNEL=${1:-stable}
MODE=${2:---interactive}
[[ $MODE == --interactive || $MODE == --unattended ]] || { echo "Invalid execution mode" >&2; exit 2; }
[[ $CHANNEL == stable || $CHANNEL == early ]] || { echo 'Channel must be stable or early' >&2; exit 2; }
[[ $MTA_PACKAGES_URL == https://* && $MTA_PACKAGES_URL != *' '* ]] || exit 2
[[ $MTA_REPO_KEY_FINGERPRINT =~ ^[[:xdigit:]]{40}$ ]] || exit 2
(( EUID == 0 )) || { echo 'Run as root' >&2; exit 2; }
. /etc/os-release
base=${MTA_PACKAGES_URL%/}
# Never enable unrelated repositories silently during interactive installs.
# In unattended mode opt in only to the documented, system-managed EPEL RPM.
confirm_external() {
  local question=$1 reply
  if [[ $MODE == --unattended ]]; then
    echo "Unattended mode: approving $question"
    return 0
  fi
  if [[ ! -t 0 ]]; then
    echo "External dependency requires approval, but stdin is non-interactive. Use --unattended to opt in." >&2
    return 1
  fi
  read -r -p "$question [y/N]: " reply
  [[ $reply == [yY] || $reply == [yY][eE][sS] ]]
}
# Use bounded DNF queries: repository metadata/network issues must never hang setup.
# A timeout is NOT evidence that a dependency is unavailable.
dnf_probe() {
  local what=$1; shift
  local rc=0
  timeout --signal=TERM --kill-after=3s 30s \
    dnf -q --setopt=timeout=8 --setopt=retries=0 "$@" >/dev/null 2>&1 || rc=$?
  if (( rc == 124 || rc == 137 )); then
    echo "DNF timed out while checking $what (30s). Check repository connectivity, DNS, subscription-manager and enabled repositories." >&2
    return 75
  fi
  return "$rc"
}
prepare_el_dependencies() {
  local major=$1 rc=0
  # Prefer local RPM database (no network access or metadata refresh).
  if rpm -q --whatprovides /usr/bin/ffmpeg >/dev/null 2>&1; then
    return 0
  fi
  dnf_probe ffmpeg provides /usr/bin/ffmpeg || rc=$?
  if (( rc == 0 )); then return 0; fi
  if (( rc == 75 )); then return 75; fi
  echo 'FFmpeg is not provided by currently enabled RPM repositories; EPEL may be necessary.' >&2
  rc=0
  dnf_probe epel-release list --available epel-release || rc=$?
  if (( rc == 75 )); then return 75; fi
  if (( rc != 0 )); then
    echo 'epel-release is unavailable in trusted enabled repositories. Configure EPEL manually according to your distribution policy.' >&2
    return 4
  fi
  confirm_external "Install EPEL repository configuration (epel-release) and its dependencies for EL$major?" || {
    echo 'Declined EPEL installation; leaving the host unchanged for this step.' >&2
    return 4
  }
  dnf install -y epel-release || return 4
  # Do not force a full refresh: the next bounded query can fetch required metadata.
  rc=0
  dnf_probe ffmpeg provides /usr/bin/ffmpeg || rc=$?
  if (( rc == 75 )); then return 75; fi
  if (( rc != 0 )); then
    echo 'FFmpeg still unavailable after EPEL; check CRB/CodeReady Builder or your subscription configuration.' >&2
    return 4
  fi
}

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
curl --fail --location --proto '=https' --tlsv1.2 --silent --show-error "$base/mta-archive-key.asc" -o "$tmp/key.asc"
actual=$(gpg --batch --show-keys --with-colons "$tmp/key.asc" | awk -F: '$1=="fpr" {print toupper($10); exit}')
[[ $actual == "${MTA_REPO_KEY_FINGERPRINT^^}" ]] || { echo 'Signing key fingerprint mismatch: refusing repository' >&2; exit 4; }
case " ${ID:-} ${ID_LIKE:-} " in
 *debian*|*ubuntu*)
   command -v apt-get >/dev/null || exit 2
   install -d -m 755 /etc/apt/keyrings
   gpg --batch --yes --dearmor -o /etc/apt/keyrings/mta-audio-editor.gpg "$tmp/key.asc"
   chmod 644 /etc/apt/keyrings/mta-audio-editor.gpg
   printf 'deb [signed-by=/etc/apt/keyrings/mta-audio-editor.gpg] %s/apt/%s ./\n' "$base" "$CHANNEL" > /etc/apt/sources.list.d/mta-audio-editor.list
   apt-get update
   apt-get install mta-audio-editor-server
   ;;
 *rhel*|*rocky*|*almalinux*|*centos*|*ol*|*fedora*)
   command -v dnf >/dev/null || exit 2
   install -d -m 755 /etc/pki/rpm-gpg
   install -m 644 "$tmp/key.asc" /etc/pki/rpm-gpg/RPM-GPG-KEY-MTA
   rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-MTA
   major=${VERSION_ID%%.*}
   case "$major" in
     9|10) target="el$major" ;;
     *) echo "Unsupported EL major version: $major (expected 9 or 10)" >&2; exit 2 ;;
   esac
   cat > /etc/yum.repos.d/mta-audio-editor.repo <<EOF
[mta-audio-editor]
name=MTA Audio Editor Server ($CHANNEL)
baseurl=$base/rpm/$CHANNEL/$target
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-MTA
EOF
   # First-use DNF5/DNF4 repository metadata signing keys have their own trust
   # cache. `rpm --import` alone does NOT initialize this repo_gpgcheck cache.
   # Import the already fingerprint-pinned key using DNF non-interactively,
   # before any short repository probe can hit the first-use GPG prompt.
   echo "Initializing signed MTA DNF repository metadata and GPG trust..."
   if ! timeout --signal=TERM --kill-after=5s 180s \
       dnf -y --refresh --setopt=timeout=20 --setopt=retries=2 \
       --disablerepo='*' --enablerepo=mta-audio-editor makecache; then
     echo 'Unable to initialize the signed MTA repository metadata. Check DNS, HTTPS access, and repository signing key; GPG checks were not bypassed.' >&2
     exit 75
   fi
   prepare_el_dependencies "$major"
   dnf install -y mta-audio-editor-server
   ;;
 *) echo 'Unsupported Linux distribution' >&2; exit 2;;
esac
