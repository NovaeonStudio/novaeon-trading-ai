# The strategy

NovaeonTradingAI trades one strategy, `BreakoutRegimeKev`. This page lists every rule with the value used in the
code, how it was tested, and what the tests showed, including the bad parts.

> Backtests are simulations on past data. **Past results do not guarantee future results. This is not financial
> advice.** Every return below comes with its maximum drawdown; read them together.

## In one paragraph

Buy a coin when its price breaks out above its recent range on unusually high volume, but only while Bitcoin is in
an uptrend and only if the news about that coin is not seriously bad. Sell when the price falls back below its
shorter recent range, when Bitcoin's trend breaks, or at the stop-loss. Most trades are small losses; a few large
moves pay for them.

## Rules

Source: [`bot/strategies/BreakoutRegime.py`](../bot/strategies/BreakoutRegime.py) (market rules),
[`bot/strategies/BreakoutRegimeKev.py`](../bot/strategies/BreakoutRegimeKev.py) (news check, leverage, manual stops)
and the `Breakout` base class they extend.

| Rule | Value | In the code |
|---|---|---|
| Exchange | Hyperliquid, USDC perpetual futures, isolated margin | `bot/config/exchange-hyperliquid.json` |
| Coins | BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, LINK, NEAR, ZEC, ONDO, ENA, LTC, TAO, SUI, UNI, ARB, WLD, AAVE | `pair_whitelist` |
| Candles | 1 hour | `timeframe = "1h"` |
| Direction | Long only | `can_short = False` |
| Positions | At most 8 at a time; the available balance is split across the free slots | `max_open_trades: 8`, `stake_amount: "unlimited"` |
| Trend filter | New trades only while Bitcoin's daily close is at or above its 50-day EMA | `btc_close_1d < btc_ema50_1d` → no entry |
| Entry | Hourly close above the highest high of the previous 20 candles | `hi20 = high.rolling(20).max().shift(1)` |
| Volume filter | Entry candle volume at least 2× the 20-candle average | `volume_mult = 2.0` |
| News check | Blocked if Sentinel's P(major negative news) ≥ 0.30 | `VETO_THRESHOLD = 0.3` |
| Exit | Hourly close below the lowest low of the previous 10 candles | `lo10 = low.rolling(10).min().shift(1)` |
| Trend exit | Sell when Bitcoin's daily close falls below its 50-day EMA | `exit_long = 1` |
| Stop-loss | 10% of the position's margin: a 10% price drop at 1×, about 3.3% at 3× | `stoploss = -0.10` |
| Take-profit | None (winners run until an exit rule fires) | `minimal_roi = {"0": 10}` |
| Emergency brake | After 6 stop-losses within 24 candles, no new entries for 12 candles | `StoplossGuard` |
| Orders | Limit orders at the best bid/ask; fees 0.045% per side on Hyperliquid | `order_types`, `fee` |

### Leverage

- **Default: 1× for every trade.** AI leverage is an opt-in setting and is locked off on Macs with 8 GB of memory.
- With AI leverage on, Sentinel's outlook decides, and only when the news check passed (P(major negative) < 0.30):
  - **2×** if P(clearly positive news) ≥ 0.50 (`LEV2_POSITIVE`),
  - **3×** if P(clearly positive news) ≥ 0.75 (`LEV3_POSITIVE`) **and** Bitcoin's daily close is at least 5% above
    its 50-day EMA (`LEV3_BTC_STRENGTH = 1.05`),
  - otherwise 1×. Hard cap: 3× (`MAX_LEVERAGE`).
- 3× is rare by design: on the held-out test set no threshold made "clearly positive" at least 90% precise, so the
  3× threshold stays at a strict 0.75 plus the Bitcoin condition.
- No headlines, an unreachable model or a failed request always mean 1×.

### The news check in detail

- Before each new position, the bot collects headlines (title plus up to 200 characters of summary) from the
  public RSS feeds of CoinDesk, Cointelegraph, Decrypt and The Block. Feeds are refreshed at most every 15 minutes.
- It keeps headlines from the last 48 hours that mention the coin by name (for example "chainlink") or by its
  ticker as an uppercase word (`LINK`), up to 15.
- If there are none, the trade is allowed at 1× without asking the model.
- Otherwise Sentinel answers two questions in one call (see [SENTINEL.md](SENTINEL.md)). The answer is cached for
  2 minutes, shared by the leverage and entry decisions.
- If the model does not answer (45 s timeout), the trade is allowed at 1× ("fail open"). The reasoning: a missed
  news check at 1× is the same risk as the plain strategy, which is what the backtests measure; blocking all trades
  whenever the model is down would silently turn the bot off.
- Every decision (allowed, blocked, why, probabilities, headline titles) is written to a decision log and attached
  to the trade, so the app can show why a position was opened.

### Manual controls

- **Sell now:** closes a position at the market.
- **Buy more / manual buy:** long only, at most 3 additions per position. Adding to an open position skips the
  news check (the first entry already had one); a manual buy of a new coin goes through the news check.
