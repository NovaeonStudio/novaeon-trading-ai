#!/bin/bash
# Veto replay backtests (run from the bot directory on the bot host, Sentinel reachable at NOVAEON_SENTINEL_URL).
#   record-*: every entry the bot wanted (no slot limit, fixed stake), Sentinel's verdict logged, nothing blocked
#   off-8 / veto-8: the real portfolio (8 slots, 2000 USDT, compounding), without and with the veto
# Usage: bash research/veto-eval/run.sh [timerange]   (default 20251001-20260924: the period the archive covers)
set -eu
cd "$(dirname "$0")/../.."
TR="${1:-20251001-20260924}"
D=research/veto-eval/out
mkdir -p "$D"
bt() {   # tag, extra freqtrade args...
  local tag=$1; shift
  rm -rf "$D/bt-$tag"; mkdir -p "$D/bt-$tag"
  REPLAY_TAG="$tag" .venv/bin/freqtrade backtesting -c user_data/config.json -c research/binfut20.json \
    --userdir user_data --strategy-path research/veto-eval/strategies -s BreakoutRegimeReplay \
    --timerange "$TR" --export trades --backtest-directory "$D/bt-$tag" --cache none "$@" > "$D/bt-$tag.log" 2>&1
  echo "$(date -u +%FT%TZ) done $tag"
}
rm -f "$D"/decisions-*.jsonl
ALL=(--max-open-trades -1 --stake-amount 100 --dry-run-wallet 100000000)
REPLAY_MODE=record REPLAY_TIMING=safe REPLAY_SOURCES=all   bt record-safe-all   "${ALL[@]}"
REPLAY_MODE=record REPLAY_TIMING=raw  REPLAY_SOURCES=all   bt record-raw-all    "${ALL[@]}"
REPLAY_MODE=record REPLAY_TIMING=safe REPLAY_SOURCES=press bt record-safe-press "${ALL[@]}"
PORT=(--max-open-trades 8 --dry-run-wallet 2000)
REPLAY_MODE=off                                            bt off-8             "${PORT[@]}"
REPLAY_MODE=veto   REPLAY_TIMING=safe REPLAY_SOURCES=all   bt veto-8-safe-all   "${PORT[@]}"
REPLAY_MODE=veto   REPLAY_TIMING=raw  REPLAY_SOURCES=all   bt veto-8-raw-all    "${PORT[@]}"
echo "$(date -u +%FT%TZ) ALL DONE"
