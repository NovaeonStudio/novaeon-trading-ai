# Breakout, but only while BTC's daily close is above its 50-day EMA (otherwise stay in cash).
# Exchange-neutral: uses BTC/<stake> on spot (Binance) and BTC/<stake>:<stake> on perps (Hyperliquid).
# Long-only, leverage 1x. Runs on 15m candles (v5); all windows are set in hours, so it runs on any timeframe.
from datetime import timedelta

from freqtrade.persistence import Trade
from freqtrade.exchange import timeframe_to_minutes
from freqtrade.strategy import merge_informative_pair
from pandas import DataFrame

from Breakout import Breakout


class BreakoutRegime(Breakout):
    # v5 (2026-09-29): 15-minute candles instead of 1h, same time horizon: buy a close above the 20-hour high on 2x the
    # 20-hour average volume, sell below the 10-hour low. Only the timing gets four times finer. Research (Binance,
    # see docs/STRATEGY.md): +53.1% / +101.5% (drawdown 21.8% / 10.8%) vs 1h +66.8% / +62.4% (16.1% / 17.7%); better
    # in 3 of 4 half-years, clearly worse in the choppy Nov 2024 - Apr 2025 half. The same rules on 15m or 5m with the
    # 1h candle counts (5 h / 100 min windows) lost money: noise and fees. Set timeframe = "1h" for the old behaviour.
    timeframe = "15m"
    entry_hours = 20      # breakout above the highest high of the last 20 hours
    exit_hours = 10       # exit below the lowest low of the last 10 hours
    volume_hours = 20     # volume filter: entry candle vs. the average of the last 20 hours
    startup_candle_count = 100
    can_short = False
    # v2 (2026-09-26): only take breakouts on at least 2x the 20-candle average volume.
    # Research (see docs/STRATEGY.md): better in both Binance years and on Hyperliquid 2026,
    # worst-case drawdown 30% -> 17.5%. Trailing/breakeven stops tested and rejected (much worse).
    volume_mult = 2.0
    # v3 (2026-09-29): take-profit on half. Once the price is 20% above the entry, sell half of the position; the
    # other half keeps running under the normal exit rules. Measured on the price, not on the leveraged profit, so
    # a 3x trade does not sell after a 6.7% move. Research (15 exit variants, see docs/STRATEGY.md): every
    # take-profit cost some return because the strategy lives on a few long trends; this one cost the least
    # (about -10 points in two of three periods, +3 in the third) at the same drawdown, and it locks in half of the
    # big winners. Full take-profits, trailing and give-back stops cost far more.
    position_adjustment_enable = True
    take_profit_move = 0.20
    take_profit_fraction = 0.5
    # v4 (2026-09-29): entry clustering cap. At most 2 new trades per hour and 4 per 24h. When the whole market breaks
    # out, the bot used to buy several coins at once, and they pulled back together. Research (phase 2, 12 variants +
    # 2 combos, see docs/STRATEGY.md): the only change with a better return/drawdown in all three periods; drawdown
    # 16.1/17.7/8.8% -> 10.9/9.1/3.5%, return 66.8/62.4/72.8% -> 46.8/62.3/58.6%. Waiting for a pullback after the
    # breakout was worse in every variant (the best breakouts never come back). Manual buys count but are not blocked.
    # v4.1 (same day): 5 per 24h instead of 4, for more return at a moderate drawdown cost: return 56.1/61.3/63.3%,
    # drawdown 14.0/10.8/6.9%. 6 per 24h was worse than 5 in two periods; 12 or 20 slots without a cap were worse too
    # (smaller stake per trade, many more small losers).
    # v4.2 (same day): cap OFF by choice, for the highest backtest return (+66.8/62.4/72.8%) at the higher drawdown
    # (16.1/17.7/8.8%). Behaviour is exactly v3. Set both values (e.g. 2 and 5) to switch the cap back on.
    max_entries_1h: int | None = None
    max_entries_24h: int | None = None
    # v6 (2026-10-02, Maik): the exit level only rises. While a trade is open, it sells when a closed candle closes
    # below the HIGHEST 10-hour low seen since the entry, so the line follows the price up and never steps down
    # (before, the plain 10-hour low could fall again, e.g. after wicks). Research (Binance 15m, see docs/STRATEGY.md):
    # +46.9% / +105.5% (drawdown 18.5% / 10.7%) vs +53.1% / +101.5% (21.8% / 10.8%); lower drawdown in 3 of 4
    # half-years. Only in profit (ratchet from break-even on) was neutral. Set ratchet_exit = False for v5.
    ratchet_exit = True
    _ratchet: dict = {}

    @property
    def protections(self):
        # Last-resort risk brake for crash cascades: after 6 stop-losses within 24 hours, pause new
        # entries for 12 hours. A drawdown-based brake was tested and rejected (cost ~4%/yr, no DD gain).
        return [
            {"method": "StoplossGuard", "lookback_period_candles": 24 * self._cph(), "trade_limit": 6,
             "stop_duration_candles": 12 * self._cph(), "only_per_pair": False},
        ]

    def _cph(self) -> int:
        """Candles per hour for the current timeframe (15m -> 4, 1h -> 1)."""
        return max(1, 60 // timeframe_to_minutes(self.timeframe))

    def _btc_pair(self) -> str:
        stake = self.config["stake_currency"]
        return f"BTC/{stake}:{stake}" if self.config.get("trading_mode") == "futures" else f"BTC/{stake}"

    def informative_pairs(self):
        return [(self._btc_pair(), "1d")]

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_indicators(df, metadata)
        df["hi20"] = df["high"].rolling(self.entry_hours * self._cph()).max().shift(1)   # names kept for the app
        df["lo10"] = df["low"].rolling(self.exit_hours * self._cph()).min().shift(1)
        btc = self.dp.get_pair_dataframe(self._btc_pair(), "1d")[["date", "close"]].copy()
        btc["ema50"] = btc["close"].ewm(span=50, adjust=False).mean()
        btc = btc.rename(columns={"close": "btc_close", "ema50": "btc_ema50"})
        return merge_informative_pair(df, btc, self.timeframe, "1d", ffill=True)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_entry_trend(df, metadata)
        df.loc[df["btc_close_1d"] < df["btc_ema50_1d"], "enter_long"] = 0
        df.loc[df["volume"] < self.volume_mult * df["volume"].rolling(self.volume_hours * self._cph()).mean(), "enter_long"] = 0
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_exit_trend(df, metadata)
        df.loc[df["btc_close_1d"] < df["btc_ema50_1d"], "exit_long"] = 1
        return df

    def exit_level(self, pair: str, trade, current_time) -> tuple[float | None, float | None]:
        """(Ratchet exit level, close of the last closed candle). The level is the highest lo10 of the closed candles
        since the entry. Only closed candles count (close time <= now), so backtests never look ahead."""
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or df.empty:
            return None, None
        tf = timedelta(minutes=timeframe_to_minutes(self.timeframe))
        closed = df[df["date"] + tf <= current_time]
        if closed.empty:
            return None, None
        last = closed.iloc[-1]
        key = (trade.id, trade.open_date_utc)
        lvl, seen = self._ratchet.get(key, (None, None))
        if seen is None:  # first look at this trade (or after a restart): rebuild from the candles since the entry
            since = closed.loc[closed["date"] >= trade.open_date_utc - tf, "lo10"].max()
            lvl = since if since == since else None
        elif last["date"] > seen and last["lo10"] == last["lo10"]:
            lvl = last["lo10"] if lvl is None else max(lvl, last["lo10"])
        BreakoutRegime._ratchet[key] = (lvl, last["date"])
        return lvl, float(last["close"])

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        """Ratchet exit (v6): a closed candle closed below the highest 10-hour low since the entry."""
        if not self.ratchet_exit or trade.is_short:
            return None
        lvl, close = self.exit_level(pair, trade, current_time)
        if lvl is not None and close is not None and close < lvl:
            BreakoutRegime._ratchet.pop((trade.id, trade.open_date_utc), None)
            return "exit_signal"
        return None

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit, min_stake, max_stake,
                              **kwargs):
        """Sell `take_profit_fraction` of the position once, when the price is `take_profit_move` above the entry."""
        if trade.is_short or trade.nr_of_successful_exits > 0:
            return None
        if current_rate < trade.open_rate * (1 + self.take_profit_move):
            return None
        part = trade.stake_amount * self.take_profit_fraction
        if min_stake and part < min_stake:
            return None
        return -part, "take_profit_half"

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, current_time, entry_tag, side,
                            **kwargs) -> bool:
        """Entry clustering cap (v4): skip a signal if `max_entries_1h` / `max_entries_24h` trades already opened."""
        if entry_tag == "force_entry" or self.max_entries_1h is None or self.max_entries_24h is None:
            return True
        trades = Trade.get_trades_proxy()
        recent1 = sum(1 for t in trades if t.open_date_utc >= current_time - timedelta(hours=1))
        recent24 = sum(1 for t in trades if t.open_date_utc >= current_time - timedelta(hours=24))
        return recent1 < self.max_entries_1h and recent24 < self.max_entries_24h

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag,
                 side, **kwargs) -> float:
        return 1.0
