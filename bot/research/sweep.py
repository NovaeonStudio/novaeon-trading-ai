"""Backtest the live strategy on the two Binance periods from docs/STRATEGY.md and print one row per period.

Run it from your Freqtrade folder (the one with user_data/ and the downloaded data), with the strategy files
(Breakout.py, BreakoutRegime.py) in user_data/strategies/ and the configs described in docs/STRATEGY.md
("Reproducing the backtests"):

    python /path/to/novaeon-trading-ai/bot/research/sweep.py [--config config.json] \
        [--overlay binance-futures-20.json] [--strategy BreakoutRegime]

Results are written to research-results/<strategy>_<period>-*.zip and research-results.json in the current folder.
Numbers depend on the data you download (exchanges revise candles, and newer data extends the last period).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from freqtrade.data.btanalysis import load_backtest_stats

PERIODS = {"Y1": "20241101-20250924", "Y2": "20250924-20260925"}

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("--config", default="config.json")
ap.add_argument("--overlay", default="binance-futures-20.json")
ap.add_argument("--strategy", default="BreakoutRegime")
ap.add_argument("--userdir", default="user_data")
a = ap.parse_args()

out_dir = Path("research-results")
rows = {"strategy": a.strategy}
for label, timerange in PERIODS.items():
    subprocess.run([sys.executable, "-m", "freqtrade", "backtesting", "-c", a.config, "-c", a.overlay,
                    "--userdir", a.userdir, "-s", a.strategy, "--timerange", timerange,
                    "--max-open-trades", "8", "--dry-run-wallet", "2000", "--export", "trades",
                    "--backtest-directory", str(out_dir / f"{a.strategy}_{label}")], check=True)
    meta = sorted(out_dir.glob(f"{a.strategy}_{label}-*.meta.json"))[-1]
    s = load_backtest_stats(Path(str(meta).replace(".meta.json", ".zip")))["strategy"][a.strategy]
    rows[label] = dict(profit=round(s["profit_total"] * 100, 1), dd=round(s["max_drawdown_account"] * 100, 1),
                       trades=s["total_trades"], win=round(s["winrate"] * 100), pf=round(s.get("profit_factor") or 0, 2))
    r = rows[label]
    print(f"{a.strategy} {label} ({timerange}): return {r['profit']:+.1f}% | max drawdown {r['dd']:.1f}% | "
          f"profit factor {r['pf']:.2f} | win rate {r['win']}% | {r['trades']} trades", flush=True)
Path("research-results.json").write_text(json.dumps(rows, indent=1) + "\n")
