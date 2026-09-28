#!/bin/bash
# Logic of the NovaeonTradingAI.app (the AppleScript applet only calls this script).
#   installed  -> make sure the services run and open the app in the browser
#   otherwise  -> open Terminal with the installer (the same install.sh as the one-line command, shipped in the app)
set -euo pipefail
H=${NOVAEON_HOME:-$HOME/NovaeonTradingAI}
RES=$(cd "$(dirname "$0")" && pwd)

if [ -f "$H/install.env" ] && [ -x "$H/bin/novaeon" ]; then
  port=$(sed -n 's/^NOVAEON_ENGINE_PORT=//p' "$H/install.env"); port=${port:-8081}
  url="http://127.0.0.1:$port"
  [ "${NOVAEON_APP_DRY_RUN:-0}" = 1 ] && { echo "installed at $H: start services if needed, then open $url"; exit 0; }
  if ! curl -fs -m 2 -o /dev/null "$url/api/v1/ping"; then
    "$H/bin/novaeon" start >/dev/null 2>&1 || true
    for _ in $(seq 1 45); do curl -fs -m 2 -o /dev/null "$url/api/v1/ping" && break; sleep 2; done
  fi
  open "$url"
  exit 0
fi

# Not installed yet: copy the installer out of the (read-only, possibly quarantined) app bundle and run it in Terminal.
dir="$HOME/Library/Caches/studio.novaeon.trading"
mkdir -p "$dir"
cat "$RES/install.sh" > "$dir/install.sh"
cmd="$dir/Install NovaeonTradingAI.command"
cat > "$cmd" <<EOF
#!/bin/bash
clear
/bin/bash "$dir/install.sh"
status=\$?
echo
if [ \$status -eq 0 ]; then echo "Done. You can close this window."; else echo "The install stopped (see above). Run it again to resume."; fi
EOF
chmod +x "$cmd" "$dir/install.sh"
[ "${NOVAEON_APP_DRY_RUN:-0}" = 1 ] && { echo "open -a Terminal $cmd"; exit 0; }
open -a Terminal "$cmd"
