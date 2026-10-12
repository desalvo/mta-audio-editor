#!/usr/bin/env bash
# Run only in a protected GitHub Actions environment, after a successful native server matrix.
set -Eeuo pipefail
: "${MTA_REPO_INPUT:?}" "${MTA_REPO_OUTPUT:?}" "${MTA_REPO_CHANNEL:?}" "${MTA_GPG_KEY_ID:?}"
: "${MTA_GPG_PASSPHRASE_FILE:?}"
[[ $MTA_REPO_CHANNEL == early || $MTA_REPO_CHANNEL == stable ]] || exit 2
[[ $MTA_GPG_KEY_ID =~ ^[0-9A-Fa-f]{40}$ ]] || exit 2
[[ -s $MTA_GPG_PASSPHRASE_FILE ]] || { echo 'Signing passphrase not provided' >&2; exit 2; }
shopt -s nullglob
rpms=("$MTA_REPO_INPUT"/*.rpm)
debs=("$MTA_REPO_INPUT"/*.deb)
((${#rpms[@]} > 0 && ${#debs[@]} > 0)) || { echo 'Both real DEB and RPM artifacts required' >&2; exit 3; }
# Block an accidental stable release of early prerelease packages.
if [[ $MTA_REPO_CHANNEL == stable ]]; then
  for f in "${debs[@]}"; do
    version=$(dpkg-deb -f "$f" Version)
    [[ $version != *'~early'* && $version != *'~dev'* ]] || { echo "Prerelease DEB cannot enter stable: $version" >&2; exit 3; }
  done
  for f in "${rpms[@]}"; do
    version=$(rpm -qp --qf '%{RELEASE}' "$f")
    [[ $version != *early* && $version != *dev* ]] || { echo "Prerelease RPM cannot enter stable: $version" >&2; exit 3; }
  done
fi
gpg --batch --yes --armor --export "$MTA_GPG_KEY_ID" > "$MTA_REPO_INPUT/mta-key.asc"
rpm --import "$MTA_REPO_INPUT/mta-key.asc"
# rpmsign consumes the only imported private key in isolated GNUPGHOME.
# The explicit sign command uses loopback rather than trying to open an interactive pinentry.
for f in "${rpms[@]}"; do
  rpmsign --addsign \
    --define "_gpg_name $MTA_GPG_KEY_ID" \
    --define "__gpg_sign_cmd /usr/bin/gpg --batch --no-verbose --pinentry-mode loopback --passphrase-file $MTA_GPG_PASSPHRASE_FILE --no-armor --detach-sign --digest-algo sha256 --output %{__signature_filename} %{__plaintext_filename}" \
    "$f"
  rpm --checksig --verbose "$f" | grep -Eiq '(signature.*ok|pgp.*ok|rsa.*ok)' || { echo "RPM signature validation failed: $f" >&2; exit 4; }
done
MTA_REPO_INPUT="$MTA_REPO_INPUT" MTA_REPO_OUTPUT="$MTA_REPO_OUTPUT" MTA_REPO_CHANNEL="$MTA_REPO_CHANNEL" MTA_GPG_KEY_ID="$MTA_GPG_KEY_ID" bash scripts/repositories/build_indexes.sh
root="$MTA_REPO_OUTPUT"
gpg --verify "$root/apt/$MTA_REPO_CHANNEL/Release.gpg" "$root/apt/$MTA_REPO_CHANNEL/Release"
gpg --verify "$root/rpm/$MTA_REPO_CHANNEL/repodata/repomd.xml.asc" "$root/rpm/$MTA_REPO_CHANNEL/repodata/repomd.xml"
gpg --batch --show-keys --with-colons "$root/mta-archive-key.asc" | awk -F: '$1=="fpr" {print toupper($10); exit}' | grep -qx "${MTA_GPG_KEY_ID^^}"
echo 'Signed repository validated locally; not yet published.'
