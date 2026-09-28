import { intlLocale } from '@/i18n';

/** Compact number formatting for the NovaeonTradingAI Command Center. */
export function novaMoney(
  value: number | null | undefined,
  currency = '',
  decimals = 2,
  signed = false,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '–';
  const abs = Math.abs(value).toLocaleString(intlLocale(), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  const sign = value < 0 ? '−' : signed && value > 0 ? '+' : '';
  return `${sign}${abs}${currency ? ` ${currency}` : ''}`;
}

export function novaPct(ratio: number | null | undefined, decimals = 1, signed = false): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '–';
  const v = ratio * 100;
  const sign = v < 0 ? '−' : signed && v > 0 ? '+' : '';
  const num = Math.abs(v).toLocaleString(intlLocale(), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: false,
  });
  return `${sign}${num}%`;
}

export function novaNum(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  return value.toLocaleString(intlLocale(), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: false,
  });
}

/** Number with up to `maxDecimals` decimals (no trailing zeros, no grouping) in the app language, e.g. prices. */
export function novaPlainNumber(value: number | null | undefined, maxDecimals = 5): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'N/A';
  return value.toLocaleString(intlLocale(), {
    maximumFractionDigits: maxDecimals,
    useGrouping: false,
  });
}

export function novaTone(value: number | null | undefined): 'pos' | 'neg' | 'neutral' {
  if (!value) return 'neutral';
  return value > 0 ? 'pos' : 'neg';
}

export function novaAge(fromMs: number | null | undefined, nowMs = Date.now()): string {
  if (!fromMs) return '–';
  const s = Math.max(0, Math.round((nowMs - fromMs) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ${m % 60}m`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}
