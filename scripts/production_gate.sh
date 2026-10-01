#!/usr/bin/env bash
set -Eeuo pipefail
python -m compileall -q app
if command -v ffmpeg >/dev/null 2>&1; then PYTHONPATH=. python scripts/validate_audio_presets.py; fi
ruff check app tests
bandit -q -r app -lll -iii
PYTHONPATH=. pytest --cov=app --cov-report=term-missing --cov-fail-under=70
if command -v node >/dev/null 2>&1; then node --check app/static/app.js; fi
if command -v pip-audit >/dev/null 2>&1; then pip-audit -r requirements.txt -r requirements-stems.txt --strict; fi
printf 'Production gates passed.\n'
