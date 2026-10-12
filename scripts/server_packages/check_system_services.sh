#!/usr/bin/env bash
# Production acceptance on a disposable VM with systemd as PID 1; never silently skip.
set -Eeuo pipefail
[[ ${MTA_CI_DISPOSABLE_VM:-0} == 1 ]] || { echo 'Disposable VM opt-in required' >&2; exit 2; }
[[ $(id -u) == 0 ]] || exit 2
[[ $(cat /proc/1/comm) == systemd ]] || { echo 'Real systemd PID 1 required' >&2; exit 2; }
command -v curl >/dev/null
systemd-analyze verify /usr/lib/systemd/system/mta-server.service /usr/lib/systemd/system/mta-billing-scheduler.service /usr/lib/systemd/system/mta-billing-scheduler.timer
systemctl daemon-reload
systemctl enable --now mta-server.service mta-billing-scheduler.timer
systemctl is-active --quiet mta-server.service
systemctl is-active --quiet mta-billing-scheduler.timer
systemctl is-enabled --quiet mta-billing-scheduler.timer
systemctl show -p Delegate --value mta-server.service | grep -qx yes
# Scheduler is a oneshot job. Exercise it explicitly rather than requiring it to stay active.
systemctl start mta-billing-scheduler.service
systemctl show -p Result --value mta-billing-scheduler.service | grep -qx success
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8000/api/health >/dev/null
printf '%s\n' 'Native MTA systemd service/timer/HTTP acceptance passed'
