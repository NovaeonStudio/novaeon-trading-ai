import { intlLocale, t as tr } from '@/i18n';
/**
 * Position math for the trade chart, the stop editor and the buy dialogs. Pure functions over bot API data,
 * unit-tested in tests/unit/novaPosition.spec.ts. Long positions (the strategy is long-only); money in stake
 * currency, ratios as fractions (0.05 = 5 %), ratios on the margin (leverage included), like the engine.
 */
import type { ClosedTrade, PairHistory, Trade } from '@/types';

type AnyTrade = Trade | ClosedTrade;

/** One candle plus the strategy's breakout levels (20-candle high / 10-candle low, shifted by one). */
export interface NovaCandle {
  ts: number;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
  /** Breakout level: highest high of the previous 20 hours (strategy column hi20). */
  hi20: number | null;
  /** Exit trigger: lowest low of the previous 10 hours (strategy column lo10). */
  lo10: number | null;
  /** True for the synthetic candle that is still forming (last closed candle → current price). */
  live?: boolean;
}

/** Highest high of the previous `hiN` candles and lowest low of the previous `loN` (strategy: shift(1)). */
export function donchianLevels(candles: NovaCandle[], hiN = 20, loN = 10): NovaCandle[] {
  return candles.map((c, i) => {
    const hiWin = i >= hiN ? candles.slice(i - hiN, i) : null;
    const loWin = i >= loN ? candles.slice(i - loN, i) : null;
    return {
      ...c,
      hi20: hiWin ? Math.max(...hiWin.map((x) => x.h)) : null,
      lo10: loWin ? Math.min(...loWin.map((x) => x.l)) : null,
    };
  });
}

/**
 * Candles from the engine's pair_candles response. Uses the strategy's own hi20 / lo10 columns when present,
 * otherwise computes them the same way.
 */
export function positionCandles(ph: PairHistory | null | undefined): NovaCandle[] {
  // The strategy's windows are in hours: 20 / 10 hours = 80 / 40 candles on 15m.
  const cph = ph?.timeframe_ms ? Math.max(1, Math.round(3_600_000 / ph.timeframe_ms)) : 1;
  if (!ph?.data?.length) return [];
  const col = (name: string) => ph.columns.indexOf(name);
  const [iTs, iO, iH, iL, iC, iV, iHi, iLo] = [
    '__date_ts',
    'open',
    'high',
    'low',
    'close',
    'volume',
    'hi20',
    'lo10',
  ].map(col) as number[];
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  const rows: NovaCandle[] = [];
  for (const r of ph.data) {
    const ts = num(r[iTs!]);
    const o = num(r[iO!]);
    const h = num(r[iH!]);
    const l = num(r[iL!]);
    const c = num(r[iC!]);
    if (ts === null || o === null || h === null || l === null || c === null) continue;
    rows.push({
      ts,
      o,
      h,
      l,
      c,
      v: num(r[iV!]) ?? 0,
      hi20: iHi! >= 0 ? num(r[iHi!]) : null,
      lo10: iLo! >= 0 ? num(r[iLo!]) : null,
    });
  }
  return iHi! >= 0 && iLo! >= 0 ? rows : donchianLevels(rows, 20 * cph, 10 * cph);
}

/**
 * Append the forming candle (last close → current price) so the chart ends at "now". Its levels are the ones
 * the strategy checks at this candle's close.
 */
export function withLiveCandle(
  candles: NovaCandle[],
  tfMs: number,
  price: number | null | undefined,
  now = Date.now(),
): NovaCandle[] {
  const last = candles[candles.length - 1];
  if (!last || !price || !tfMs) return candles;
  const ts = last.ts + tfMs;
  if (ts > now) return candles;
  const withLive = [
    ...candles,
    {
      ts,
      o: last.c,
      h: Math.max(last.c, price),
      l: Math.min(last.c, price),
      c: price,
      v: 0,
      hi20: null,
      lo10: null,
      live: true,
    },
  ];
  // Windows in hours, like the strategy: 20 / 10 hours of candles of this size.
  const cph = Math.max(1, Math.round(3_600_000 / tfMs));
  const levels = donchianLevels(withLive.slice(-(20 * cph + 1)), 20 * cph, 10 * cph);
  const lv = levels[levels.length - 1]!;
  withLive[withLive.length - 1] = {
    ...withLive[withLive.length - 1]!,
    hi20: lv.hi20,
    lo10: lv.lo10,
  };
  return withLive;
}

/**
 * Bigger candles from smaller ones (UTC-aligned buckets, like the exchange). The breakout levels stay the
 * strategy's own: each bucket carries the levels of its last base candle.
 */
export function aggregateCandles(candles: NovaCandle[], tfMs: number): NovaCandle[] {
  const out: NovaCandle[] = [];
  for (const c of candles) {
    const ts = Math.floor(c.ts / tfMs) * tfMs;
    const cur = out[out.length - 1];
    if (cur && cur.ts === ts) {
      cur.h = Math.max(cur.h, c.h);
      cur.l = Math.min(cur.l, c.l);
      cur.c = c.c;
      cur.v += c.v;
      cur.hi20 = c.hi20;
      cur.lo10 = c.lo10;
      cur.live = cur.live || c.live;
    } else out.push({ ...c, ts });
  }
  return out;
}

/** Open value (what was paid incl. the entry fee) of the coins still held. */
function openValue(t: AnyTrade): number {
  return t.amount * t.open_rate * (1 + (t.fee_open ?? 0));
}

