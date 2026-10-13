#!/usr/bin/env bash
# Build RPM from the same offline application/wheel staging as DEB.
set -Eeuo pipefail
: "${MTA_SERVER_STAGE:?Provide CI staging root}"
: "${MTA_RPM_VERSION:?Provide X.Y.Z}"
: "${MTA_RPM_RELEASE:?Provide release number, for example 0.208.early or 1}"
: "${MTA_SERVER_OUTPUT:?Provide output directory}"
[[ $MTA_RPM_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ && $MTA_RPM_RELEASE =~ ^[0-9][a-zA-Z0-9._]*$ ]] || exit 2
command -v rpmbuild >/dev/null || { echo 'rpmbuild is required on an RPM build runner' >&2; exit 2; }
"${MTA_SERVER_PYTHON:-python3.12}" "$(dirname "$0")/validate_stage.py" "$MTA_SERVER_STAGE"
if [[ ${MTA_SERVER_RELEASE_READY:-0} == 1 ]]; then
  "${MTA_SERVER_PYTHON:-python3.12}" "$(dirname "$0")/verify_offline_runtime.py" "$MTA_SERVER_STAGE" --check-proof
fi
root=$(realpath "$MTA_SERVER_STAGE"); out=$(realpath -m "$MTA_SERVER_OUTPUT")
[[ -f "$root/application/app/main.py" && -f "$root/application/app/ai_cgroup_launcher.py" && -f "$root/application/requirements.txt" ]] || exit 3
[[ -n $(find "$root/wheelhouse" -name '*.whl' -print -quit) ]] || { echo 'Wheelhouse missing' >&2; exit 3; }
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
mkdir -p "$work"/{SOURCES,SPECS,BUILD,RPMS,SRPMS}
cp -a "$root/application" "$work/SOURCES/application"
cp -a "$root/wheelhouse" "$work/SOURCES/wheelhouse"
cp "$(dirname "$0")"/*.service "$(dirname "$0")"/*.timer "$work/SOURCES/"
cp "$(dirname "$0")/postinst" "$work/SOURCES/"
cp "$(dirname "$0")/install_runtime.py" "$work/SOURCES/"
cp "$(dirname "$0")/../install_ace_step.sh" "$(dirname "$0")/../install_rocm_userspace.sh" "$work/SOURCES/"
cat > "$work/SPECS/mta-server.spec" <<'SPEC'
Name: mta-audio-editor-server
Version: %{getenv:MTA_RPM_VERSION}
Release: %{getenv:MTA_RPM_RELEASE}%{?dist}
Summary: MTA Audio Editor web server and offline runtime dependencies
License: MIT
BuildArch: %{_arch}
Requires: python3.12, python3.12-pip, /usr/bin/ffmpeg, ca-certificates
AutoReqProv: no
%description
MTA Audio Editor web server, distinct from the desktop and Proxmox agent.
%install
mkdir -p %{buildroot}/usr/lib/mta-audio-editor-server %{buildroot}/usr/share/mta-audio-editor-server/wheelhouse %{buildroot}/usr/lib/systemd/system
cp -a %{_sourcedir}/application/. %{buildroot}/usr/lib/mta-audio-editor-server/
cp %{_sourcedir}/install_runtime.py %{buildroot}/usr/lib/mta-audio-editor-server/install_runtime.py
mkdir -p %{buildroot}/usr/lib/mta-audio-editor-server/native-installers
install -m 755 %{_sourcedir}/install_ace_step.sh %{buildroot}/usr/lib/mta-audio-editor-server/native-installers/install_ace_step.sh
install -m 755 %{_sourcedir}/install_rocm_userspace.sh %{buildroot}/usr/lib/mta-audio-editor-server/native-installers/install_rocm_userspace.sh
cp -a %{_sourcedir}/wheelhouse/. %{buildroot}/usr/share/mta-audio-editor-server/wheelhouse/
cp %{_sourcedir}/*.service %{_sourcedir}/*.timer %{buildroot}/usr/lib/systemd/system/
%pre
if [ -e /opt/mta/application/.git ] || [ -f /opt/mta/application/.mta-wizard-managed ]; then
  echo 'MTA legacy installation detected. Use explicit migration before installing native RPM.' >&2
  exit 1
fi
%post
if [ "$1" -ge 1 ]; then
  umask 077
  if [ -e /opt/mta/application/.git ] || [ -f /opt/mta/application/.mta-wizard-managed ]; then
    echo 'Legacy git-managed MTA detected; migrate explicitly before native installation' >&2
    exit 1
  fi
  mkdir -p /etc/mta /var/lib/mta/projects /var/lib/mta/models /opt/mta
  chmod 700 /etc/mta
  if [ ! -f /etc/mta/mta.env ]; then
    printf 'MTA_ADMIN_USERNAME=admin\nMTA_ADMIN_PASSWORD=%s\nMTA_DATA_DIR=/var/lib/mta/projects\n' "$(/usr/bin/python3.12 -c 'import secrets; print(secrets.token_urlsafe(24))')" > /etc/mta/mta.env
  fi
  chmod 600 /etc/mta/mta.env
  /usr/bin/python3.12 /usr/lib/mta-audio-editor-server/install_runtime.py --python /usr/bin/python3.12
  systemctl daemon-reload || :
  systemctl enable mta-server.service mta-billing-scheduler.timer || :
  systemctl try-restart mta-server.service || :
  systemctl start mta-server.service || :
  systemctl start mta-billing-scheduler.timer || :
fi
%preun
if [ "$1" -eq 0 ]; then systemctl stop mta-server.service mta-billing-scheduler.timer mta-billing-scheduler.service 2>/dev/null || :; fi
%files
/usr/lib/mta-audio-editor-server
/usr/share/mta-audio-editor-server/wheelhouse
/usr/lib/systemd/system/mta-server.service
/usr/lib/systemd/system/mta-billing-scheduler.service
/usr/lib/systemd/system/mta-billing-scheduler.timer
SPEC
export MTA_RPM_VERSION MTA_RPM_RELEASE
rpmbuild --define "_topdir $work" -bb "$work/SPECS/mta-server.spec"
mkdir -p "$out"; find "$work/RPMS" -name '*.rpm' -exec cp {} "$out/" \;
