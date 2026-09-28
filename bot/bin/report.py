#!/usr/bin/env python3
"""Status report for the single paper bot (engine API on :8081) + Sentinel news-veto log."""
import base64
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(os.environ.get("NOVAEON_HOME", Path(__file__).resolve().parents[1]))   # install folder
_LOGIN = (ROOT / "login.txt").read_text()  # "user: <name>" and "password: <pw>" lines
USER = re.search(r"user: (\S+)", _LOGIN).group(1)
PW = re.search(r"password: (\S+)", _LOGIN).group(1)
AUTH = "Basic " + base64.b64encode(f"{USER}:{PW}".encode()).decode()


def api(path):
    req = urllib.request.Request(f"http://127.0.0.1:{os.environ.get('NOVAEON_ENGINE_PORT', '8081')}/api/v1/{path}", headers={"Authorization": AUTH})
    # /balance can take half a minute when the engine refreshes all exchange prices: wait longer and retry once.
    for attempt in (1, 2):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except TimeoutError:
            if attempt == 2:
                raise


try:
    cfg, p, b, s = api("show_config"), api("profit"), api("balance"), api("status")
except Exception as e:  # noqa: BLE001
    raise SystemExit(f"BOT DOWN ({e.__class__.__name__}): see logs/engine.log in the install folder")
def _start():
    """Practice money as set in the app (user_data/practice.json), else the engine's figures."""
    try:
        return json.loads((ROOT / "user_data/practice.json").read_text())["dry_run_wallet"]
    except Exception:  # noqa: BLE001
        return b.get("starting_capital") or cfg.get("dry_run_wallet") or "?"


mode = "PAPER (simulated)" if cfg["dry_run"] else "LIVE — REAL MONEY"
print(f"Bot: {cfg['exchange']} / {cfg['trading_mode']} / {cfg['stake_currency']} / {cfg['strategy']} / {mode}")
print(f"Wallet:          {b['total']:.2f} {cfg['stake_currency']} (start {_start()})")
print(f"Total P&L:       {p['profit_all_percent']:+.2f}% (incl. open trades)")
print(f"Closed trades:   {p['closed_trade_count']}  (wins {p['winning_trades']} / losses {p['losing_trades']}), "
      f"closed P&L {p['profit_closed_percent']:+.2f}%")
print(f"Max drawdown:    {p.get('max_drawdown', 0) * 100:.1f}%")
print(f"Open trades:     {len(s)}")
for t in s:
    print(f"  {t['pair']:16} {t.get('leverage', 1):.0f}x  since {t['open_date'][:16]}  {t['profit_pct']:+.2f}%")

# Did Sentinel's higher-leverage picks do better? Closed trades grouped by leverage.
closed = [t for t in api("trades?limit=500")["trades"] if not t["is_open"]]
if closed:
    print("\nClosed trades by leverage (Sentinel's pick, or manual):")
    for lev in sorted({t.get("leverage", 1) for t in closed}):
        g = [t for t in closed if t.get("leverage", 1) == lev]
        wins = sum(1 for t in g if t["profit_abs"] > 0)
        print(f"  {lev:.0f}x: {len(g)} trades, {wins} wins, avg {sum(t['profit_pct'] for t in g) / len(g):+.2f}%, "
              f"total {sum(t['profit_abs'] for t in g):+.2f}")

log = ROOT / "user_data/kev_decisions.jsonl"
recs = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
c = Counter(r["decision"] for r in recs)
print(f"\nSentinel: {len(recs)} entry checks, {c['allow']} allowed, {c['veto']} vetoed, "
      f"{sum(1 for r in recs if 'kev_unavailable' in r.get('reason', ''))} while Sentinel was down")
for r in recs:
    if r["decision"] == "veto":
        print(f"  VETO {r['time'][:16]} {r['pair']} p={r['p_negative']:.2f}  {r['titles'][:2]}")
