#!/usr/bin/env bash
# Destructive CI integration test: never run on a real host.
set -Eeuo pipefail
: "${MTA_SERVER_RPM:?Path to a release-ready server RPM is required}"
[[ ${MTA_CI_DISPOSABLE_CONTAINER:-0} == 1 ]] || { echo 'Refusing RPM install test outside disposable CI container' >&2; exit 2; }
[[ $(id -u) == 0 ]] || { echo 'Root is required' >&2; exit 2; }
[[ -f $MTA_SERVER_RPM ]] || exit 2
[[ $(rpm -qp --qf '%{NAME}' "$MTA_SERVER_RPM") == mta-audio-editor-server ]] || exit 3
command -v dnf >/dev/null || exit 2
# All OS dependencies must be available from preconfigured, trusted repositories.
dnf -y install "$MTA_SERVER_RPM"
rpm -q mta-audio-editor-server
[[ -x /opt/mta/server-venv/bin/python ]]
/opt/mta/server-venv/bin/python -m pip check
mkdir -p /var/lib/mta/projects
printf '%s\n' persistent-rpm-project-fixture > /var/lib/mta/projects/.native-rpm-upgrade-fixture
cp -p /etc/mta/mta.env /tmp/mta-rpm-env-before-upgrade
dnf -y reinstall "$MTA_SERVER_RPM"
[[ $(cat /var/lib/mta/projects/.native-rpm-upgrade-fixture) == persistent-rpm-project-fixture ]]
cmp /etc/mta/mta.env /tmp/mta-rpm-env-before-upgrade
/opt/mta/server-venv/bin/python -m pip check
printf '%s\n' 'RPM install/reinstall/state-preservation: OK'
