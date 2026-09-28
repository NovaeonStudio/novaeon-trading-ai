import { t } from '@/i18n';

/**
 * Sentinel decision record (Novaeon Sentinel 9B, the AI news check), written by the strategy into trade custom data.
 * The custom-data key stays `kev` (the model's former name) so existing trades keep their records.
 */
export interface KevRecord {
  time: string;
  pair: string;
  decision: 'allow' | 'veto';
  reason?: 'no_news' | 'kev_unavailable' | string;
  headlines?: number;
  leverage?: number;
  leverage_reason?: string | null;
  /** What Sentinel would have picked while AI leverage was off or locked (the trade itself used 1×). */
  leverage_suggested?: number;
  p_negative?: number | null;
  outlook?: Record<string, number> | null;
  titles?: string[];
  /** Which model answered (e.g. novaeon-sentinel-9b, or the kev-9b base model as fallback). */
  model?: string;
}

/** True when the news model could not be reached (the trade went ahead at 1×). */
export function sentinelOffline(reason?: string | null): boolean {
  return !!reason && /^(kev|sentinel)_unavailable/.test(reason);
}

/** i18n keys (kev.reason.*) for the known reason codes; unknown codes are shown as plain words. */
const REASON_KEY: Record<string, string> = {
  no_news: 'kev.reason.noNews',
  neutral: 'kev.reason.neutral',
  clearly_positive: 'kev.reason.clearlyPositive',
  'clearly_positive+strong_btc': 'kev.reason.clearlyPositiveStrongBtc',
  ai_leverage_off: 'kev.reason.aiLeverageOff',
  ai_leverage_locked: 'kev.reason.aiLeverageLocked',
  manual: 'kev.reason.manual',
};

/** Plain words for a decision / leverage reason code (stored codes keep their historical names). */
export function sentinelReasonText(reason?: string | null): string {
  if (!reason) return '';
  if (sentinelOffline(reason)) return t('kev.reason.offline');
  const key = REASON_KEY[reason];
  return key ? t(key) : reason.replaceAll('_', ' ');
}
