#!/usr/bin/env bash
# Configure MTA's web backend with local ACE-Step, preserving the operator's data.
set -Eeuo pipefail
if [[ ${1:-} == '--help' ]]; then
  echo 'sudo MTA_APP_DIR=/opt/mta/application MTA_APP_PYTHON=/opt/mta/venv-mta/bin/python bash scripts/install_mta_lxc_service.sh'
  exit 0
fi
[[ $EUID -eq 0 ]] || { echo 'Requires root' >&2; exit 1; }
APP_DIR="${MTA_APP_DIR:-/opt/mta/application}"
PYTHON="${MTA_APP_PYTHON:-/opt/mta/venv-mta/bin/python}"
USER_NAME="${MTA_APP_USER:-root}"
[[ "$APP_DIR" == /* && "$PYTHON" == /* && "$APP_DIR" != / ]] || exit 2
id "$USER_NAME" >/dev/null
[[ -f "$APP_DIR/app/main.py" && -x "$PYTHON" && -f "$APP_DIR/app/ace_step_http_worker.py" ]] || {
  echo 'MTA source/runtime missing; install the MTA source and dependencies first.' >&2
  exit 3
}
mkdir -p /etc/mta /var/lib/mta/projects
ENVFILE=/etc/mta/mta.env
if [[ ! -f "$ENVFILE" ]]; then
  cat > "$ENVFILE" <<EOT
MTA_AI_WORKER_ENABLED=true
MTA_AI_WORKER_EXECUTABLE=$APP_DIR/app/ace_step_http_worker.py
MTA_ACE_STEP_URL=http://127.0.0.1:8001
MTA_ACE_MODEL_CACHE=/var/lib/mta/models/checkpoints
HF_HOME=/var/lib/mta/models/huggingface
EOT
  chmod 600 "$ENVFILE"
fi
chmod 755 "$APP_DIR/app/ace_step_http_worker.py"
SERVICE=/etc/systemd/system/mta-audio-editor.service
if [[ -f "$SERVICE" ]]; then cp -a "$SERVICE" "$SERVICE.backup.$(date -u +%Y%m%dT%H%M%SZ)"; fi
cat > "$SERVICE" <<EOT
[Unit]
Description=MTA Audio Editor web server
After=network-online.target mta-ace-step.service
Wants=network-online.target mta-ace-step.service
[Service]
User=$USER_NAME
Type=simple
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENVFILE
ExecStart=$PYTHON -m app.main
Restart=on-failure
RestartSec=10
NoNewPrivileges=true
[Install]
WantedBy=multi-user.target
EOT
systemctl daemon-reload
systemctl enable --now mta-audio-editor.service
systemctl status --no-pager mta-audio-editor.service
