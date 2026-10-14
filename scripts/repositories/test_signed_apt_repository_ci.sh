#!/usr/bin/env bash
# CI-only end-to-end signature and package-index test; creates an ephemeral signing key.
set -Eeuo pipefail
[[ ${MTA_CI_DISPOSABLE_CONTAINER:-0} == 1 && $(id -u) == 0 ]] || { echo 'Disposable root CI environment required' >&2; exit 2; }
for tool in gpg dpkg-deb dpkg-scanpackages apt-ftparchive createrepo_c rpm; do command -v "$tool" >/dev/null || exit 2; done
root=$(mktemp -d)
trap 'rm -rf "$root"; rm -f /etc/apt/sources.list.d/mta-ci-signed-test.list /usr/share/keyrings/mta-ci-signed-test.gpg' EXIT
mkdir -p "$root/incoming" "$root/pkg/DEBIAN" "$root/repo" "$root/gnupg"
chmod 700 "$root/gnupg"
# APT downloads as the unprivileged _apt user; signed local index must be traversable.
chmod 755 "$root" "$root/repo"
printf 'Package: mta-audio-editor-server\nVersion: 0.3.0~early.208\nArchitecture: all\nMaintainer: CI <ci@example.org>\nDescription: CI fixture only\n' > "$root/pkg/DEBIAN/control"
dpkg-deb --build "$root/pkg" "$root/incoming/mta-server-test.deb"
export GNUPGHOME="$root/gnupg"
gpg --batch --passphrase '' --quick-generate-key 'MTA CI Ephemeral <ci@example.org>' ed25519 sign 0
fingerprint=$(gpg --batch --with-colons --list-keys | awk -F: '$1=="fpr" {print $10;exit}')
[[ $fingerprint =~ ^[A-Fa-f0-9]{40}$ ]] || exit 3
CI=true MTA_CI_DISPOSABLE_CONTAINER=1 MTA_CI_APT_ONLY=1 MTA_REPO_INPUT="$root/incoming" MTA_REPO_OUTPUT="$root/repo" MTA_REPO_CHANNEL=early MTA_GPG_KEY_ID="$fingerprint" bash scripts/repositories/build_indexes.sh
gpg --batch --dearmor -o /usr/share/keyrings/mta-ci-signed-test.gpg "$root/repo/mta-archive-key.asc"
gpg --batch --no-default-keyring --keyring /usr/share/keyrings/mta-ci-signed-test.gpg --verify "$root/repo/apt/early/Release.gpg" "$root/repo/apt/early/Release"
# Signature verification must reject corrupted metadata; never trust the presence
# of a detached signature alone.
cp "$root/repo/apt/early/Release" "$root/tampered-release"
printf '\nTampered: yes\n' >> "$root/tampered-release"
if gpg --batch --no-default-keyring --keyring /usr/share/keyrings/mta-ci-signed-test.gpg --verify "$root/repo/apt/early/Release.gpg" "$root/tampered-release" 2>/dev/null; then
  echo 'ERROR: signed repository accepted tampered Release metadata' >&2
  exit 5
fi
printf 'deb [signed-by=/usr/share/keyrings/mta-ci-signed-test.gpg] file://%s/apt/early ./\n' "$root/repo" > /etc/apt/sources.list.d/mta-ci-signed-test.list
apt-get update -o Dir::Etc::sourcelist='sources.list.d/mta-ci-signed-test.list' -o Dir::Etc::sourceparts='-' -o APT::Get::List-Cleanup='0'
apt-cache -o Dir::Etc::sourcelist='sources.list.d/mta-ci-signed-test.list' -o Dir::Etc::sourceparts='-' policy mta-audio-editor-server | grep -F '0.3.0~early.208'
# Install the harmless empty fixture from the signed index (isolated container only).
apt-get -y -o Dir::Etc::sourcelist='sources.list.d/mta-ci-signed-test.list' -o Dir::Etc::sourceparts='-' install mta-audio-editor-server
dpkg-query -W -f='${Status}\n' mta-audio-editor-server | grep -qx 'install ok installed'
apt-get -y remove mta-audio-editor-server
echo 'Ephemeral signed APT repository installation: OK (fixture only, no production keys)'
