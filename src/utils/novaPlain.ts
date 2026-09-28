import { t } from '@/i18n';

/** Plain-language wording for Simple mode. */
export function plainExitReason(reason?: string | null): string {
  const r = (reason ?? '').toLowerCase();
  if (r === 'exit_signal' || r === 'sell_signal') return t('plain.exit.signal');
  if (r === 'manual_stop') return t('plain.exit.manualStop');
  if (r.includes('trailing')) return t('plain.exit.trailing');
  if (r.includes('stop_loss') || r === 'stoploss' || r.includes('stoploss'))
    return t('plain.exit.stop');
  if (r === 'roi') return t('plain.exit.roi');
  if (r.includes('force')) return t('plain.exit.force');
  if (r.includes('liquidation')) return t('plain.exit.liquidation');
  return reason ? reason.replaceAll('_', ' ') : t('common.unknown');
}

export function plainAgo(ts: number | null | undefined, now = Date.now()): string {
  if (!ts) return '';
  const min = Math.round((now - ts) / 60000);
  if (min < 1) return t('plain.ago.justNow');
  if (min < 60) return t('plain.ago.minutes', { n: min });
  const h = Math.round(min / 60);
  if (h < 24) return t('plain.ago.hours', h);
  const d = Math.round(h / 24);
  return t('plain.ago.days', d);
}

export function plainDuration(ms: number): string {
  const h = Math.round(ms / 3_600_000);
  if (h < 1) return t('plain.duration.underHour');
  if (h < 48) return t('plain.duration.hours', h);
  return t('plain.duration.days', Math.round(h / 24));
}

/**
 * Public name of a strategy class. The live strategy keeps its historical class name BreakoutRegimeKev (stored in
 * trades and configs); users see the name of our news model, Sentinel, instead.
 */
const STRATEGY_NAMES: Record<string, string> = {
  BreakoutRegimeKev: 'Breakout + Sentinel',
  BreakoutRegime: 'Breakout',
};
export function novaStrategyName(name?: string | null): string {
  if (!name) return '';
  return STRATEGY_NAMES[name] ?? name;
}
