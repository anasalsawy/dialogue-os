#!/usr/bin/env bash
set -Eeuo pipefail

BASE="https://raw.githubusercontent.com/anasalsawy/dialogue-os/354f7fc53242c953bc841aa6b940bf9d5fd4efe2/yta-runtime-fix/chunks"
EXPECTED="e7064ddcc7065eecab4b992d2f9fadd41699a5a2d464fcf81a77be0ac27821c9"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

: > "$TMP/payload.b64"
for n in 00 01 02 03 04 05 06 07; do
  curl --fail --silent --show-error --location \
    "$BASE/chunk-$n.b64" >> "$TMP/payload.b64"
done

base64 --decode "$TMP/payload.b64" | gzip --decompress > "$TMP/install.sh"
ACTUAL="$(sha256sum "$TMP/install.sh" | awk '{print $1}')"

if [[ "$ACTUAL" != "$EXPECTED" ]]; then
  echo "Installer checksum mismatch. Nothing was changed." >&2
  exit 1
fi

chmod +x "$TMP/install.sh"
exec "$TMP/install.sh"
