#!/bin/bash
# Apply NovaeonTradingAI's engine patch to the installed Freqtrade (idempotent; re-run after every engine upgrade).
# Path-independent version of bot/bin/ensure-engine-patches.sh: the install root is $NOVAEON_HOME or this script's
# parent directory. Restart the engine afterwards (bin/novaeon restart).
set -euo pipefail
ROOT=${NOVAEON_HOME:-$(cd "$(dirname "$0")/.." && pwd)}
M=""
for f in "$ROOT"/.venv/lib/python3*/site-packages/freqtrade/persistence/models.py; do [ -f "$f" ] && M=$f; done
[ -n "$M" ] || { echo "engine not found under $ROOT/.venv" >&2; exit 1; }
if grep -qE "(NovaeonTradingAI|NovaTradeUI) patch" "$M"; then echo "engine patch present"; exit 0; fi
cp "$M" "$M.bak-before-patch-$(date +%Y%m%d-%H%M%S)"
"$ROOT/.venv/bin/python" - "$M" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); s = p.read_text()
anchor = '''                "connect_args": {"check_same_thread": False},
            }
        )
'''
assert s.count(anchor) == 1, "anchor not found: engine code changed, patch manually"
s = s.replace(anchor, anchor + '''    # NovaeonTradingAI patch (2026-09-26): the API server runs up to 40 worker threads; the default
    # QueuePool (5 + 10 overflow, 30 s timeout) could be exhausted under concurrent UI load, which
    # also starved the trading loop and stopped the bot. Keep pool capacity above the thread count.
    if db_url.startswith("sqlite:///") and "poolclass" not in kwargs:
        kwargs.update({"pool_size": 20, "max_overflow": 40, "pool_timeout": 60})
''')
p.write_text(s)
PY
echo "engine patch applied"
