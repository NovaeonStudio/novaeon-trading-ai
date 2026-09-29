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
| Candles | 15 minutes (all windows below are in hours, so the rules keep the same time horizon as on 1h candles) | `timeframe = "15m"` |
| Direction | Long only | `can_short = False` |
| Positions | At most 8 at a time; the available balance is split across the free slots | `max_open_trades: 8`, `stake_amount: "unlimited"` |
| Trend filter | New trades only while Bitcoin's daily close is at or above its 50-day EMA | `btc_close_1d < btc_ema50_1d` → no entry |
| Entry | 15-minute close above the highest high of the previous 20 hours (80 candles) | `entry_hours = 20` |
| Volume filter | Entry candle volume at least 2× the average of the previous 20 hours | `volume_mult = 2.0`, `volume_hours = 20` |
| Entry cap | Off: no limit on new trades per hour or day beyond the 8 slots. Optional: e.g. at most 2 per hour and 5 per 24 hours (manual buys count, but are never blocked) | `max_entries_1h = None`, `max_entries_24h = None` |
| News check | Blocked if Sentinel's P(major negative news) ≥ 0.30 | `VETO_THRESHOLD = 0.3` |
| Exit | 15-minute close below the lowest low of the previous 10 hours (40 candles) | `exit_hours = 10` |
| Trend exit | Sell when Bitcoin's daily close falls below its 50-day EMA | `exit_long = 1` |
| Stop-loss | 10% of the position's margin: a 10% price drop at 1×, about 3.3% at 3× | `stoploss = -0.10` |
| Take-profit | Half the position once the price is 20% above the entry (measured on the price, not the leveraged profit); the other half runs until an exit rule fires | `take_profit_move = 0.20`, `take_profit_fraction = 0.5` |
| Emergency brake | After 6 stop-losses within 24 hours, no new entries for 12 hours | `StoplossGuard` |
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

- Before each new position, the bot collects headlines from the last 48 hours from two kinds of source:
  - the public RSS feeds of CoinDesk, Cointelegraph, Decrypt and The Block (title plus up to 200 characters of
    summary), refreshed at most every 15 minutes;
  - two public Google News RSS searches for the coin, one plain and one for risk words (hack, exploit, delisting,
    lawsuit, outage, halt), cached for 15 minutes. This is the same source Sentinel's training data came from. The
    four outlet feeds alone carry only about 50 items in 48 hours, so most coins had no headlines at all.
    `NOVAEON_NEWS_SEARCH=off` turns the searches off.
- It keeps headlines that mention the coin by name (for example "chainlink") or by its ticker as an uppercase word
  (`LINK`), up to 15, newest first. Up to 7 of the 15 go to hits of the risk search first, so a day-old hack is not
  pushed out by a few hours of price commentary on a busy coin.
