#!/bin/bash
# Build the release assets the installer downloads, into installer/build/:
#   novaeon-ui.tar.gz (+ .sha256)   the built web app (contents of dist/); install.sh fetches it from the GitHub release
#   NovaeonTradingAI-<version>.dmg  the double-click installer app (build-dmg.sh)
# Upload both to a GitHub release of NovaeonStudio/novaeon-trading-ai (tag v<version>, marked "latest").
#   installer/build-release.sh [--skip-ui-build]    (--skip-ui-build: package the existing dist/ as is)
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
BUILD="$REPO/installer/build"
mkdir -p "$BUILD"
cd "$REPO"
if [ "${1:-}" != "--skip-ui-build" ]; then npx -y pnpm@11 install --frozen-lockfile && npx -y pnpm@11 run build; fi
[ -f dist/index.html ] || { echo "dist/ missing: build the web app first" >&2; exit 1; }
COPYFILE_DISABLE=1 tar -C dist --exclude "*.map" -czf "$BUILD/novaeon-ui.tar.gz" .   # no source maps: they embed build paths
(cd "$BUILD" && shasum -a 256 novaeon-ui.tar.gz > novaeon-ui.tar.gz.sha256)
echo "built $BUILD/novaeon-ui.tar.gz ($(du -h "$BUILD/novaeon-ui.tar.gz" | cut -f1))"
"$REPO/installer/build-dmg.sh"