function closeFee(t: AnyTrade): number {
  return t.fee_close ?? t.fee_open ?? 0;
}

/** Price at which selling the coins still held returns exactly what they cost (entry + exit fees, funding). */
export function breakEvenPrice(t: AnyTrade): number | null {
  if (!t.amount || !t.open_rate) return null;
  return (openValue(t) - (t.funding_fees ?? 0)) / (t.amount * (1 - closeFee(t)));
}

/** Result of selling the coins still held at `price`: money and ratio on the margin (after fees). */
export function profitAtPrice(t: AnyTrade, price: number): { abs: number; ratio: number } {
  const ov = openValue(t);
  const abs = t.amount * price * (1 - closeFee(t)) - ov + (t.funding_fees ?? 0);
  const margin = ov / (t.leverage || 1);
  return { abs, ratio: margin ? abs / margin : 0 };
}

/** Inverse of profitAtPrice: the price at which the result on the margin is `ratio`. */
export function priceForProfit(t: AnyTrade, ratio: number): number | null {
  if (!t.amount || !t.open_rate) return null;
  const ov = openValue(t);
  const abs = (ratio * ov) / (t.leverage || 1);
  return (abs + ov - (t.funding_fees ?? 0)) / (t.amount * (1 - closeFee(t)));
}

export type NovaFillKind = 'entry' | 'add' | 'partial' | 'exit';

export interface NovaFill {
  ts: number;
  price: number;
  amount: number;
  cost: number;
  side: 'buy' | 'sell';
  kind: NovaFillKind;
  /** Order tag, e.g. "manual" for buys from this app. */
  tag: string | null;
  /** Sold by the stop order. */
  stop: boolean;
}

/** Every filled order of a trade, oldest first: first buy, added buys, partial sells, final sell. */
export function tradeFills(t: AnyTrade): NovaFill[] {
  const orders = (t.orders ?? [])
    .filter((o) => (o.filled ?? o.amount) > 0 && o.order_filled_timestamp && o.safe_price)
    .sort((a, b) => (a.order_filled_timestamp ?? 0) - (b.order_filled_timestamp ?? 0));
  const out: NovaFill[] = [];
  let seenEntry = false;
  orders.forEach((o, i) => {
    const amount = o.filled ?? o.amount;
    // The engine's API may leave ft_is_entry empty: fall back to the order side (long: buy = entry).
    const isEntry = o.ft_is_entry ?? o.ft_order_side === (t.is_short ? 'sell' : 'buy');
    let kind: NovaFillKind;
    if (isEntry) {
      kind = seenEntry ? 'add' : 'entry';
      seenEntry = true;
    } else kind = !t.is_open && i === orders.length - 1 ? 'exit' : 'partial';
    out.push({
      ts: o.order_filled_timestamp!,
      price: o.safe_price,
      amount,
      cost: amount * o.safe_price,
      side: isEntry ? 'buy' : 'sell',
      kind,
      tag: o.ft_order_tag ?? null,
      stop: o.ft_order_side === 'stoploss' || (kind === 'exit' && isStopExit(t.exit_reason)),
    });
  });
  return out;
}

/** Exit reasons that mean "a stop sold it" (engine stop, raised stop, manual stop, exchange stop). */
export function isStopExit(reason: string | null | undefined): boolean {
  const r = (reason ?? '').toLowerCase();
  return r.includes('stop_loss') || r.includes('stoploss') || r === 'manual_stop';
}

/** Short exit-reason label for Pro views (the new control-service reasons included). */
export function novaExitReason(reason: string | null | undefined): string {
  const r = (reason ?? '').toLowerCase();
  if (!r) return '–';
  if (r === 'trailing_stop_loss') return tr('exit.reason.raisedStop');
  if (r === 'manual_stop') return tr('exit.reason.manualStop');
  if (r === 'stop_loss' || r === 'stoploss_on_exchange') return tr('exit.reason.stopLoss');
  if (r === 'exit_signal') return tr('exit.reason.exitSignal');
  if (r === 'force_exit') return tr('exit.reason.forceExit');
  if (r === 'roi') return tr('exit.reason.roi');
  return (r.charAt(0).toUpperCase() + r.slice(1)).replaceAll('_', ' ');
}

export interface NovaStopCheck {
  ok: boolean;
  /** Plain reason when not ok. */
  reason: string | null;
}

/** Client-side version of the engine rule: a stop can only move up, and must stay below the current price. */
export function checkNewStop(
  price: number | null | undefined,
  currentStop: number | null | undefined,
  currentPrice: number | null | undefined,
  liquidation?: number | null,
): NovaStopCheck {
  if (!price || !Number.isFinite(price) || price <= 0)
    return { ok: false, reason: tr('position.stopCheck.enterPrice') };
  if (currentPrice && price >= currentPrice)
    return {
      ok: false,
      reason: tr('position.stopCheck.atOrAbovePrice'),
    };
  if (liquidation && price <= liquidation)
    return { ok: false, reason: tr('position.stopCheck.aboveLiquidation') };
  if (currentStop && price <= currentStop)
    return {
      ok: false,
      reason: tr('position.stopCheck.onlyUp'),
    };
  return { ok: true, reason: null };
}

/** Readable price: about 5 significant digits (100.23, 65,012, 0.012345), thousands separators, no float noise. */
export function novaPriceText(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '–';
  const mag = v === 0 ? 0 : Math.floor(Math.log10(Math.abs(v)));
  const decimals = Math.min(8, Math.max(0, 4 - mag));
  return v.toLocaleString(intlLocale(), { maximumFractionDigits: decimals });
}
