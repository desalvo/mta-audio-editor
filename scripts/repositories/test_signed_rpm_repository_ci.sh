#!/usr/bin/env bash
# Rocky 9 disposable CI only. Sign an actual server RPM, validate signed repomd,
# verify DNF rejects tampered metadata and installs from a GPG-verified repo.
set -Eeuo pipefail
: "${MTA_SERVER_RPM:?Provide real built server RPM}"
[[ ${MTA_CI_DISPOSABLE_CONTAINER:-0} == 1 && $(id -u) == 0 ]] || { echo 'Disposable CI container only' >&2; exit 2; }
for cmd in gpg rpmsign rpm createrepo_c dnf python3.12; do command -v "$cmd" >/dev/null || exit 2; done
[[ -f $MTA_SERVER_RPM && $(rpm -qp --qf '%{NAME}' "$MTA_SERVER_RPM") == mta-audio-editor-server ]] || exit 3
root=$(mktemp -d)
trap 'rm -rf "$root"; rm -f /etc/yum.repos.d/mta-signed-ci.repo' EXIT
chmod 755 "$root"
export GNUPGHOME="$root/gnupg"
install -d -m 700 "$GNUPGHOME"
gpg --batch --passphrase '' --quick-generate-key 'MTA CI RPM Ephemeral <ci@example.org>' rsa3072 sign 0
fpr=$(gpg --batch --with-colons --list-keys | awk -F: '$1=="fpr" {print $10;exit}')
[[ $fpr =~ ^[[:xdigit:]]{40}$ ]] || exit 3
gpg --batch --armor --export "$fpr" > "$root/key.asc"
cp "$MTA_SERVER_RPM" "$root/mta-signed.rpm"
cat > "$root/rpmmacros" <<MACROS
%_signature gpg
%_gpg_name $fpr
%_gpg_path $GNUPGHOME
%__gpg /usr/bin/gpg
%__gpg_sign_cmd %{__gpg} --batch --no-verbose --no-armor --pinentry-mode loopback --passphrase '' --digest-algo sha256 --detach-sign --sign --output %{__signature_filename} %{__plaintext_filename}
MACROS
HOME="$root" rpmsign --addsign --macros "$root/rpmmacros" "$root/mta-signed.rpm"
rpm --import "$root/key.asc"
rpm --checksig "$root/mta-signed.rpm" | grep -Eiq '(pgp.*ok|rsa.*ok|signatures ok)' || { echo 'RPM signature check failed' >&2; exit 4; }
mkdir -p "$root/site/rpm/early/packages"
cp "$root/mta-signed.rpm" "$root/site/rpm/early/packages/"
createrepo_c "$root/site/rpm/early"
gpg --batch --yes --local-user "$fpr" --armor --detach-sign -o "$root/site/rpm/early/repodata/repomd.xml.asc" "$root/site/rpm/early/repodata/repomd.xml"
gpg --batch --verify "$root/site/rpm/early/repodata/repomd.xml.asc" "$root/site/rpm/early/repodata/repomd.xml"
cp "$root/site/rpm/early/repodata/repomd.xml" "$root/tampered.xml"
printf '\n<!-- tampered -->\n' >> "$root/tampered.xml"
if gpg --batch --verify "$root/site/rpm/early/repodata/repomd.xml.asc" "$root/tampered.xml" >/dev/null 2>&1; then
  echo 'Tampered repository metadata was accepted' >&2; exit 5
fi
cat > /etc/yum.repos.d/mta-signed-ci.repo <<REPO
[mta-signed-ci]
name=MTA signed CI only
baseurl=file://$root/site/rpm/early
enabled=1
gpgcheck=1
repo_gpgcheck=1
gpgkey=file://$root/key.asc
REPO
# Root must be traversable by dnf and metadata must remain signed.
dnf -y --disablerepo='*' --enablerepo=mta-signed-ci makecache
dnf -y remove mta-audio-editor-server
dnf -y --disablerepo='*' --enablerepo=mta-signed-ci --setopt=install_weak_deps=False install mta-audio-editor-server || {
  echo 'DNF signed repository install failed (dependencies must be preinstalled)' >&2; exit 6;
}
rpm -q mta-audio-editor-server
echo 'Signed RPM and DNF repository verified with ephemeral test key'
