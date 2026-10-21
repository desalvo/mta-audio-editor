#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BUILD_ID="$(TZ=Europe/Rome date '+%Y%m%d%H%M%S')"
printf '%s\n' "$BUILD_ID" > BUILD_INFO
python scripts/build_docs.py
./scripts/production_gate.sh
find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +
rm -f .coverage coverage.xml
OUT="${1:-$ROOT/../mta-audio-editor-$(cat VERSION)-r$(cat REVISION).zip}"
python - "$ROOT" "$OUT" <<'PY'
import sys, zipfile, stat
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2]); base=root.name
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(root.rglob('*')):
        if p.is_file() and '.git' not in p.parts and p != out:
            arcname = Path(base)/p.relative_to(root)
            info = zipfile.ZipInfo.from_file(p, str(arcname))
            # Cumulative archives may have been unpacked by tools that discard Unix
            # execute bits. Restore them for executable entry-point scripts.
            mode = stat.S_IMODE(p.stat().st_mode)
            if p.parent == root / 'scripts' and p.suffix == '.sh' and p.read_bytes().startswith(b'#!'):
                mode |= 0o111
            info.external_attr = ((stat.S_IFREG | mode) << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            with p.open('rb') as source, z.open(info, 'w') as target:
                import shutil
                shutil.copyfileobj(source, target)
print(out)
PY
