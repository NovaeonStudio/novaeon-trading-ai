#!/bin/bash
# Uninstall NovaeonTradingAI (installed as <install dir>/bin/uninstall.sh).
#   uninstall.sh              stop and remove the services and the program; asks whether to delete your data too
#   uninstall.sh --keep-data  keep user_data/ (settings, trade history, login) and the downloaded model
#   uninstall.sh --all        delete everything, including trade history and the model (no question)
# The wallet's API-wallet key lives in the macOS Keychain or, on Linux, in an encrypted systemd user credential
# (~/.config/novaeon/credentials) and is never deleted automatically (see the end).
set -euo pipefail
H=$(cd "$(dirname "$0")/.." && pwd)
[ -f "$H/install.env" ] || H=${NOVAEON_HOME:-$HOME/NovaeonTradingAI}
[ -f "$H/install.env" ] || { echo "No NovaeonTradingAI install found ($H/install.env missing)." >&2; exit 1; }
# shellcheck disable=SC1091
. "$H/install.env"
[ "$NOVAEON_HOME" = "$H" ] || { echo "install.env belongs to $NOVAEON_HOME, not $H - refusing." >&2; exit 1; }
case "$H" in "$HOME"|"/"|"") echo "refusing to remove $H" >&2; exit 1 ;; esac
P=$NOVAEON_LABEL_PREFIX
OSN=${NOVAEON_OS:-Darwin}
LA=${NOVAEON_LAUNCH_AGENTS:-$HOME/Library/LaunchAgents}
UD=${NOVAEON_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}

MODE=ask
case "${1:-}" in --keep-data) MODE=keep ;; --all) MODE=all ;; "") ;; *) echo "unknown option $1" >&2; exit 2 ;; esac
if [ "$MODE" = ask ]; then
  MODE=keep
  if { exec 3</dev/tty; } 2>/dev/null; then
    printf 'Also delete your data (settings, trade history, login and the %s model)? [y/N] ' "${NOVAEON_MODEL_VARIANT:-AI}" >/dev/tty
    read -r ans <&3 || ans=""
    case "$ans" in [yY]*) MODE=all ;; esac
  fi
fi

echo "Stopping services..."
for n in control engine sentinel; do
  if [ "$OSN" = Darwin ]; then
    launchctl bootout "gui/$(id -u)/$P.$n" 2>/dev/null && echo "  stopped $P.$n" || true
    rm -f "$LA/$P.$n.plist"
  else
    u="$P-$n.service"
    [ -f "$UD/$u" ] || continue
    systemctl --user disable --now -q "$u" 2>/dev/null && echo "  stopped $u" || true
    systemctl --user reset-failed "$u" 2>/dev/null || true   # forget a non-zero exit on stop
    rm -f "$UD/$u"
  fi
done
[ "$OSN" = Darwin ] || systemctl --user daemon-reload 2>/dev/null || true

echo "Removing program files from $H ..."
rm -rf "${H:?}/.venv" "${H:?}/sentinel" "${H:?}/tools" "${H:?}/.cache" "${H:?}/src" "${H:?}/src.new" "${H:?}/ui" "${H:?}/ui.new" "${H:?}/bin" "${H:?}/logs"
if [ "$MODE" = all ]; then
  rm -rf "$H/user_data" "$H/models" "$H/login.txt" "$H/install.env"
  rmdir "$H" 2>/dev/null || echo "  (left $H: it contains files not created by the installer)"
  echo "NovaeonTradingAI removed completely."
else
  echo "NovaeonTradingAI removed. Kept your data in $H (user_data/, models/, login.txt)."
  echo "Installing again picks it up; delete the folder to remove it for good."
fi
if [ "$OSN" = Darwin ]; then
  if security find-generic-password -s novaeon-trading-agent >/dev/null 2>&1; then
    echo
    echo "Your Hyperliquid API-wallet key is still in the macOS Keychain (it can trade, never withdraw)."
    echo "Remove it in Keychain Access (search \"novaeon-trading-agent\") or revoke the API wallet on Hyperliquid."
  fi
elif ls "$HOME"/.config/novaeon/credentials/novaeon-trading-agent.*.cred >/dev/null 2>&1; then
  echo
  echo "Your Hyperliquid API-wallet key is still stored (encrypted) in ~/.config/novaeon/credentials (it can trade,"
  echo "never withdraw). Delete the novaeon-trading-agent.*.cred files there, or revoke the API wallet on Hyperliquid."
fi
