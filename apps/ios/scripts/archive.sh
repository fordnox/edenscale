#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Archive and export a signed, App Store-ready IPA using your Apple Developer
# team (automatic signing). Requires full Xcode. Run via `make ios-archive`,
# which runs prepare.sh first so the web bundle and native project are current.
# ---------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$(cd "$HERE/.." && pwd)"

if [ -f "$IOS_DIR/.env" ]; then
  set -a; . "$IOS_DIR/.env"; set +a
fi

: "${APPLE_TEAM_ID:?Set APPLE_TEAM_ID in apps/ios/.env (Developer portal ▸ Membership)}"

APP_DIR="$IOS_DIR/ios/App"
WORKSPACE="$APP_DIR/App.xcworkspace"
BUILD="$IOS_DIR/build"
ARCHIVE="$BUILD/App.xcarchive"

[ -d "$WORKSPACE" ] || { echo "🚨 $WORKSPACE not found — run 'make ios' once first to generate the native project."; exit 1; }

mkdir -p "$BUILD"
sed "s/__TEAM_ID__/$APPLE_TEAM_ID/" "$IOS_DIR/ExportOptions.plist.template" > "$BUILD/ExportOptions.plist"

echo "▸ Archiving (Release, team $APPLE_TEAM_ID)…"
xcodebuild \
  -workspace "$WORKSPACE" \
  -scheme App \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE" \
  DEVELOPMENT_TEAM="$APPLE_TEAM_ID" \
  -allowProvisioningUpdates \
  archive

echo "▸ Exporting signed IPA…"
xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportOptionsPlist "$BUILD/ExportOptions.plist" \
  -exportPath "$BUILD/ipa" \
  -allowProvisioningUpdates

echo ""
echo "✓ Signed IPA → apps/ios/build/ipa/"
echo "  Submit it to App Store Connect with either:"
echo "    • Transporter.app — drag in the .ipa, then Deliver"
echo "    • xcrun altool --upload-app -f apps/ios/build/ipa/App.ipa -t ios \\"
echo "        -u <apple-id> -p <app-specific-password>"
