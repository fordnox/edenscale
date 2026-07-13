#!/usr/bin/env bash
# Assemble App Store screenshot pages and render them to PNG.
# Output: NN-name-1242x2688.png (iPhone 6.5" display size).
set -euo pipefail
cd "$(dirname "$0")"

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p pages

for f in src/shots/*.html; do
  name=$(basename "$f" .html)
  cat src/prefix.html "$f" src/suffix.html > "pages/$name.html"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --window-size=414,896 --force-device-scale-factor=3 \
    --virtual-time-budget=8000 --default-background-color=00000000 \
    --screenshot="$PWD/$name-1242x2688.png" \
    "file://$PWD/pages/$name.html" 2>/dev/null
  echo "rendered $name"
done
