#!/usr/bin/env bash
# CI only: execute in an isolated disposable Debian container, never on a live host.
set -Eeuo pipefail
: "${MTA_SERVER_DEB:?Path to built DEB required}"
[[ ${MTA_CI_DISPOSABLE_CONTAINER:-0} == 1 ]] || { echo 'Refusing installation test outside disposable CI container' >&2; exit 2; }
[[ $(id -u) == 0 ]] || { echo 'Root required' >&2; exit 2; }
[[ -f "$MTA_SERVER_DEB" ]] || exit 2
[[ $(dpkg-deb --field "$MTA_SERVER_DEB" Package) == mta-audio-editor-server ]] || exit 3
apt-get update
apt-get install -y "$MTA_SERVER_DEB"
dpkg-query -W -f='${Status}\n' mta-audio-editor-server | grep -qx 'install ok installed'
test -x /opt/mta/server-venv/bin/python
/opt/mta/server-venv/bin/python -m pip check
(cd /usr/lib/mta-audio-editor-server && /opt/mta/server-venv/bin/python -c 'import app.ai_cgroup_launcher, app.main')
/opt/mta/server-venv/bin/python scripts/server_packages/http_smoke.py
mkdir -p /var/lib/mta/projects
printf '%s\n' 'persistent-project-fixture' > /var/lib/mta/projects/.native-upgrade-fixture
cp /etc/mta/mta.env /tmp/mta-env-before-upgrade
apt-get install -y --reinstall "$MTA_SERVER_DEB"
test "$(cat /var/lib/mta/projects/.native-upgrade-fixture)" = 'persistent-project-fixture'
cmp /etc/mta/mta.env /tmp/mta-env-before-upgrade
/opt/mta/server-venv/bin/python -m pip check
(cd /usr/lib/mta-audio-editor-server && /opt/mta/server-venv/bin/python -c 'import app.ai_cgroup_launcher, app.main')
/opt/mta/server-venv/bin/python scripts/server_packages/http_smoke.py
echo 'DEB install/reinstall/state-preservation: OK'
