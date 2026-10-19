#!/usr/bin/env bash
# Reproducible payload-only DEB from CI-prepared offline artifacts.
set -Eeuo pipefail
: "${MTA_SERVER_STAGE:?Stage must contain application/ and wheelhouse/}"
: "${MTA_SERVER_VERSION:?Debian version required}"
: "${MTA_SERVER_OUTPUT:?Output directory required}"
[[ $MTA_SERVER_VERSION =~ ^[0-9][a-zA-Z0-9.+:~_-]*$ ]] || exit 2
for cmd in dpkg-deb find; do command -v "$cmd" >/dev/null || exit 2; done
"${MTA_SERVER_PYTHON:-python3}" "$(dirname "$0")/validate_stage.py" "$MTA_SERVER_STAGE"
if [[ ${MTA_SERVER_RELEASE_READY:-0} == 1 ]]; then
  "${MTA_SERVER_PYTHON:-python3}" "$(dirname "$0")/verify_offline_runtime.py" "$MTA_SERVER_STAGE" --check-proof
fi
if [[ ${MTA_SERVER_RELEASE_READY:-0} == 1 ]]; then
  for metadata in VERSION REVISION BUILD_INFO RELEASE_CHANNEL; do
    [[ -f "$MTA_SERVER_STAGE/application/$metadata" ]] || {
      echo "Missing native release metadata: $metadata" >&2
      exit 3
    }
  done
fi

stage=$(realpath "$MTA_SERVER_STAGE"); out=$(realpath -m "$MTA_SERVER_OUTPUT")
[[ -f "$stage/application/app/main.py" && -f "$stage/application/app/ai_cgroup_launcher.py" && -f "$stage/application/requirements.txt" ]] || { echo 'Incomplete server application staging' >&2; exit 3; }
[[ -d "$stage/wheelhouse" && -n $(find "$stage/wheelhouse" -name '*.whl' -print -quit) ]] || { echo 'Offline wheelhouse is required; refusing network install at deployment' >&2; exit 3; }
[[ ! -e "$stage/application/.git" ]] || { echo 'Git metadata forbidden in server package' >&2; exit 3; }
arch=${MTA_DEB_ARCH:-$(dpkg --print-architecture)}
# Distribution-specific Python ABI: never deploy a cp313 wheelhouse into cp312.
if [[ ${MTA_SERVER_RELEASE_READY:-0} == 1 ]]; then
  pyminor=$("${MTA_SERVER_PYTHON:-python3}" -c 'import sys;print(".".join(map(str,sys.version_info[:2])))')
  case "$pyminor" in
    3.12) py_deps='python3 (>= 3.12), python3 (<< 3.13), python3-venv' ;;
    3.13) py_deps='python3 (>= 3.13), python3 (<< 3.14), python3-venv' ;;
    *) echo "Unsupported Debian server Python $pyminor" >&2; exit 3 ;;
  esac
else
  py_deps='python3 (>= 3.12), python3-venv'
fi
[[ $arch == amd64 || $arch == arm64 ]] || { echo 'Unsupported architecture' >&2; exit 3; }
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
root="$work/root"
mkdir -p "$root/DEBIAN" "$root/usr/lib/mta-audio-editor-server" "$root/usr/share/mta-audio-editor-server/wheelhouse" "$root/usr/lib/systemd/system"
cp -a "$stage/application/." "$root/usr/lib/mta-audio-editor-server/"
# Staging fixtures deliberately omit optional worker entrypoints. Real release
# staging must include the worker; never let a fixture bypass the release gate.
worker="$root/usr/lib/mta-audio-editor-server/app/ace_step_http_worker.py"
if [[ -f "$worker" && ! -L "$worker" ]]; then
  chmod 755 "$worker"
elif [[ ${MTA_SERVER_RELEASE_READY:-0} == 1 ]]; then
  echo 'Release staging is missing the ACE-Step worker' >&2
  exit 3
fi
cp -a "$stage/wheelhouse/." "$root/usr/share/mta-audio-editor-server/wheelhouse/"
cp "$(dirname "$0")/install_runtime.py" "$root/usr/lib/mta-audio-editor-server/install_runtime.py"
install -d -m 755 "$root/usr/lib/mta-audio-editor-server/native-installers"
install -m 755 "$(dirname "$0")/../install_ai_engines.py" "$root/usr/lib/mta-audio-editor-server/native-installers/install_ai_engines.py"
for requirement in requirements-stems.txt requirements-lyrics.txt requirements-chords.txt requirements-roformer-compat.txt; do
 install -m 644 "$(dirname "$0")/../../$requirement" "$root/usr/lib/mta-audio-editor-server/$requirement"
done
install -m 755 "$(dirname "$0")/../install_ace_step.sh" "$root/usr/lib/mta-audio-editor-server/native-installers/install_ace_step.sh"
install -m 755 "$(dirname "$0")/../configure_ai_workers.py" "$root/usr/lib/mta-audio-editor-server/native-installers/configure_ai_workers.py"
install -m 755 "$(dirname "$0")/../gpu_verified_billing.py" "$root/usr/lib/mta-audio-editor-server/native-installers/gpu_verified_billing.py"
install -m 755 "$(dirname "$0")/../install_demucs.py" "$root/usr/lib/mta-audio-editor-server/native-installers/install_demucs.py"
install -m 755 "$(dirname "$0")/../install_rocm_userspace.sh" "$root/usr/lib/mta-audio-editor-server/native-installers/install_rocm_userspace.sh"
cp "$(dirname "$0")/mta-server.service" "$root/usr/lib/systemd/system/mta-server.service"
cp "$(dirname "$0")/mta-billing-scheduler.service" "$root/usr/lib/systemd/system/mta-billing-scheduler.service"
cp "$(dirname "$0")/mta-billing-scheduler.timer" "$root/usr/lib/systemd/system/mta-billing-scheduler.timer"
cat > "$root/DEBIAN/control" <<EOF
Package: mta-audio-editor-server
Version: $MTA_SERVER_VERSION
Section: sound
Priority: optional
Architecture: $arch
Maintainer: MTA Audio Editor maintainers
Depends: $py_deps, ffmpeg, ca-certificates, libstdc++6, libasound2t64 | libasound2, libfreetype6, libx11-6, libxext6, libxrandr2, libxinerama1, libxcursor1, libgl1, libgl1-mesa-dri, xvfb, libxtst6
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

# Fail closed when the actual final artifact lacks native installers.
"${MTA_SERVER_PYTHON:-python3}" "$(dirname "$0")/verify_native_installers.py" "$out"/*.deb
