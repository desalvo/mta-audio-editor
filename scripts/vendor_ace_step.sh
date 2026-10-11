#!/usr/bin/env bash
# Build-time only: vendor reviewed upstream ACE-Step code, not model weights.
set -euo pipefail
if [[ $# -ne 1 || ! "$1" =~ ^[a-fA-F0-9]{40}$ ]]; then
  echo "Usage: $0 <audited-40-character-upstream-commit>" >&2; exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/third_party/ace-step-1.5"
if [[ -e "$DEST" ]]; then echo "Destination already exists: $DEST" >&2; exit 3; fi
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
# Network access is expected only in a trusted release-build environment.
git clone --no-checkout https://github.com/ace-step/ACE-Step-1.5.git "$TMP/source"
git -C "$TMP/source" checkout --detach "$1"
[[ "$(git -C "$TMP/source" rev-parse HEAD)" == "$1" ]] || exit 4
[[ -s "$TMP/source/LICENSE" ]] || { echo "Missing upstream license" >&2; exit 5; }
mkdir -p "$(dirname "$DEST")"
rsync -a --exclude='.git' --exclude='checkpoints' --exclude='*.safetensors' --exclude='*.ckpt' --exclude='*.pt' "$TMP/source/" "$DEST/"
printf '%s\n' "$1" > "$DEST/UPSTREAM_COMMIT"
echo "Vendored code only. Audit licenses and dependencies before distribution."
