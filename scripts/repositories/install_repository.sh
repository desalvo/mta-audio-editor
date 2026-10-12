#!/usr/bin/env bash
# Repo bootstrap for released SERVER packages; never installs desktop package as server.
set -Eeuo pipefail
MTA_PACKAGES_URL=${MTA_PACKAGES_URL:-https://desalvo.github.io/mta-audio-editor-packages}
MTA_REPO_KEY_FINGERPRINT=${MTA_REPO_KEY_FINGERPRINT:-0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7}
CHANNEL=${1:-stable}
[[ $CHANNEL == stable || $CHANNEL == early ]] || { echo 'Channel must be stable or early' >&2; exit 2; }
[[ $MTA_PACKAGES_URL == https://* && $MTA_PACKAGES_URL != *' '* ]] || exit 2
[[ $MTA_REPO_KEY_FINGERPRINT =~ ^[[:xdigit:]]{40}$ ]] || exit 2
(( EUID == 0 )) || { echo 'Run as root' >&2; exit 2; }
. /etc/os-release
base=${MTA_PACKAGES_URL%/}
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
   cat > /etc/yum.repos.d/mta-audio-editor.repo <<EOF
[mta-audio-editor]
name=MTA Audio Editor Server ($CHANNEL)
baseurl=$base/rpm/$CHANNEL
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-MTA
EOF
   dnf install -y mta-audio-editor-server
   ;;
 *) echo 'Unsupported Linux distribution' >&2; exit 2;;
esac
