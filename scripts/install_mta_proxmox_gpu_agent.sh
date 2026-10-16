#!/usr/bin/env bash
# Optional Proxmox host-only AMD SMI service. Does not modify GPU kernel drivers.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run as root on Proxmox host' >&2; exit 1; }
command -v amd-smi >/dev/null || { echo 'Install amd-smi on Proxmox host first' >&2; exit 1; }
[[ -f scripts/mta_proxmox_gpu_agent.py ]] || { echo 'Run from the MTA repository root' >&2; exit 1; }
install -d -m 0750 /opt/mta-gpu-agent
install -m 0755 scripts/mta_proxmox_gpu_agent.py /opt/mta-gpu-agent/agent.py
if [[ ! -f /etc/mta-gpu-agent.env ]]; then
  umask 077
  python3 - <<'PY' > /etc/mta-gpu-agent.env
import secrets
print('MTA_GPU_AGENT_TOKEN='+secrets.token_urlsafe(36))
PY
fi
chmod 0600 /etc/mta-gpu-agent.env
cat > /etc/systemd/system/mta-gpu-agent.service <<'EOF'
[Unit]
Description=Optional MTA Proxmox AMD GPU telemetry agent
After=local-fs.target
[Service]
Type=simple
EnvironmentFile=/etc/mta-gpu-agent.env
ExecStart=/usr/bin/python3 /opt/mta-gpu-agent/agent.py
Restart=on-failure
RestartSec=5
RuntimeDirectory=mta-gpu-agent
RuntimeDirectoryMode=0750
RuntimeDirectoryPreserve=yes
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now mta-gpu-agent.service
echo 'Agent installed; bind-mount /run/mta-gpu-agent into the LXC explicitly and configure the token securely.'
