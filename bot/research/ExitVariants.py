"""Research (2026-09-29): profit-taking variants of BreakoutRegime v2 at 1x. Each class changes one idea.
Base exit = hourly close below the 10-candle low (lo10), BTC trend exit, -10% stop, no take-profit.
Results: exit-results.json. P50at20 became the live rule in v3 (BreakoutRegime.take_profit_*)."""
import sys
from pathlib import Path

from pandas import DataFrame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strategies"))
from BreakoutRegime import BreakoutRegime  # noqa: E402


class _V2(BreakoutRegime):
    """The rules before v3: no take-profit (v3 sells half at +20%)."""

    def adjust_trade_position(self, *args, **kwargs):
        return None


class V00Base(_V2):
    pass


# --- Fixed take-profit (sell everything at +X%) -----------------------------------------------------------------
class R10(_V2):
    minimal_roi = {"0": 0.10}


class R15(_V2):
    minimal_roi = {"0": 0.15}


class R20(_V2):
    minimal_roi = {"0": 0.20}


class R30(_V2):
    minimal_roi = {"0": 0.30}


# --- Partial take-profit: sell part at +X%, the rest keeps running under the normal exit rules -------------------
class _Partial(_V2):
    position_adjustment_enable = True
    max_entry_position_adjustment = 0
    tp_levels: tuple = ()   # ((profit, fraction of the ORIGINAL stake to sell), ...)

    def adjust_trade_position(self, trade, current_time, current_rate, current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate, current_entry_profit, current_exit_profit,
                              **kwargs):
        done = trade.nr_of_successful_exits
        if done >= len(self.tp_levels):
            return None
        level, frac = self.tp_levels[done]
        if current_profit >= level:
            first = trade.select_filled_orders(trade.entry_side)[0]
            return -(first.stake_amount * frac), f"tp{done + 1}"
        return None


class P50at10(_Partial):
    tp_levels = ((0.10, 0.5),)


class P50at15(_Partial):
    tp_levels = ((0.15, 0.5),)


class P33at8_16(_Partial):
    tp_levels = ((0.08, 0.33), (0.16, 0.33))


class P50at20(_Partial):
    tp_levels = ((0.20, 0.5),)


# --- Once far in profit, exit faster (5-candle low instead of 10) ----------------------------------------------
class _Lock(_V2):
    lock_at = 0.10

    def populate_indicators(self, df: DataFrame, metadata: dict) -> DataFrame:
        df = super().populate_indicators(df, metadata)
        df["lo5"] = df["low"].rolling(5).min().shift(1)
        return df

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        peak = trade.max_rate / trade.open_rate - 1
        if peak < self.lock_at:
            return None
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last = df.iloc[-1]
        if last["close"] < last["lo5"]:
            return "lock_lo5"
        return None


class L5at10(_Lock):
    lock_at = 0.10


class L5at15(_Lock):
    lock_at = 0.15


# --- Give-back cap: once the peak was >= X%, sell when half (or 40%) of the peak gain is gone -------------------
class _GiveBack(_V2):
    gb_at = 0.10
    keep = 0.5   # sell when the gain falls below keep * peak gain

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        peak = trade.max_rate / trade.open_rate - 1
        if peak >= self.gb_at and (current_rate / trade.open_rate - 1) <= self.keep * peak:
            return "giveback"
        return None


class GB50at10(_GiveBack):
    gb_at, keep = 0.10, 0.5


class GB60at15(_GiveBack):
    gb_at, keep = 0.15, 0.6


# --- Wide trailing stop (the narrow ones were rejected earlier) -------------------------------------------------
class T6at12(_V2):
    trailing_stop = True
    trailing_stop_positive = 0.06
    trailing_stop_positive_offset = 0.12
    trailing_only_offset_is_reached = True


class T8at20(_V2):
    trailing_stop = True
    trailing_stop_positive = 0.08
    trailing_stop_positive_offset = 0.20
    trailing_only_offset_is_reached = True
