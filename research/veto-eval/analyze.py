"""Veto replay analysis: did the entries Sentinel would have blocked do worse than the ones it let through?
Run from the bot directory after run.sh:
    .venv/bin/python research/veto-eval/analyze.py > research/veto-eval/out/report.md"""
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "out"
DATA = ROOT / "user_data/data/binance/futures"
THRESH = 0.30
HORIZONS = {"24h": 24, "72h": 72, "7d": 168}
rng = np.random.default_rng(7)


def bt_result(tag: str) -> dict:
    z = sorted((OUT / f"bt-{tag}").glob("backtest-result-*.zip"))[-1]
    with zipfile.ZipFile(z) as f:
        name = next(n for n in f.namelist() if n.endswith(".json") and "_config" not in n and "meta" not in n)
        return json.loads(f.read(name))["strategy"]["BreakoutRegimeReplay"]


_candles: dict[str, pd.Series] = {}


def closes(pair: str) -> pd.Series:
    if pair not in _candles:
        f = DATA / (pair.replace("/", "_").replace(":", "_") + "-1h-futures.feather")
        d = pd.read_feather(f)
        _candles[pair] = d.set_index("date")["close"]
    return _candles[pair]


def boot_diff(a: np.ndarray, b: np.ndarray, n: int = 20000) -> tuple[float, float, float, float]:
    """mean(a) - mean(b), 95% bootstrap CI, and one-sided permutation p for 'a is worse than b'."""
    d = a.mean() - b.mean()
    bs = rng.choice(a, (n, len(a))).mean(1) - rng.choice(b, (n, len(b))).mean(1)
    pool = np.concatenate([a, b])
    perm = np.empty(n)
    for i in range(n):
        rng.shuffle(pool)
        perm[i] = pool[: len(a)].mean() - pool[len(a):].mean()
    return d, *np.percentile(bs, [2.5, 97.5]), float((perm <= d).mean())


def piles(tag: str) -> pd.DataFrame:
    trades = pd.DataFrame(bt_result(tag)["trades"])
    trades["open_date"] = pd.to_datetime(trades["open_date"], utc=True)
    dec = pd.DataFrame([json.loads(line) for line in open(OUT / f"decisions-{tag}.jsonl")])
    dec["time"] = pd.to_datetime(dec["time"], utc=True)
    dec = dec.drop_duplicates(["pair", "time"], keep="last")
    df = trades.merge(dec[["pair", "time", "headlines", "p_negative", "decision", "reason", "titles"]],
                      left_on=["pair", "open_date"], right_on=["pair", "time"], how="left")
    assert df["decision"].notna().all(), "trade without a logged decision"
    df["pile"] = np.where(df["decision"] == "veto", "vetoed",
                          np.where(df["headlines"] > 0, "allowed (news)", "allowed (no news)"))
    for h, n in HORIZONS.items():
        fwd = []
        for p, t, r in zip(df["pair"], df["open_date"], df["open_rate"]):
            c = closes(p)
            j = c.index.searchsorted(t + pd.Timedelta(hours=n - 1))   # close of the n-th candle after entry
            fwd.append(c.iloc[j] / r - 1 if j < len(c) and c.index[j] == t + pd.Timedelta(hours=n - 1) else np.nan)
        df[f"fwd_{h}"] = fwd
    return df


def pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


def pile_table(df: pd.DataFrame) -> str:
    rows = ["| Pile | Entries | Trade return (mean) | median | win rate | fwd 24h | fwd 72h | fwd 7d |",
            "|---|---|---|---|---|---|---|---|"]
    order = ["vetoed", "allowed (news)", "allowed (no news)"]
    for name in order + ["all not vetoed"]:
        g = df[df["pile"] != "vetoed"] if name == "all not vetoed" else df[df["pile"] == name]
        if g.empty:
            continue
        rows.append(f"| {name} | {len(g)} | {pct(g.profit_ratio.mean())} | {pct(g.profit_ratio.median())} | "
                    f"{(g.profit_ratio > 0).mean() * 100:.0f}% | "
                    + " | ".join(pct(g[f'fwd_{h}'].mean()) for h in HORIZONS) + " |")
    return "\n".join(rows)


