#!/bin/bash
# Starts the trading engine in the mode stored in user_data/mode.json ("paper" = practice, "live" = real money).
# Used by launchd (studio.novaeon.trading.engine, written by the installer). The mode is switched by bin/control.py.
# Live: dry_run off via user_data/live.json; the API-wallet key comes from the macOS Keychain or, on Linux, from an
# encrypted systemd user credential - never from a plain file.
set -euo pipefail
cd "${NOVAEON_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR=${NOVAEON_LOG_DIR:-$PWD/logs}; mkdir -p "$LOG_DIR"
PY=/usr/bin/python3
MODE=$($PY -c 'import json;print(json.load(open("user_data/mode.json")).get("mode","paper"))' 2>/dev/null || echo paper)
ARGS=(trade -c user_data/config.json -c user_data/exchange-hyperliquid.json -c user_data/bot.json
      --userdir user_data --logfile "${NOVAEON_LOG_FILE:-$LOG_DIR/engine.log}")
# Novaeon settings (AI leverage on/off, set in the app via bin/control.py): an extra top-level "novaeon" block, both modes.
if [ -f user_data/novaeon.json ]; then ARGS+=(-c user_data/novaeon.json); fi
if [ "$MODE" = "live" ]; then
  ADDR=$($PY -c 'import json;print(json.load(open("user_data/live.json"))["exchange"]["walletAddress"])')
  if [ "$(uname)" = Darwin ]; then
    KEY=$(security find-generic-password -s novaeon-trading-agent -a "$ADDR" -w 2>/dev/null) || KEY=""
  else   # Linux: encrypted systemd user credential written by bin/control.py
    NAME="novaeon-trading-agent.$(printf %s "$ADDR" | tr A-F a-f)"
    KEY=$(systemd-creds --user decrypt --name="$NAME" "$HOME/.config/novaeon/credentials/$NAME.cred" - 2>/dev/null) || KEY=""
  fi
  if [ -z "$KEY" ]; then
    echo "$(date) live mode but no API-wallet key in the key store for $ADDR - refusing to start" >&2
    exit 1   # never fall back to practice silently
  fi
  export FREQTRADE__EXCHANGE__PRIVATE_KEY="$KEY"
  exec .venv/bin/freqtrade "${ARGS[@]}" -c user_data/live.json --db-url sqlite:///user_data/live-hyperliquid.sqlite
fi
# Practice money (set on the Wallet page via bin/control.py): practice.json overrides config.json's dry_run_wallet and
# the ledger names the database of the current practice run ("start over" switches to a fresh one, the old one stays).
DB=$($PY -c 'import json;print(json.load(open("user_data/practice-ledger.json")).get("db","paper-hyperliquid.sqlite"))' 2>/dev/null || echo paper-hyperliquid.sqlite)
if [ -f user_data/practice.json ]; then ARGS+=(-c user_data/practice.json); fi
exec .venv/bin/freqtrade "${ARGS[@]}" --db-url "sqlite:///user_data/$DB"
