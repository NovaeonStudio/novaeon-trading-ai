import { describe, expect, it } from 'vitest';
import {
  aggregateCandles,
  breakEvenPrice,
  checkNewStop,
  donchianLevels,
  isStopExit,
  novaExitReason,
  novaPriceText,
  positionCandles,
  priceForProfit,
  profitAtPrice,
  tradeFills,
  withLiveCandle,
  type NovaCandle,
} from '@/utils/novaPosition';
import type { Order, Trade } from '@/types';

const H = 3_600_000;
const candle = (i: number, o: number, h: number, l: number, c: number): NovaCandle => ({
  ts: i * H,
  o,
  h,
  l,
  c,
  v: 1,
  hi20: null,
  lo10: null,
});
const trade = (over: Partial<Trade> = {}) =>
  ({
    trade_id: 1,
    pair: 'HYPE/USDC:USDC',
    is_open: true,
    amount: 2,
    open_rate: 100,
    fee_open: 0.001,
    fee_close: 0.001,
    leverage: 2,
    funding_fees: 0,
    orders: [],
    ...over,
  }) as unknown as Trade;
const order = (over: Partial<Order>) =>
  ({
    amount: 1,
    filled: 1,
    safe_price: 100,
    ft_order_side: 'buy',
    ft_is_entry: true,
    order_filled_timestamp: 1,
    ...over,
  }) as Order;

describe('donchianLevels', () => {
  it('uses the previous candles only (shift by one), like the strategy', () => {
    const rows = Array.from({ length: 12 }, (_, i) => candle(i, 10, 10 + i, 10 - i, 10));
    const out = donchianLevels(rows, 3, 2);
    expect(out[2]!.hi20).toBeNull();
    expect(out[3]!.hi20).toBe(12); // max high of candles 0..2
    expect(out[3]!.lo10).toBe(8); // min low of candles 1..2
  });
});

describe('withLiveCandle / aggregateCandles', () => {
  it('appends the forming candle ending at the current price with its levels', () => {
    const rows = Array.from({ length: 25 }, (_, i) =>
      candle(i, 100, 101, 99 - (i === 20 ? 1 : 0), 100),
    );
    const out = withLiveCandle(rows, H, 103, 30 * H);
    const live = out[out.length - 1]!;
    expect(live.live).toBe(true);
    expect(live.o).toBe(100);
    expect(live.c).toBe(103);
    expect(live.lo10).toBe(98);
    expect(live.hi20).toBe(101);
  });
  it('does not add a candle that would start in the future', () => {
    const rows = [candle(0, 1, 1, 1, 1)];
    expect(withLiveCandle(rows, H, 2, H / 2)).toHaveLength(1);
  });
  it('builds 4h candles from 1h candles', () => {
    const rows = [candle(0, 1, 5, 0.5, 2), candle(1, 2, 3, 1, 3), candle(4, 3, 4, 2, 4)];
    const out = aggregateCandles(rows, 4 * H);
    expect(out).toHaveLength(2);
    expect(out[0]).toMatchObject({ o: 1, h: 5, l: 0.5, c: 3, v: 2 });
  });
});

describe('position math', () => {
  it('break-even covers entry and exit fees', () => {
    const t = trade();
    const be = breakEvenPrice(t)!;
    expect(be).toBeCloseTo((100 * 1.001) / 0.999, 8);
    expect(profitAtPrice(t, be).abs).toBeCloseTo(0, 8);
  });
  it('profit ratio is on the margin (leverage included)', () => {
    const t = trade({ fee_open: 0, fee_close: 0 });
    expect(profitAtPrice(t, 101).ratio).toBeCloseTo(0.02, 10);
    expect(profitAtPrice(t, 101).abs).toBeCloseTo(2, 10);
    expect(priceForProfit(t, 0.02)).toBeCloseTo(101, 10);
  });
});

describe('tradeFills', () => {
  it('labels first buy, added buy, partial sell and final stop exit', () => {
    const t = trade({
      is_open: false,
      exit_reason: 'trailing_stop_loss',
      orders: [
        order({ order_filled_timestamp: 1 }),
        order({ order_filled_timestamp: 2, ft_order_tag: 'manual', safe_price: 102 }),
        order({ order_filled_timestamp: 3, ft_is_entry: false, ft_order_side: 'sell' }),
        order({ order_filled_timestamp: 4, ft_is_entry: false, ft_order_side: 'sell' }),
        order({ order_filled_timestamp: 5, filled: 0 }),
      ],
    });
    const f = tradeFills(t);
    expect(f.map((x) => x.kind)).toEqual(['entry', 'add', 'partial', 'exit']);
    expect(f[1]!.tag).toBe('manual');
    expect(f[3]!.stop).toBe(true);
    expect(f[2]!.stop).toBe(false);
  });
});

describe('checkNewStop', () => {
  it('only lets a stop move up, below the price and above liquidation', () => {
    expect(checkNewStop(97, 95, 101).ok).toBe(true);
    expect(checkNewStop(94, 95, 101).ok).toBe(false);
    expect(checkNewStop(101, 95, 101).ok).toBe(false);
    expect(checkNewStop(50, null, 101, 51).ok).toBe(false);
    expect(checkNewStop(null, 95, 101).ok).toBe(false);
  });
});

describe('labels', () => {
  it('names the new exit reasons', () => {
    expect(novaExitReason('manual_stop')).toMatch(/Manual stop/);
    expect(novaExitReason('trailing_stop_loss')).toBe('Raised stop hit');
    expect(isStopExit('manual_stop')).toBe(true);
    expect(isStopExit('exit_signal')).toBe(false);
  });
  it('formats prices with about five significant digits', () => {
    expect(novaPriceText(100.233333)).toBe('100.23');
    expect(novaPriceText(65012.7)).toBe('65,013');
    expect(novaPriceText(0.0123456)).toBe('0.012346');
    expect(novaPriceText(null)).toBe('–');
  });
});

describe('strategy windows in hours (15m candles)', () => {
  const M15 = 900_000;
  // 100 candles: lows fall 1 per candle, so the 10-hour low (40 candles) is clearly below the 2.5-hour low.
  const rows = Array.from({ length: 100 }, (_, i) => [
    i * M15,
    200 - i,
    201 - i,
    199 - i,
    200 - i,
    1,
  ]);
  const ph = {
    timeframe_ms: M15,
    columns: ['__date_ts', 'open', 'high', 'low', 'close', 'volume'],
    data: rows,
  } as unknown as Parameters<typeof positionCandles>[0];

  it('computes lo10 / hi20 over 10 / 20 hours when the engine sends no level columns', () => {
    const out = positionCandles(ph);
    const last = out[out.length - 1]!;
    // lows of candles 59..98 (previous 40): min = 199 - 98 = 101; highs of 19..98 (previous 80): max = 201 - 19 = 182
    expect(last.lo10).toBe(101);
    expect(last.hi20).toBe(182);
  });

  it('gives the forming candle the 10-hour low too', () => {
    const base = positionCandles(ph);
    const live = withLiveCandle(base, M15, 50, base[base.length - 1]!.ts + 2 * M15);
    // previous 40 candles for the live one: 60..99 -> min low = 199 - 99 = 100
    expect(live[live.length - 1]!.lo10).toBe(100);
  });
});