def test_lines(df: pd.DataFrame) -> str:
    v = df[df.pile == "vetoed"]
    if len(v) < 2:
        return f"Only {len(v)} vetoed entries: no test possible."
    out = []
    for other_name, other in [("allowed (news)", df[df.pile == "allowed (news)"]),
                              ("all not vetoed", df[df.pile != "vetoed"])]:
        for col, label in [("profit_ratio", "trade return"), ("fwd_72h", "fwd 72h")]:
            a, b = v[col].dropna().to_numpy(), other[col].dropna().to_numpy()
            d, lo, hi, p = boot_diff(a, b)
            out.append(f"- vetoed − {other_name}, {label}: **{pct(d)}** (95% CI {pct(lo)} … {pct(hi)}; "
                       f"one-sided permutation p = {p:.3f})")
    return "\n".join(out)


def portfolio(tag: str) -> dict:
    s = bt_result(tag)
    t = pd.DataFrame(s["trades"])
    return {"tag": tag, "trades": s["total_trades"], "return": s["profit_total"],
            "max_dd": s.get("max_drawdown_account", s.get("max_relative_drawdown")),
            "pf": s.get("profit_factor"), "win": (t.profit_ratio > 0).mean() if len(t) else float("nan")}


def main() -> None:
    print("# Sentinel veto replay\n")
    print(f"Binance USDT futures, 20 coins, 1x, fees and funding included, veto at P(major negative) ≥ {THRESH}.\n")
    for tag, label in [("record-safe-all", "Main: safe timestamps, all archive sources"),
                       ("record-raw-all", "Sensitivity: raw timestamps (can leak up to a day of future news)"),
                       ("record-safe-press", "Sensitivity: only the four outlets the live bot reads")]:
        if not (OUT / f"decisions-{tag}.jsonl").exists():
            continue
        df = piles(tag)
        print(f"## {label} (`{tag}`)\n")
        print(f"{df.open_date.min():%Y-%m-%d} to {df.open_date.max():%Y-%m-%d}: {len(df)} entries the bot wanted, "
              f"{(df.headlines > 0).sum()} with headlines, {(df.pile == 'vetoed').sum()} vetoed.\n")
        print(pile_table(df) + "\n")
        print(test_lines(df) + "\n")
        v = df[df.pile == "vetoed"].sort_values("open_date")
        if len(v):
            print("| Vetoed entry | P(neg) | Trade return | fwd 72h | Newest headline |\n|---|---|---|---|---|")
            for _, r in v.iterrows():
                title = (r.titles or [""])[0].replace("|", "/")[:90]
                print(f"| {r.open_date:%Y-%m-%d %H:%M} {r.pair.split('/')[0]} | {r.p_negative:.2f} | "
                      f"{pct(r.profit_ratio)} | {pct(r.fwd_72h) if pd.notna(r.fwd_72h) else 'n/a'} | {title} |")
            print()
        df.drop(columns=["titles"]).to_csv(OUT / f"piles-{tag}.csv", index=False)
    print("## Portfolio (8 slots, 2,000 USDT, compounding)\n")
    print("| Run | Trades | Return | Max drawdown | Profit factor | Win rate |\n|---|---|---|---|---|---|")
    for tag in ["off-8", "veto-8-safe-all", "veto-8-raw-all"]:
        if (OUT / f"bt-{tag}").exists():
            p = portfolio(tag)
            print(f"| {tag} | {p['trades']} | {pct(p['return'])} | {p['max_dd'] * 100:.1f}% | {p['pf']:.2f} | "
                  f"{p['win'] * 100:.0f}% |")


if __name__ == "__main__":
    main()
