# Donchian breakout ("turtle"): buy a new 20-candle high, exit on a 10-candle low (4h).
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class Breakout(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count = 30
    stoploss = -0.10
    minimal_roi = {"0": 10}
    use_exit_signal = True

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df["hi20"] = df["high"].rolling(20).max().shift(1)
        df["lo10"] = df["low"].rolling(10).min().shift(1)
        return df

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[(df["close"] > df["hi20"]) & (df["volume"] > 0), "enter_long"] = 1
        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        df.loc[df["close"] < df["lo10"], "exit_long"] = 1
        return df
