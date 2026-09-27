#!/usr/bin/env bash
# Assemble the Hugging Face Space folder (default: ./space) from this repository.
# Then:  cd space && git init && git remote add origin https://huggingface.co/spaces/<user>/<space>
#        git add . && git commit -m "demo" && git push -u origin main
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/space}"
if [ -e "$OUT" ]; then
  echo "Refusing to overwrite existing path: $OUT" >&2
  echo "Remove it explicitly or pass a new output directory." >&2
  exit 1
fi
mkdir -p "$OUT/weights"
cp "$ROOT/demo/app.py" "$ROOT/demo/requirements.txt" "$ROOT/demo/packages.txt" "$ROOT/demo/README.md" "$OUT/"
cp "$ROOT/LICENSE" "$OUT/"
cp -r "$ROOT/src" "$ROOT/configs" "$OUT/"
cp "$ROOT/weights/yolo11n.pt" "$OUT/weights/"
find "$OUT" -name "__pycache__" -type d -prune -exec rm -rf {} +
echo "Space ready in $OUT"