- **Move stop:** a stop can only be raised (tightened), never lowered. If the price is already below the new stop,
  the position is sold right away.
- Manual changes never affect the automatic rules or the backtests.

### When the Mac is off

The strategy runs on your Mac. While the Mac sleeps or is off, no new trades happen and exits based on the rules
above cannot fire. In live mode the stop-loss is also placed on the exchange (`stoploss_on_exchange`), so open
positions keep a stop.

## How it was tested

- **Engine:** the same trading engine the bot runs on, in backtesting mode, with the same strategy code.
- **Setup:** 20 coins, 8 slots, 2,000 USDC start, 1×, trading fees and funding payments included.
- **Two separate Binance periods** (USDT-margined futures, which have longer history than Hyperliquid):
  2024-11-01 to 2025-09-24 and 2025-09-24 to 2026-09-25. Rules were compared on both; a change had to help in both.
- **Hyperliquid check:** the real exchange data from 2025-01-01 to 2026-09-26. Hyperliquid only serves about 5,000
  hourly candles per coin, so 9 coins (BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, LINK) cover the whole period and
  the other 11 start in March 2026.
- **Not in the backtests:** the news check and AI leverage. Historical headlines cannot be replayed the way the
  live feeds deliver them, so the backtests show the plain rules at 1×. The news check can only change results by
  skipping trades.

## Results

| Period | Data | Return | Max drawdown | Trades | Win rate | Profit factor | Longest losing streak |
|---|---|---|---|---|---|---|---|
| 2024-11-01 to 2025-09-24 | Binance | +64.9% | 16.1% | 663 | 40% | 1.34 | 16 trades |
| 2025-09-24 to 2026-09-25 | Binance | +74.5% | 17.5% | 397 | 37% | 2.00 | 24 trades |
| 2025-01-01 to 2026-09-26 | Hyperliquid | +82.9% | 9.1% | 340 | 38% | 2.27 | 14 trades |

Read these together with the bad parts:

- **Drawdowns last long.** In the second Binance period the account stayed below its previous high from
  2025-10-04 to 2026-05-01, almost seven months. In the Hyperliquid test the worst drawdown ran from 2026-05-12 to
  2026-08-10.
- **Most trades lose.** Win rates are 37–40%. The average trade lasts about a day; profits come from a few trades
  that run for days.
- **Leverage cuts both ways.** As a stress test we ran the same rules on Hyperliquid with **every** trade at 3×
  (the AI would choose 3× far less often): +210.6% with the account up to 23.9% below its previous high. Higher
  return, much deeper drops, and a 10% stop-loss becomes a 3.3% price move.
- **The backtest periods include a strong crypto market.** A long bear market mostly means the trend filter keeps
  the bot in cash: little loss, but also no gain.

## Why these rules

- **The trend filter** keeps the bot out of the market when Bitcoin is weak, which is when breakouts of other coins
  fail most often.
- **The volume filter** was the research result that mattered most: a breakout on at least twice the normal volume
  is far less often a false start. Compared with the same rules without it, it improved the return and reduced
  the maximum drawdown in both Binance periods. Every threshold between 1.5× and 3× reduced the drawdown in both
  periods, so the effect does not hinge on one lucky value; 2× gave the best balance of return and drawdown.
- **No trailing stop or break-even stop:** tested, and both made results clearly worse. This strategy depends on
  letting winners run through normal pullbacks.
- **The emergency brake** never triggered in the test periods; it exists for crash cascades that the tests did not
  contain.

## Checking live results

The app's Strategy page compares live trading with these backtests (win rate, profit factor, trades per day,
drawdown). Treat anything under about 30 closed trades as noise.

## Reproducing the backtests

The research scripts are in [`bot/research/`](../bot/research/) (`sweep.py`, `analyze.py`). You need Freqtrade
2026.8, the strategy files (including the `Breakout` base class) in `user_data/strategies/`, `bot/config/config.json`
and downloaded data. For Binance, use a small config overlay `binance-futures-20.json` with
`"stake_currency": "USDT"`, `"trading_mode": "futures"`, `"margin_mode": "isolated"`, `"fee": 0.0005` and the same
20 coins as `BTC/USDT:USDT` … `AAVE/USDT:USDT`.

```bash
# Binance futures, 1h + 1d (the engine also fetches funding rates and mark prices for futures)
freqtrade download-data -c config.json -c binance-futures-20.json -t 1h 1d --timerange 20240901-
freqtrade backtesting  -c config.json -c binance-futures-20.json -s BreakoutRegime \
  --timerange 20241101-20250924 --max-open-trades 8 --dry-run-wallet 2000

# Hyperliquid: the engine cannot download Hyperliquid history, use bot/bin/hl-download.py
python bot/bin/hl-download.py
freqtrade backtesting -c config.json -c exchange-hyperliquid.json -s BreakoutRegime \
  --timerange 20250101- --max-open-trades 8 --dry-run-wallet 2000
```

Results depend on the data you download (exchanges revise candles, and newer data extends the last period).
