#!/usr/bin/env bash
set -Eeuo pipefail
python -m compileall -q app
if command -v ffmpeg >/dev/null 2>&1; then PYTHONPATH=. python scripts/validate_audio_presets.py; fi
ruff check app tests
bandit -q -r app -lll -iii
PYTHONPATH=. pytest --cov=app --cov-report=term-missing --cov-fail-under=70
if command -v node >/dev/null 2>&1; then node --check app/static/app.js; fi
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -r requirements.txt --strict
  sed '/^--extra-index-url /d; s/^torch==\(.*\)+cpu$/torch==\1/' requirements-stems.txt > /tmp/mta-stems-audit.txt
  pip-audit -r /tmp/mta-stems-audit.txt --strict
fi
printf 'Production gates passed.\n'
