#!/usr/bin/env bash
# Disposable CI only: actual DNF update/downgrade across two native RPM versions.
set -Eeuo pipefail
: "${MTA_SERVER_RPM_OLD:?}" "${MTA_SERVER_RPM_NEW:?}"
[[ ${MTA_CI_DISPOSABLE_CONTAINER:-0} == 1 && $(id -u) == 0 ]] || { echo 'Disposable CI container only' >&2; exit 2; }
for pkg in "$MTA_SERVER_RPM_OLD" "$MTA_SERVER_RPM_NEW"; do
  [[ -f $pkg && $(rpm -qp --qf '%{NAME}' "$pkg") == mta-audio-editor-server ]] || exit 3
done
old=$(rpm -qp --qf '%{VERSION}-%{RELEASE}' "$MTA_SERVER_RPM_OLD")
new=$(rpm -qp --qf '%{VERSION}-%{RELEASE}' "$MTA_SERVER_RPM_NEW")
[[ $old != "$new" ]] || exit 3
# A previous CI stage has installed the current package: start from the old RPM.
if rpm -q mta-audio-editor-server >/dev/null 2>&1; then
  dnf -y remove mta-audio-editor-server
fi
dnf -y install "$MTA_SERVER_RPM_OLD"
install -d -m 700 /var/lib/mta/projects
printf 'rpm-cycle-preserved\n' > /var/lib/mta/projects/.native-version-cycle
cp /etc/mta/mta.env /tmp/mta-rpm-version-cycle.env
check() {
  [[ $(rpm -q --qf '%{VERSION}-%{RELEASE}' mta-audio-editor-server) == "$1" ]]
  [[ $(cat /var/lib/mta/projects/.native-version-cycle) == rpm-cycle-preserved ]]
  cmp /etc/mta/mta.env /tmp/mta-rpm-version-cycle.env
  /opt/mta/server-venv/bin/python -m pip check
  (cd /usr/lib/mta-audio-editor-server && /opt/mta/server-venv/bin/python -c 'import app.main')
}
check "$old"
dnf -y upgrade "$MTA_SERVER_RPM_NEW"
check "$new"
dnf -y downgrade "$MTA_SERVER_RPM_OLD"
check "$old"
dnf -y upgrade "$MTA_SERVER_RPM_NEW"
check "$new"
echo 'DNF upgrade/downgrade/re-upgrade/state: OK'
