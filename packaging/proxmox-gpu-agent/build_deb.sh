#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/dist}"
VERSION=0.3.0-208.9
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PKG="$TMP/pkg"
install -d -m 0755 "$PKG/DEBIAN" "$PKG/usr/lib/mta-proxmox-gpu-agent" "$PKG/usr/bin" "$PKG/lib/systemd/system"
install -m 0755 "$ROOT/scripts/mta_proxmox_gpu_agent.py" "$PKG/usr/lib/mta-proxmox-gpu-agent/agent.py"
install -m 0755 "$ROOT/scripts/mta_proxmox_tag_sync.py" "$PKG/usr/lib/mta-proxmox-gpu-agent/tag_sync.py"
install -m 0755 "$ROOT/scripts/mta_proxmox_gpu_preflight.py" "$PKG/usr/lib/mta-proxmox-gpu-agent/preflight.py"
install -m 0755 "$ROOT/scripts/mta_proxmox_gpu_readiness.py" "$PKG/usr/lib/mta-proxmox-gpu-agent/readiness.py"
cat > "$PKG/DEBIAN/control" <<EOF
Package: mta-proxmox-gpu-agent
Version: $VERSION
Architecture: all
Maintainer: MTA Audio Editor <noreply@example.com>
Depends: python3, systemd, pve-container, acl, amd-smi
Section: admin
Priority: optional
Description: Optional Proxmox AMD GPU telemetry for MTA Audio Editor
 UNIX socket AMD SMI telemetry and opt-in tagged LXC discovery.
EOF
cat > "$PKG/DEBIAN/postinst" <<'SH2'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
 install -d -m 0700 /etc/mta-gpu-agent
 if [ ! -f /etc/mta-gpu-agent/token ]; then
  python3 -c 'import secrets;print(secrets.token_urlsafe(40))' > /etc/mta-gpu-agent/token
 fi
 chmod 0600 /etc/mta-gpu-agent/token
 systemctl daemon-reload || true
 systemctl enable mta-gpu-agent.service || true
 systemctl try-restart mta-gpu-agent.service || true
 systemctl start mta-gpu-agent.service || true
 systemctl enable --now mta-gpu-agent-tag-sync.timer || true
 if /usr/bin/python3 /usr/lib/mta-proxmox-gpu-agent/preflight.py; then
  systemctl start mta-gpu-agent-tag-sync.service || true
 else
  echo "MTA GPU telemetry unavailable; LXC mounts will not be configured until a supported AMD GPU is available." >&2
 fi
fi
exit 0
SH2
cat > "$PKG/DEBIAN/prerm" <<'SH2'
#!/bin/sh
set -e
if [ "$1" = remove ]; then
 systemctl disable --now mta-gpu-agent-tag-sync.timer || true
 systemctl disable --now mta-gpu-agent.service || true
fi
exit 0
SH2
chmod 0755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/prerm"
cat > "$PKG/lib/systemd/system/mta-gpu-agent.service" <<'UNIT'
[Unit]
Description=MTA AMD GPU telemetry agent for Proxmox LXC
After=local-fs.target
ConditionPathExists=/etc/mta-gpu-agent/token
[Service]
Type=simple
ExecCondition=/usr/bin/python3 /usr/lib/mta-proxmox-gpu-agent/preflight.py
ExecStartPre=/usr/bin/install -m 0600 /etc/mta-gpu-agent/token /run/mta-gpu-agent/token
ExecStart=/usr/bin/python3 /usr/lib/mta-proxmox-gpu-agent/agent.py
EnvironmentFile=-/etc/mta-gpu-agent/agent.env
Restart=on-failure
RestartSec=5
RuntimeDirectory=mta-gpu-agent
RuntimeDirectoryMode=0750
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
UNIT
cat > "$PKG/lib/systemd/system/mta-gpu-agent-tag-sync.service" <<'UNIT'
[Unit]
Description=Discover authorized MTA tagged Proxmox LXCs
ConditionPathIsDirectory=/etc/pve/lxc
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/lib/mta-proxmox-gpu-agent/tag_sync.py --apply
UNIT
cat > "$PKG/lib/systemd/system/mta-gpu-agent-tag-sync.timer" <<'UNIT'
[Unit]
Description=Reconcile tagged MTA LXCs with local GPU agent
[Timer]
OnBootSec=2min
OnUnitInactiveSec=5min
Persistent=true
[Install]
WantedBy=timers.target
UNIT
mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$PKG" "$OUT/mta-proxmox-gpu-agent_${VERSION}_all.deb"
