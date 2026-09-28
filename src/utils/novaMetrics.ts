/**
 * NovaeonTradingAI Command Center metrics. Pure functions over bot API data, unit-tested in tests/unit/novaMetrics.spec.ts.
 * Conventions: long and short supported; ratios are fractions (0.05 = 5 %), money in stake currency.
 */
import type { ClosedTrade, Trade } from '@/types';

/** How trustworthy a statistic is, given the number of closed trades behind it. */
export type SampleQuality = 'early' | 'low' | 'solid';

export function sampleQuality(closedTrades: number, solidAt = 100, lowAt = 30): SampleQuality {
  if (closedTrades >= solidAt) return 'solid';
  if (closedTrades >= lowAt) return 'low';
  return 'early';
}

function sideSign(trade: Pick<Trade, 'is_short'>): 1 | -1 {
  return trade.is_short ? -1 : 1;
}

/** Position notional in stake currency (stake × leverage). */
export function notional(trade: Pick<Trade, 'stake_amount' | 'leverage'>): number {
  return (trade.stake_amount ?? 0) * (trade.leverage ?? 1);
}

/** Σ notional of open positions / equity. 1.0 = fully invested at 1x. */
export function exposureRatio(openTrades: Trade[], equity: number): number {
  if (!equity) return 0;
  return openTrades.reduce((sum, t) => sum + notional(t), 0) / equity;
}

/** Loss (positive number) if price moved from the current rate to the stop for this position. */
export function lossAtStop(trade: Trade): number {
  const current = trade.current_rate ?? trade.open_rate;
  if (!trade.stop_loss_abs || !current || !trade.amount) return 0;
  const move = (trade.stop_loss_abs - current) * sideSign(trade);
  return Math.max(0, -move * trade.amount);
}

/** Total loss if every open position hit its stop from here. */
export function riskAtStops(openTrades: Trade[]): number {
  return openTrades.reduce((sum, t) => sum + lossAtStop(t), 0);
}

/** Relative distance from the current price to the stop (price terms, not leveraged). */
export function distanceToStop(trade: Trade): number | null {
  const current = trade.current_rate ?? trade.open_rate;
  if (!trade.stop_loss_abs || !current) return null;
  return ((current - trade.stop_loss_abs) * sideSign(trade)) / current;
}

/** Relative distance from the current price to liquidation, or null without a liquidation price. */
export function distanceToLiquidation(trade: Trade): number | null {
  const current = trade.current_rate ?? trade.open_rate;
  if (!trade.liquidation_price || !current) return null;
  return ((current - trade.liquidation_price) * sideSign(trade)) / current;
}

export interface Excursion {
  /** Maximum favorable excursion, leveraged, as ratio of stake. */
  mfe: number;
  /** Maximum adverse excursion, leveraged, as ratio of stake (≤ 0). */
  mae: number;
}

/** MFE/MAE from the best and worst price seen during the trade (max_rate/min_rate). */
export function excursion(
  trade: Pick<Trade, 'open_rate' | 'max_rate' | 'min_rate' | 'leverage' | 'is_short'>,
): Excursion | null {
  const { open_rate: open, max_rate: hi, min_rate: lo } = trade;
  if (!open || !hi || !lo) return null;
  const lev = trade.leverage ?? 1;
  const up = ((hi - open) / open) * lev;
  const down = ((lo - open) / open) * lev;
  return trade.is_short ? { mfe: -down, mae: -up } : { mfe: up, mae: down };
}

export interface EdgeStats {
  wins: number;
  losses: number;
  winRate: number | null;
  avgWin: number | null;
  avgLoss: number | null;
  /** avg win / |avg loss| */
  payoff: number | null;
  /** Mean profit per closed trade in stake currency. */
  expectancyAbs: number | null;
  profitFactor: number | null;
}

export function edgeStats(closed: Pick<ClosedTrade, 'profit_abs'>[]): EdgeStats {
  const profits = closed.map((t) => t.profit_abs ?? 0);
  const winsArr = profits.filter((p) => p > 0);
  const lossArr = profits.filter((p) => p < 0);
  const sum = (a: number[]) => a.reduce((s, v) => s + v, 0);
  const avgWin = winsArr.length ? sum(winsArr) / winsArr.length : null;
  const avgLoss = lossArr.length ? sum(lossArr) / lossArr.length : null;
  return {
    wins: winsArr.length,
    losses: lossArr.length,
    winRate: profits.length ? winsArr.length / profits.length : null,
    avgWin,
    avgLoss,
    payoff: avgWin !== null && avgLoss !== null ? avgWin / Math.abs(avgLoss) : null,
    expectancyAbs: profits.length ? sum(profits) / profits.length : null,
    profitFactor: lossArr.length ? sum(winsArr) / Math.abs(sum(lossArr)) : null,
  };
}

export interface EquityPoint {
  ts: number;
  equity: number;
  /** Drawdown from the running peak as ratio (≤ 0). */
  drawdown: number;
}

/** Realized equity curve + underwater series from closed trades, starting at startingCapital. */
export function equityCurve(
  closed: Pick<ClosedTrade, 'close_timestamp' | 'profit_abs'>[],
  startingCapital: number,
  startTs?: number,
): EquityPoint[] {
  const sorted = [...closed]
    .filter((t) => t.close_timestamp)
    .sort((a, b) => (a.close_timestamp ?? 0) - (b.close_timestamp ?? 0));
  const points: EquityPoint[] = [];
  let equity = startingCapital;
  let peak = startingCapital;
  if (startTs !== undefined) points.push({ ts: startTs, equity, drawdown: 0 });
  for (const t of sorted) {
    equity += t.profit_abs ?? 0;
    peak = Math.max(peak, equity);
    points.push({
      ts: t.close_timestamp as number,
      equity,
      drawdown: peak ? equity / peak - 1 : 0,
    });
  }
  return points;
}

/** Gain needed to recover from a drawdown (e.g. -0.2 → 0.25). */
export function recoveryNeeded(drawdown: number): number {
  const dd = Math.min(0, drawdown);
  return dd <= -1 ? Infinity : 1 / (1 + dd) - 1;
}

/** Share of the largest winner in total gross profit (concentration / luck indicator). */
export function largestWinShare(closed: Pick<ClosedTrade, 'profit_abs'>[]): number | null {
  const wins = closed.map((t) => t.profit_abs ?? 0).filter((p) => p > 0);
  if (!wins.length) return null;
  return Math.max(...wins) / wins.reduce((s, v) => s + v, 0);
}