- Filler is dropped before that: paid presale promotions and "best crypto to buy" lists (always, even when they
  ride on real news), currency-converter and price-chart pages, and price predictions unless they contain a risk word.
  That is about one in five search hits for a big coin. On Sentinel's 495 held-out items the filter kept every
  caught bad-news item (23 of 28 with the 8-bit build) and cut harmless blocks from 8 to 6.
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
  skipping trades. A separate replay with archived headlines estimates what the news check did: see
  [The news check in a replay](#the-news-check-in-a-replay).

## Results

| Period | Data | Return | Max drawdown | Trades | Win rate | Profit factor | Longest losing streak |
|---|---|---|---|---|---|---|---|
| 2024-11-01 to 2025-09-24 | Binance | +53.1% | 21.8% | 941 | 37% | 1.23 | 22 trades |
| 2025-09-24 to 2026-09-25 | Binance | +101.5% | 10.8% | 494 | 39% | 2.25 | 19 trades |

On 15-minute candles there is no Hyperliquid row: Hyperliquid serves only about 5,000 candles per coin, which is
about 50 days at 15 minutes. The same rules on 1-hour candles (version 1.3.2 and earlier) gave +66.8% / 16.1%,
+62.4% / 17.7% and, on Hyperliquid from 2025-01-01, +72.8% / 8.8%. The notes below on drawdown periods refer to the
1-hour runs.

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
- **Take-profit on half, at +20%** (added 2026-09-29, version 1.2): winners often gave a large part of their
  peak gain back before the 10-candle-low exit fired (on trades that were at least +10% at their best, only about
  55–60% of the peak gain was kept). We tested 15 exit variants on all three periods
  ([`bot/research/ExitVariants.py`](../bot/research/ExitVariants.py), results in
  [`exit-results.json`](../bot/research/exit-results.json)): fixed take-profits at +10/15/20/30%, selling a
  part at +8/10/15/20%, a faster exit once a trade was +10/15% up, a cap on how much gain may be given back, and
  wide trailing stops. **None beat the plain rules on return**, and none lowered the drawdown noticeably: the
  strategy lives on a few long trends, and every take-profit cuts some of them. Selling half at +20% cost the
  least (+66.8% vs +64.9%, +62.4% vs +72.1% and +72.8% vs +82.9% on the same data) at the same drawdown, and it
  banks half of every big winner. We chose it on purpose: a steadier path is worth those points to us. Before this
  change the results table read +64.9% / +74.5% / +82.9% (the second Binance period is +72.1% on today's data).
- **Entry cap: at most 2 new trades per hour and 4 per 24 hours** (added 2026-09-29, version 1.3). The bot buys
  at the close of the breakout candle, which is usually the local top: in our entry analysis the entry candle was
  already up about 2.5% (median), and in the next 6 hours the price fell about 2.1% at worst but rose only 1.3% at
  best (medians). When the whole market breaks out, the bot bought several coins in the same hour, and they
  pulled back together. We tested 13 entry variants and 12 exit and risk variants on all three periods, plus two
  combinations, and judged them by return divided by maximum drawdown:
  - **Waiting for a pullback** after the breakout (−1%, −2%, back to the breakout level, to the candle middle) or
    for a second confirming candle was **worse in every variant**: the best breakouts never come back and are missed.
  - Wider exits (20/40-candle low), chandelier and ATR stops, a time stop, volatility sizing and a 40-candle
    breakout filter were mixed or worse.
  - **Only the entry cap was better in all three periods**: drawdown 16.1% → 10.9%, 17.7% → 9.1% and 8.8% → 3.5%;
    return +66.8% → +46.8%, +62.4% → +62.3% and +72.8% → +58.6%. It gives up return in two of three periods for
    a much steadier path, and we chose that on purpose. Before this change the results table read +66.8% / +62.4% /
    +72.8% with drawdowns of 16.1% / 17.7% / 8.8%.
  - **5 per 24 hours instead of 4** (version 1.3.1, same day): more return where the bot trades, at a moderate
    drawdown cost: +56.1% / +61.3% / +63.3% with drawdowns of 14.0% / 10.8% / 6.9% (4 per day: +46.8% / +62.3% /
    +58.6%, 10.9% / 9.1% / 3.5%). Looser settings were worse: 6 per day (+64.2% / +49.1% / +59.2%, drawdown up to
    15.3%), 2 per hour with no daily limit, and more slots without a cap (12 slots: +62.5% / +44.5% / +60.2%;
    20 slots: +46.8% / +28.0% / +34.8%). More slots split the balance into smaller stakes, so the few big winners
    earn less while many more small losers are added.
  - **Cap switched off again** (version 1.3.2, same day): we run the uncapped rules on purpose, for the highest
    backtest return, and accept the deeper drawdowns and the clustered entries on strong breakout days. The cap
    stays in the code as an option; the results table above is for the uncapped rules.
- **15-minute candles, same time horizon** (added 2026-09-29, version 1.4): the rules still buy a 20-hour high and
  sell below a 10-hour low, but the bot checks every 15 minutes instead of every hour, so it gets in and out earlier.
  Tested on both Binance periods and on four half-years:

  | Half-year | 1 hour | 15 minutes |
  |---|---|---|
  | Nov 2024 – Apr 2025 | +25.2% / 14.6% | +7.7% / 21.6% |
  | May – Sep 2025 | +34.3% / 15.6% | +41.7% / 16.7% |
  | Sep 2025 – Mar 2026 | −4.2% / 11.7% | +1.0% / 9.6% |
  | Mar – Sep 2026 | +68.4% / 7.3% | +99.2% / 8.3% |

  15 minutes did better in three of four half-years, most in trends, and clearly worse in the choppy first half
  (Nov 2024 – Apr 2025). Over both Binance years together it turned 2,000 into about 6,170 instead of 5,420, with a
  deeper worst drawdown (21.8% instead of 17.7%). We chose it for the higher return. Not tested on Hyperliquid
  (too little 15-minute history). The same rules with the 1-hour candle counts on shorter candles (20/10 candles =
  5 h / 2.5 h on 15m, 100 / 50 minutes on 5m) lost money: −7.5% and −48.4% in the first Binance period, from noise
  and fees on 4 to 12 times as many trades. Five-minute candles with the same time horizon were worse than one hour.
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
# Binance futures, 15m + 1d (the engine also fetches funding rates and mark prices for futures)
freqtrade download-data -c config.json -c binance-futures-20.json -t 15m 1d --timerange 20240901-
freqtrade backtesting  -c config.json -c binance-futures-20.json -s BreakoutRegime \
  --timerange 20241101-20250924 --max-open-trades 8 --dry-run-wallet 2000

# Hyperliquid: the engine cannot download Hyperliquid history, use bot/bin/hl-download.py
python bot/bin/hl-download.py
freqtrade backtesting -c config.json -c exchange-hyperliquid.json -s BreakoutRegime \
  --timerange 20250101- --max-open-trades 8 --dry-run-wallet 2000
```

Results depend on the data you download (exchanges revise candles, and newer data extends the last period).

## The news check in a replay

To see what the news check does to the bot (not just how well Sentinel agrees with its training labels), we replayed
it over the second Binance year with an archive of about 33,000 timestamped headlines (the Google News searches
Sentinel's data was collected from). The replay uses the bot's own news-check code and only swaps the live feeds for
the archive. Headlines with only a date count as known 24 hours later, so no later news leaks into an entry.

- 2025-10-01 to 2026-09-23: 616 entries the strategy wanted (no slot limit), 530 with headlines, **10 blocked**.
- Blocked entries: average trade −2.1%, 1 of 10 winners, −2.8% after 72 hours. Allowed entries: +1.0%, 38% winners,
  +0.9% after 72 hours. Difference per trade −3.0 points (one-sided permutation p ≈ 0.05; after 72 hours p ≈ 0.12).
- The 10 blocks come from about five events (the Kelp DAO fallout at Aave, the Litecoin MWEB exploit, a Bittensor
  founder dispute, a closed Dogecoin ETF and a Uniswap trademark case), so this is weak evidence, not proof.
- Portfolio (8 slots, 2,000 USDT): +61.5% without the news check, +61.4% with it, drawdown 17.1% vs 17.2%. The
  stop-loss already limits these trades to −2% to −5%, and the freed slots get average trades.

Read: the news check is cheap insurance against hack-type events, not a source of returns. Code and full results:
[`research/veto-eval/`](../research/veto-eval/).
