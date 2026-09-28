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

    def leverage(self, pair, current_time, current_rate, proposed_leverage, max_leverage, entry_tag,
                 side, **kwargs) -> float:
        return 1.0
