#!/usr/bin/env bash
# Reproducible payload-only DEB from CI-prepared offline artifacts.
set -Eeuo pipefail
: "${MTA_SERVER_STAGE:?Stage must contain application/ and wheelhouse/}"
: "${MTA_SERVER_VERSION:?Debian version required}"
: "${MTA_SERVER_OUTPUT:?Output directory required}"
[[ $MTA_SERVER_VERSION =~ ^[0-9][a-zA-Z0-9.+:~_-]*$ ]] || exit 2
for cmd in dpkg-deb find; do command -v "$cmd" >/dev/null || exit 2; done
python3 "$(dirname "$0")/validate_stage.py" "$MTA_SERVER_STAGE"
if [[ ${MTA_SERVER_RELEASE_READY:-0} == 1 ]]; then
  python3 "$(dirname "$0")/verify_offline_runtime.py" "$MTA_SERVER_STAGE" --check-proof
fi
stage=$(realpath "$MTA_SERVER_STAGE"); out=$(realpath -m "$MTA_SERVER_OUTPUT")
[[ -f "$stage/application/app/main.py" && -f "$stage/application/app/ai_cgroup_launcher.py" && -f "$stage/application/requirements.txt" ]] || { echo 'Incomplete server application staging' >&2; exit 3; }
[[ -d "$stage/wheelhouse" && -n $(find "$stage/wheelhouse" -name '*.whl' -print -quit) ]] || { echo 'Offline wheelhouse is required; refusing network install at deployment' >&2; exit 3; }
[[ ! -e "$stage/application/.git" ]] || { echo 'Git metadata forbidden in server package' >&2; exit 3; }
arch=${MTA_DEB_ARCH:-$(dpkg --print-architecture)}
[[ $arch == amd64 || $arch == arm64 ]] || { echo 'Unsupported architecture' >&2; exit 3; }
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
root="$work/root"
mkdir -p "$root/DEBIAN" "$root/usr/lib/mta-audio-editor-server" "$root/usr/share/mta-audio-editor-server/wheelhouse" "$root/usr/lib/systemd/system"
cp -a "$stage/application/." "$root/usr/lib/mta-audio-editor-server/"
cp -a "$stage/wheelhouse/." "$root/usr/share/mta-audio-editor-server/wheelhouse/"
cp "$(dirname "$0")/install_runtime.py" "$root/usr/lib/mta-audio-editor-server/install_runtime.py"
cp "$(dirname "$0")/mta-server.service" "$root/usr/lib/systemd/system/mta-server.service"
cp "$(dirname "$0")/mta-billing-scheduler.service" "$root/usr/lib/systemd/system/mta-billing-scheduler.service"
cat > "$root/DEBIAN/control" <<EOF
Package: mta-audio-editor-server
Version: $MTA_SERVER_VERSION
Section: sound
Priority: optional
Architecture: $arch
Maintainer: MTA Audio Editor maintainers
Depends: python3 (>= 3.12), python3-venv, ffmpeg, ca-certificates
Description: MTA Audio Editor web server with offline Python dependencies
 Server application; distinct from the desktop editor and Proxmox GPU agent.
EOF
cp "$(dirname "$0")/preinst" "$root/DEBIAN/preinst"
cp "$(dirname "$0")/postinst" "$root/DEBIAN/postinst"
cp "$(dirname "$0")/prerm" "$root/DEBIAN/prerm"
chmod 0755 "$root/DEBIAN/preinst" "$root/DEBIAN/postinst" "$root/DEBIAN/prerm"
find "$root" -exec touch -h -d "@${SOURCE_DATE_EPOCH:-1700000000}" {} +
mkdir -p "$out"
dpkg-deb --root-owner-group --build "$root" "$out/mta-audio-editor-server_${MTA_SERVER_VERSION}_${arch}.deb"
