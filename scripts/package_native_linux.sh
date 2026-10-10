#!/usr/bin/env bash
set -euo pipefail
# Run on the same CPU architecture as the PyInstaller bundle; no cross-arch repacking.
: "${MTA_NATIVE_DIST:?set MTA_NATIVE_DIST to the PyInstaller dist/MTA Audio Editor directory}"
command -v dpkg-deb >/dev/null
command -v rpmbuild >/dev/null
root="$(cd "$(dirname "$0")/.." && pwd)"
version="$(tr -d '\r\n' < "$root/VERSION")"
revision="$(tr -d '\r\n' < "$root/REVISION")"
arch="$(uname -m)"
case "$arch" in x86_64) deb_arch=amd64; rpm_arch=x86_64;; aarch64|arm64) deb_arch=arm64; rpm_arch=aarch64;; *) echo "Unsupported architecture: $arch" >&2; exit 1;; esac
name=mta-audio-editor
out="${MTA_LINUX_OUTPUT:-$root/dist-installer}"
mkdir -p "$out"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
stage="$work/deb"
mkdir -p "$stage/opt/mta-audio-editor" "$stage/usr/bin" "$stage/usr/share/applications" "$stage/DEBIAN"
cp -a "$MTA_NATIVE_DIST"/. "$stage/opt/mta-audio-editor/"
cat > "$stage/usr/bin/mta-audio-editor" <<'EOF'
#!/bin/sh
exec '/opt/mta-audio-editor/MTA Audio Editor' "$@"
EOF
chmod 755 "$stage/usr/bin/mta-audio-editor"
cat > "$stage/usr/share/applications/mta-audio-editor.desktop" <<'EOF'
[Desktop Entry]
Name=MTA Audio Editor
Comment=Multi-track audio editor
Exec=mta-audio-editor %F
Terminal=false
Type=Application
Categories=AudioVideo;Audio;AudioVideoEditing;
MimeType=application/x-mta-audio-editor-project;
EOF
cat > "$stage/DEBIAN/control" <<EOF
Package: $name
Version: $version-$revision
Section: sound
Priority: optional
Architecture: $deb_arch
Maintainer: MTA Audio Editor <noreply@github.com>
Depends: libgtk-3-0 | libgtk-3-0t64, libwebkit2gtk-4.1-0 | libwebkit2gtk-4.1-0t64
Description: MTA Audio Editor native desktop client
 Local single-user audio editor. VST3 plugins are installed separately.
EOF
dpkg-deb --build --root-owner-group "$stage" "$out/${name}_${version}-${revision}_${deb_arch}.deb"
mkdir -p "$work/rpmbuild"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}
tar -C "$stage" --exclude=DEBIAN -czf "$work/rpmbuild/SOURCES/${name}.tar.gz" .
cat > "$work/rpmbuild/SPECS/${name}.spec" <<EOF
Name: $name
Version: $version
Release: $revision%{?dist}
Summary: MTA Audio Editor native desktop client
License: EUPL-1.2
BuildArch: $rpm_arch
Source0: %{name}.tar.gz
Requires: gtk3, webkit2gtk4.1
AutoReqProv: no
%description
Local single-user audio editor with optional VST3 effects.
%prep
%build
%install
mkdir -p %{buildroot}
tar -xf %{SOURCE0} -C %{buildroot}
%files
/opt/mta-audio-editor
/usr/bin/mta-audio-editor
/usr/share/applications/mta-audio-editor.desktop
EOF
rpmbuild --define "_topdir $work/rpmbuild" -bb "$work/rpmbuild/SPECS/${name}.spec"
find "$work/rpmbuild/RPMS" -name '*.rpm' -exec cp -v {} "$out/" \;
(cd "$out" && sha256sum *.deb *.rpm > SHA256SUMS)
