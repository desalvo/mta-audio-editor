#!/usr/bin/env bash
# Disposable CI only: exercise actual apt upgrade/downgrade across two package versions.
set -Eeuo pipefail
: "${MTA_SERVER_DEB_OLD:?}" "${MTA_SERVER_DEB_NEW:?}"
[[ ${MTA_CI_DISPOSABLE_VM:-0} == 1 && $(id -u) == 0 && $(cat /proc/1/comm) == systemd ]] || { echo 'Disposable systemd CI VM only' >&2; exit 2; }
for pkg in "$MTA_SERVER_DEB_OLD" "$MTA_SERVER_DEB_NEW"; do
  [[ -f $pkg && $(dpkg-deb -f "$pkg" Package) == mta-audio-editor-server ]] || exit 3
done
old=$(dpkg-deb -f "$MTA_SERVER_DEB_OLD" Version)
new=$(dpkg-deb -f "$MTA_SERVER_DEB_NEW" Version)
dpkg --compare-versions "$old" lt "$new" || { echo 'Expected strictly increasing versions' >&2; exit 3; }
# The preceding CI step may already have installed the newer package.
# Remove the installed package first, but keep persistent data and config.
if dpkg-query -W -f='${Status}' mta-audio-editor-server 2>/dev/null | grep -qx 'install ok installed'; then
  apt-get -y remove mta-audio-editor-server
fi
apt-get -y install "$MTA_SERVER_DEB_OLD"
install -d -m 700 /var/lib/mta/projects
printf 'upgrade-downgrade-preserved\n' > /var/lib/mta/projects/.native-version-cycle
cp /etc/mta/mta.env "${RUNNER_TEMP:-/tmp}/mta-version-cycle.env"
check() {
  [[ $(dpkg-query -W -f='${Version}' mta-audio-editor-server) == "$1" ]]
  [[ $(cat /var/lib/mta/projects/.native-version-cycle) == upgrade-downgrade-preserved ]]
  cmp /etc/mta/mta.env "${RUNNER_TEMP:-/tmp}/mta-version-cycle.env"
  /opt/mta/server-venv/bin/python -m pip check
  MTA_CI_DISPOSABLE_VM=1 bash scripts/server_packages/check_system_services.sh
}
check "$old"
apt-get -y install "$MTA_SERVER_DEB_NEW"
check "$new"
apt-get -y --allow-downgrades install "$MTA_SERVER_DEB_OLD"
check "$old"
apt-get -y install "$MTA_SERVER_DEB_NEW"
check "$new"
echo 'APT upgrade/downgrade/re-upgrade/state/systemd: OK'
