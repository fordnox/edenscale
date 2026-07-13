#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Build the investor SPA and sync it into the native iOS project.
# Called by `make ios` and `make ios-archive`.
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "$HERE/.." && pwd)"
ROOT="$(cd "$IOS_DIR/../.." && pwd)"

# Load build-time env (VITE_*, IOS_*, CAP_SERVER_URL). Exported so both Vite and
# capacitor.config.ts (evaluated by the Capacitor CLI) can read them.
if [ -f "$IOS_DIR/.env" ]; then
  set -a; . "$IOS_DIR/.env"; set +a
else
  echo "⚠️  apps/ios/.env not found — using defaults. Copy .env.example to .env and set VITE_API_URL / VITE_HANKO_API_URL, or the app will point at localhost."
fi

case "${VITE_API_URL:-}" in
  ""|*localhost*|*127.0.0.1*)
    echo "⚠️  VITE_API_URL is '${VITE_API_URL:-unset}'. A device build cannot reach localhost — set a public https API URL in apps/ios/.env before shipping." ;;
esac

echo "▸ Installing workspace dependencies…"
( cd "$ROOT" && pnpm install )

echo "▸ Building the investor web bundle (base=/)…"
# base=/ overrides the investor app's production base of /investor/ so assets
# resolve at the Capacitor web root (capacitor://localhost/).
( cd "$ROOT/apps/investor" && pnpm exec vite build --base=/ )

echo "▸ Copying web assets → apps/ios/www…"
rm -rf "$IOS_DIR/www"
mkdir -p "$IOS_DIR/www"
cp -R "$ROOT/apps/investor/dist/." "$IOS_DIR/www/"

# Generate the native iOS project on first run (idempotent). Needs Xcode +
# CocoaPods — `make ios` checks for these first via `ios-check`.
if [ ! -d "$IOS_DIR/ios" ]; then
  echo "▸ Adding the native iOS platform (first run)…"
  ( cd "$IOS_DIR" && pnpm exec cap add ios )
fi

echo "▸ Syncing Capacitor (copy web + update native deps)…"
( cd "$IOS_DIR" && pnpm exec cap sync ios )

echo "✓ iOS project ready."
