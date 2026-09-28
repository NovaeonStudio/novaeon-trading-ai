# News check replay

What did Sentinel's veto do to the bot? This replays the news check over a year of backtest entries: the bot's own
`BreakoutRegimeKev` code path (same coin filter, same Sentinel request, same 0.30 threshold, 1×), with the live news
feeds swapped for an archive of timestamped headlines. Results and discussion:
[docs/STRATEGY.md → The news check in a replay](../../docs/STRATEGY.md#the-news-check-in-a-replay); full numbers in
[`results/report-2026-09-28.md`](results/report-2026-09-28.md) (per-entry tables in `results/piles-*.csv`).

## Files

- `strategies/BreakoutRegimeReplay.py`: subclass of `BreakoutRegimeKev` that reads headlines from the archive at the
  candle time. Modes via environment: `REPLAY_MODE` (`off` / `record` / `veto`), `REPLAY_TIMING` (`safe`: date-only
  timestamps count 24 h later; `raw`), `REPLAY_SOURCES` (`all` / `press`), `REPLAY_SELECT` (`newest` / `live`).
- `run.sh`: three `record` runs (every entry the strategy wanted, no slot limit, verdict logged, nothing blocked) and
  three portfolio runs (8 slots, 2,000 USDT: without the news check, with it, with raw timestamps).
- `analyze.py`: joins trades with decisions, adds forward returns (24 h, 72 h, 7 d) from the 1h candles, compares
  the vetoed pile with the rest (bootstrap intervals, permutation test) and the portfolio runs.

## Running it

Written for a bot host laid out like this (adapt the paths otherwise): Freqtrade 2026.8 in `.venv/`, the strategies
in `user_data/strategies/`, `user_data/config.json`, the Binance overlay from
[Reproducing the backtests](../../docs/STRATEGY.md#reproducing-the-backtests) saved as `research/binfut20.json`,
downloaded Binance futures data, and Sentinel reachable at `NOVAEON_SENTINEL_URL`.

```bash
bash research/veto-eval/run.sh 20251001-20260924
.venv/bin/python research/veto-eval/analyze.py > research/veto-eval/out/report.md
```

The headline archive is not published (the headlines belong to their publishers). Rebuild one with the collectors in
[`novaeon-kev/`](../../novaeon-kev/) (`collect.py`, `collect2.py`: public Google News RSS searches) and put
`headlines.jsonl` / `headlines-v2.jsonl` into `research/veto-eval/data/`. A new collection returns different
headlines, so expect somewhat different numbers.
