#!/usr/bin/env bash
set -euo pipefail
DEST="${1:-native/runtime/chordino}"
ROOT="$(pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST/bin" "$DEST/vamp"

HOST="$(command -v vamp-simple-host || true)"
if [[ -z "$HOST" ]]; then
  echo "vamp-simple-host not found; install vamp-plugin-sdk/vamp-examples first" >&2
  exit 2
fi
cp "$HOST" "$DEST/bin/"

curl -fsSL "https://github.com/c4dm/nnls-chroma/archive/refs/heads/master.tar.gz" -o "$TMP/nnls.tar.gz"
tar -xzf "$TMP/nnls.tar.gz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'nnls-chroma-*' | head -1)"
if [[ -z "$SRC" ]]; then echo "NNLS-Chroma source not found" >&2; exit 3; fi

VAMP_SDK_DIR="${VAMP_SDK_DIR:-/usr/include/vamp-sdk}"
if [[ "$(uname -s)" == "Darwin" ]]; then
  BREW_PREFIX="$(brew --prefix vamp-plugin-sdk)"
  VAMP_SDK_DIR="${VAMP_SDK_DIR_MAC:-$BREW_PREFIX/include/vamp-sdk}"
  make -C "$SRC" -f Makefile.osx VAMP_SDK_DIR="$VAMP_SDK_DIR"
  cp "$SRC/nnls-chroma.dylib" "$DEST/vamp/"
else
  make -C "$SRC" -f Makefile.linux VAMP_SDK_DIR="$VAMP_SDK_DIR"
  cp "$SRC/nnls-chroma.so" "$DEST/vamp/"
fi
for f in nnls-chroma.cat nnls-chroma.n3 COPYING CITATION README; do
  [[ -f "$SRC/$f" ]] && cp "$SRC/$f" "$DEST/vamp/"
done
VAMP_PATH="$ROOT/$DEST/vamp" "$ROOT/$DEST/bin/vamp-simple-host" --list-ids | grep -q 'nnls-chroma:chordino'
echo "Chordino runtime ready in $DEST"
