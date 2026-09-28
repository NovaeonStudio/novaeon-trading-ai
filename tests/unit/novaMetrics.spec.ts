import { describe, expect, it } from 'vitest';
import {
  distanceToLiquidation,
  distanceToStop,
  edgeStats,
  equityCurve,
  excursion,
  exposureRatio,
  largestWinShare,
  lossAtStop,
  recoveryNeeded,
  riskAtStops,
  sampleQuality,
} from '@/utils/novaMetrics';
import type { Trade } from '@/types';

const long = (over: Partial<Trade> = {}) =>
  ({
    stake_amount: 250,
    leverage: 1,
    amount: 2,
    open_rate: 100,
    current_rate: 110,
    stop_loss_abs: 90,
    is_short: false,
    ...over,
  }) as Trade;

describe('novaMetrics', () => {
  it('grades sample size', () => {
    expect(sampleQuality(5)).toBe('early');
    expect(sampleQuality(30)).toBe('low');
    expect(sampleQuality(100)).toBe('solid');
  });

  it('computes exposure from stake × leverage', () => {
    const open = [long(), long({ leverage: 3 })];
    // (250 + 750) / 2000
    expect(exposureRatio(open, 2000)).toBeCloseTo(0.5);
    expect(exposureRatio(open, 0)).toBe(0);
  });

  it('computes loss if stops are hit (long and short)', () => {
    // long: 2 × (110 - 90) = 40
    expect(lossAtStop(long())).toBeCloseTo(40);
    // short: price 90, stop 100 → 2 × 10 = 20
    expect(lossAtStop(long({ is_short: true, current_rate: 90, stop_loss_abs: 100 }))).toBeCloseTo(
      20,
    );
    // stop already above price for a long (trailing into profit) → no loss
    expect(lossAtStop(long({ stop_loss_abs: 120 }))).toBe(0);
    expect(riskAtStops([long(), long()])).toBeCloseTo(80);
  });

  it('computes distances to stop and liquidation', () => {
    expect(distanceToStop(long())).toBeCloseTo(20 / 110);
    expect(distanceToLiquidation(long())).toBeNull();
    expect(distanceToLiquidation(long({ liquidation_price: 77 }))).toBeCloseTo(33 / 110);
  });

  it('computes leveraged excursions', () => {
    expect(excursion(long({ max_rate: 120, min_rate: 95, leverage: 2 }))).toEqual({
      mfe: 0.4,
      mae: -0.1,
    });
    const short = excursion(long({ is_short: true, max_rate: 105, min_rate: 80 }));
    expect(short?.mfe).toBeCloseTo(0.2);
    expect(short?.mae).toBeCloseTo(-0.05);
    expect(excursion(long({ max_rate: undefined }))).toBeNull();
  });

  it('computes edge stats', () => {
    const e = edgeStats([
      { profit_abs: 30 },
      { profit_abs: 10 },
      { profit_abs: -10 },
      { profit_abs: -10 },
    ]);
    expect(e.winRate).toBe(0.5);
    expect(e.avgWin).toBe(20);
    expect(e.avgLoss).toBe(-10);
    expect(e.payoff).toBe(2);
    expect(e.expectancyAbs).toBe(5);
    expect(e.profitFactor).toBe(2);
    expect(edgeStats([]).winRate).toBeNull();
    expect(edgeStats([{ profit_abs: 5 }]).profitFactor).toBeNull();
  });

  it('builds an equity curve with running drawdown', () => {
    const pts = equityCurve(
      [
        { close_timestamp: 3, profit_abs: -50 },
        { close_timestamp: 1, profit_abs: 100 },
        { close_timestamp: 2, profit_abs: -110 },
      ],
      1000,
      0,
    );
    expect(pts.map((p) => p.equity)).toEqual([1000, 1100, 990, 940]);
    expect(pts[2]?.drawdown).toBeCloseTo(990 / 1100 - 1);
    expect(pts[3]?.drawdown).toBeCloseTo(940 / 1100 - 1);
  });

  it('computes recovery needed and win concentration', () => {
    expect(recoveryNeeded(-0.2)).toBeCloseTo(0.25);
    expect(recoveryNeeded(0.1)).toBe(0);
    expect(
      largestWinShare([{ profit_abs: 30 }, { profit_abs: 10 }, { profit_abs: -5 }]),
    ).toBeCloseTo(0.75);
    expect(largestWinShare([{ profit_abs: -5 }])).toBeNull();
  });
});
