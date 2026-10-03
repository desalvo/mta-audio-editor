#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BUILD_ID="$(TZ=Europe/Rome date '+%Y%m%d-%H:%M:%S')"
printf '%s\n' "$BUILD_ID" > BUILD_INFO
python scripts/build_docs.py
./scripts/production_gate.sh
find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
rm -f .coverage coverage.xml
OUT="${1:-$ROOT/../mta-audio-editor-$(cat VERSION).zip}"
python - "$ROOT" "$OUT" <<'PY'
import sys, zipfile
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2]); base=root.name
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(root.rglob('*')):
        if p.is_file() and '.git' not in p.parts and p != out:
            z.write(p, Path(base)/p.relative_to(root))
print(out)
PY
