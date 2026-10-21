#!/usr/bin/env bash
# Build static signed APT and RPM repository trees from previously validated package files.
set -Eeuo pipefail
: "${MTA_REPO_INPUT:?Provide directory with validated DEB/RPM packages}"
: "${MTA_REPO_OUTPUT:?Provide destination directory}"
: "${MTA_REPO_CHANNEL:?early or stable}"
: "${MTA_GPG_KEY_ID:?Set full signing key fingerprint (available in isolated publisher)}"
[[ $MTA_REPO_CHANNEL == early || $MTA_REPO_CHANNEL == stable ]] || exit 2
[[ $MTA_GPG_KEY_ID =~ ^[A-Fa-f0-9]{40}$ ]] || { echo 'Full 40-hex GPG fingerprint required' >&2; exit 2; }
# Only a disposable CI container may exercise the APT-only fixture path.
# Production repository publishing always requires both signed EL9 and EL10 RPMs.
apt_only=${MTA_CI_APT_ONLY:-0}
if [[ $apt_only == 1 ]]; then
  [[ ${MTA_CI_DISPOSABLE_CONTAINER:-0} == 1 && ${CI:-} == true ]] || {
    echo 'APT-only mode is restricted to disposable CI' >&2; exit 2;
  }
fi
for tool in dpkg-scanpackages apt-ftparchive gpg; do command -v "$tool" >/dev/null || { echo "Missing $tool" >&2; exit 2; }; done
src=$(realpath "$MTA_REPO_INPUT")
out=$(realpath -m "$MTA_REPO_OUTPUT")
[[ -d $src && $src != "$out" ]] || exit 2
# Prune stale package binaries BEFORE copying any of the three OS variants.
# Retention was performed against incoming artifacts prior to signing.
python3 "$(dirname "$0")/preflight_package_copy.py" \
  --input "$src" --output "$out" --channel "$MTA_REPO_CHANNEL"
mkdir -p "$out/apt/$MTA_REPO_CHANNEL/pool"
if [[ $apt_only != 1 ]]; then
  command -v createrepo_c >/dev/null || { echo 'Missing createrepo_c' >&2; exit 2; }
  command -v rpm >/dev/null || { echo 'Missing rpm' >&2; exit 2; }
  mkdir -p "$out/rpm/$MTA_REPO_CHANNEL/el9/packages"
fi
shopt -s nullglob
for f in "$src"/*.deb; do
  [[ $(dpkg-deb -f "$f" Package) == mta-audio-editor-server ]] || { echo "Not a server package: $f" >&2; exit 3; }
  cp -n "$f" "$out/apt/$MTA_REPO_CHANNEL/pool/"
done
if [[ $apt_only != 1 ]]; then
for target in el9 el10; do
  mkdir -p "$out/rpm/$MTA_REPO_CHANNEL/$target/packages"
  for f in "$src/rpm/$target/"*.rpm; do
    [[ $(rpm -qp --qf '%{NAME}' "$f") == mta-audio-editor-server ]] || { echo "Not a server package: $f" >&2; exit 3; }
    cp -n "$f" "$out/rpm/$MTA_REPO_CHANNEL/$target/packages/"
  done
done
fi
aptroot="$out/apt/$MTA_REPO_CHANNEL"
[[ -n $(find "$aptroot/pool" -maxdepth 1 -name '*.deb' -print -quit) ]] || { echo 'No server DEB packages' >&2; exit 3; }
( cd "$aptroot"; dpkg-scanpackages --multiversion pool /dev/null > Packages; gzip -n -9 -c Packages > Packages.gz )
cat > "$aptroot/apt-release.conf" <<EOF
APT::FTPArchive::Release::Origin "MTA Audio Editor";
APT::FTPArchive::Release::Label "MTA Audio Editor Server";
APT::FTPArchive::Release::Suite "$MTA_REPO_CHANNEL";
APT::FTPArchive::Release::Codename "$MTA_REPO_CHANNEL";
APT::FTPArchive::Release::Architectures "amd64 arm64";
APT::FTPArchive::Release::Components "main";
EOF
( cd "$aptroot"; apt-ftparchive -c apt-release.conf release . > Release )
gpg --batch --yes --local-user "$MTA_GPG_KEY_ID" --armor --detach-sign -o "$aptroot/Release.gpg" "$aptroot/Release"
gpg --batch --yes --local-user "$MTA_GPG_KEY_ID" --clearsign -o "$aptroot/InRelease" "$aptroot/Release"
rm "$aptroot/apt-release.conf"
if [[ $apt_only != 1 ]]; then
for target in el9 el10; do
  rpmroot="$out/rpm/$MTA_REPO_CHANNEL/$target"
  [[ -n $(find "$rpmroot/packages" -maxdepth 1 -name '*.rpm' -print -quit) ]] || { echo "No $target RPM packages" >&2; exit 3; }
  for file in "$rpmroot"/packages/*.rpm; do
    rpm --checksig "$file" | grep -Eiq '(signatures ok|pgp.*ok|rsa.*ok)' || { echo "RPM not signed: $file" >&2; exit 4; }
  done
  createrepo_c --update "$rpmroot"
  gpg --batch --yes --local-user "$MTA_GPG_KEY_ID" --armor --detach-sign -o "$rpmroot/repodata/repomd.xml.asc" "$rpmroot/repodata/repomd.xml"
done
fi
gpg --batch --yes --armor --export "$MTA_GPG_KEY_ID" > "$out/mta-archive-key.asc"
echo "Repository staging generated: $out ($MTA_REPO_CHANNEL)"
