#!/bin/bash
# Build NovaeonTradingAI.dmg: a small unsigned app (AppleScript applet + launch.sh + install.sh) and an Applications
# link. Only macOS built-ins are used (osacompile, sips, iconutil, codesign ad-hoc, hdiutil). No paid tools.
#   installer/build-dmg.sh [output.dmg]      (default installer/build/NovaeonTradingAI-<version>.dmg)
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(sed -n 's/^ *"version": *"\([^"]*\)".*/\1/p' "$REPO/package.json" | head -1)
BUILD="$REPO/installer/build"
OUT=${1:-$BUILD/NovaeonTradingAI-$VERSION.dmg}
STAGE="$BUILD/dmg"
APP="$STAGE/NovaeonTradingAI.app"
rm -rf "$STAGE"; mkdir -p "$STAGE" "$(dirname "$OUT")"

osacompile -o "$APP" "$REPO/installer/app/main.applescript"
R="$APP/Contents/Resources"
cp "$REPO/installer/app/launch.sh" "$REPO/install.sh" "$R/"
chmod +x "$R/launch.sh" "$R/install.sh"

# Brand icon: public/icon-512.png -> applet.icns (the icon file osacompile's applets use)
ICON_SRC="$REPO/public/icon-512.png"
if [ -f "$ICON_SRC" ]; then
  ICONSET="$BUILD/applet.iconset"; rm -rf "$ICONSET"; mkdir -p "$ICONSET"
  for s in 16 32 128 256; do
    sips -z $s $s "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    sips -z $((s * 2)) $((s * 2)) "$ICON_SRC" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
  done
  sips -z 512 512 "$ICON_SRC" --out "$ICONSET/icon_512x512.png" >/dev/null
  iconutil -c icns "$ICONSET" -o "$R/applet.icns"
  rm -rf "$ICONSET"
  # newer osacompile also ships the default icon in Assets.car (CFBundleIconName), which would win over applet.icns
  rm -f "$R/Assets.car"
  plutil -remove CFBundleIconName "$APP/Contents/Info.plist" 2>/dev/null || true
fi

PL="$APP/Contents/Info.plist"
plutil -replace CFBundleIdentifier -string "studio.novaeon.trading.app" "$PL"
plutil -replace CFBundleName -string "NovaeonTradingAI" "$PL"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PL"
plutil -replace CFBundleVersion -string "$VERSION" "$PL"
plutil -replace LSMinimumSystemVersion -string "14.0" "$PL"
plutil -replace LSArchitecturePriority -json '["arm64"]' "$PL"
plutil -remove LSMinimumSystemVersionByArchitecture "$PL" 2>/dev/null || true
plutil -replace NSHumanReadableCopyright -string "Copyright Novaeon Studio. GPL-3.0." "$PL"
# Resources changed after osacompile: re-seal with an ad-hoc signature (no Apple Developer ID; users approve it once).
codesign --force --deep --sign - "$APP" 2>/dev/null
codesign --verify --deep --strict "$APP"

ln -s /Applications "$STAGE/Applications"
cat > "$STAGE/READ ME FIRST.txt" <<'EOF'
NovaeonTradingAI - install

1. Drag NovaeonTradingAI into Applications.
2. Open it the first time like this (the app is free and not signed with a paid Apple certificate):
   macOS 14 (Sonoma):  right-click (or Control-click) NovaeonTradingAI -> Open -> Open.
   macOS 15 and newer: double-click it, click "Done" in the warning, then open
                       System Settings -> Privacy & Security, scroll down, click "Open Anyway" and confirm.
   You only need to do this once.
3. A Terminal window opens and installs everything (about 10-30 minutes, mostly the AI model download).
   At the end your browser opens the app and the Terminal shows your login password.

Later, opening NovaeonTradingAI starts the bot if needed and opens the app in your browser.

Prefer the command line? This is the same installer:
  curl -fsSL https://raw.githubusercontent.com/NovaeonStudio/novaeon-trading-ai/main/install.sh | bash

Needs: Apple Silicon Mac (M1 or newer), macOS 14+, 8 GB memory (16 GB recommended), 12 GB free disk.
Starts with practice money. Uninstall: ~/NovaeonTradingAI/bin/novaeon uninstall
EOF

rm -f "$OUT"
hdiutil create -quiet -volname "NovaeonTradingAI" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$OUT"
hdiutil verify -quiet "$OUT"
shasum -a 256 "$OUT" | awk '{print $1}' > "$OUT.sha256"
echo "built $OUT ($(du -h "$OUT" | cut -f1), sha256 $(cut -c1-12 < "$OUT.sha256")...)"
