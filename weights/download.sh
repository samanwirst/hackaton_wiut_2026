#!/usr/bin/env bash
# The weights are committed in this folder, so evaluation needs no download. This script only
# restores them (e.g. after cloning without the files) and verifies their SHA-256 checksums.
# Works with the bash 3.2 that ships with macOS as well as on Linux.
set -euo pipefail
cd "$(dirname "$0")"
BASE="https://github.com/ultralytics/assets/releases/download/v8.3.0"
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1; }
while read -r file sum; do
  [ -f "$file" ] || curl -fL --retry 3 -o "$file" "$BASE/$file"
  if [ "$(sha256 "$file")" != "$sum" ]; then echo "checksum mismatch: $file" >&2; exit 1; fi
  echo "$file OK"
done <<'LIST'
yolo11n.pt 0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1
yolo11s.pt 85a76fe86dd8afe384648546b56a7a78580c7cb7b404fc595f97969322d502d5
yolo11m.pt d5ffc1a674953a08e11a8d21e022781b1b23a19b730afc309290bd9fb5305b95
LIST
