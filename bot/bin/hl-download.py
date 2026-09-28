#!/usr/bin/env python3
"""Fetch Hyperliquid perp candles + hourly funding via the public info API and store them as Freqtrade data
(Freqtrade itself can't download Hyperliquid history). API returns at most ~5000 candles per timeframe."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd
from freqtrade.data.history.datahandlers import get_datahandler
from freqtrade.enums import CandleType

API = "https://api.hyperliquid.xyz/info"
# Freqtrade data folder: $NOVAEON_HOME/user_data/... in an install, else ./user_data/... (run it from your Freqtrade folder)
DATADIR = Path(os.environ.get("NOVAEON_HOME", ".")) / "user_data/data/hyperliquid"
COINS = sys.argv[1:] or ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK"]
TF_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def post(body):
    # The live bot shares this IP with Hyperliquid's rate limit (1200 weight/min): stay slow on purpose.
    time.sleep(1.5)
    for attempt in range(5):
        try:
            req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                         headers={"content-type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception:  # noqa: BLE001
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"API failed: {body}")


def candles(coin, tf):
    end = int(time.time() * 1000)
    start = end - 5000 * TF_MS[tf]
    rows = post({"type": "candleSnapshot", "req": {"coin": coin, "interval": tf, "startTime": start, "endTime": end}})
    df = pd.DataFrame([{"date": pd.to_datetime(r["t"], unit="ms", utc=True), "open": float(r["o"]),
                        "high": float(r["h"]), "low": float(r["l"]), "close": float(r["c"]),
                        "volume": float(r["v"])} for r in rows])
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def funding(coin, start_ms):
    out, cur = [], start_ms
    while True:
        rows = post({"type": "fundingHistory", "coin": coin, "startTime": cur})
        if not rows:
            break
        out += rows
        nxt = rows[-1]["time"] + 1
        if nxt <= cur or len(rows) < 500:
            break
        cur = nxt
    df = pd.DataFrame([{"date": pd.to_datetime(r["time"], unit="ms", utc=True).floor("h"),
                        "funding_rate": float(r["fundingRate"])} for r in out])
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


dh = get_datahandler(DATADIR, "feather")
for coin in COINS:
    pair = f"{coin}/USDC:USDC"
    first = None
    for tf in ("1d", "4h", "1h"):
        df = candles(coin, tf)
        dh.ohlcv_store(pair, tf, df, CandleType.FUTURES)
        first = df["date"].iloc[0] if first is None else first
        print(f"{pair:16} {tf:3} {len(df):5} candles  {df['date'].iloc[0]:%Y-%m-%d} → {df['date'].iloc[-1]:%Y-%m-%d}")
    fr = funding(coin, int(first.timestamp() * 1000))
    dh.ohlcv_store(pair, "1h", fr, CandleType.FUNDING_RATE)
    print(f"{pair:16} funding {len(fr)} hours, avg {fr['funding_rate'].mean() * 100:.4f}%/h")
