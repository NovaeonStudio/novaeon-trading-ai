# Breakout, but only while BTC's daily close is above its 50-day EMA (otherwise stay in cash).
# Exchange-neutral: uses BTC/<stake> on spot (Binance) and BTC/<stake>:<stake> on perps (Hyperliquid).
# Long-only, leverage 1x. Runs on 1h candles.
from freqtrade.strategy import merge_informative_pair
from pandas import DataFrame

from Breakout import Breakout


class BreakoutRegime(Breakout):
    timeframe = "1h"
    startup_candle_count = 30
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

    @property
    def protections(self):
        # Last-resort risk brake for crash cascades: after 6 stop-losses within 24 candles, pause new
        # entries for 12 candles. A drawdown-based brake was tested and rejected (cost ~4%/yr, no DD gain).
        return [
            {"method": "StoplossGuard", "lookback_period_candles": 24, "trade_limit": 6,
             "stop_duration_candles": 12, "only_per_pair": False},
        ]

    def _btc_pair(self) -> str:
        stake = self.config["stake_currency"]
        return f"BTC/{stake}:{stake}" if self.config.get("trading_mode") == "futures" else f"BTC/{stake}"

    def informative_pairs(self):
        return [(self._btc_pair(), "1d")]

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_indicators(df, metadata)
        btc = self.dp.get_pair_dataframe(self._btc_pair(), "1d")[["date", "close"]].copy()
        btc["ema50"] = btc["close"].ewm(span=50, adjust=False).mean()
        btc = btc.rename(columns={"close": "btc_close", "ema50": "btc_ema50"})
        return merge_informative_pair(df, btc, self.timeframe, "1d", ffill=True)

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_entry_trend(df, metadata)
        df.loc[df["btc_close_1d"] < df["btc_ema50_1d"], "enter_long"] = 0
        df.loc[df["volume"] < self.volume_mult * df["volume"].rolling(20).mean(), "enter_long"] = 0
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_exit_trend(df, metadata)
        df.loc[df["btc_close_1d"] < df["btc_ema50_1d"], "exit_long"] = 1
        return df

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

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag,
                 side, **kwargs) -> float:
        return 1.0
