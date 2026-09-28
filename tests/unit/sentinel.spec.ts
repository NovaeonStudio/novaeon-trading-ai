import { describe, expect, it } from 'vitest';
import { sentinelOffline, sentinelReasonText } from '@/components/nova/kev';

describe('sentinel reason codes', () => {
  it('treats the old and the new "unavailable" codes as offline', () => {
    expect(sentinelOffline('kev_unavailable')).toBe(true);
    expect(sentinelOffline('kev_unavailable: 127.0.0.1:8010: timed out')).toBe(true);
    expect(sentinelOffline('sentinel_unavailable')).toBe(true);
    expect(sentinelOffline('no_news')).toBe(false);
    expect(sentinelOffline(null)).toBe(false);
  });

  it('never shows the former model name to users', () => {
    expect(sentinelReasonText('kev_unavailable')).toBe('Sentinel offline');
    expect(sentinelReasonText('ai_leverage_off')).toBe('AI leverage off, 1×');
    expect(sentinelReasonText('ai_leverage_locked')).toContain('locked');
    expect(sentinelReasonText('clearly_positive+strong_btc')).toBe(
      'clearly good news and strong Bitcoin',
    );
    expect(sentinelReasonText('some_new_code')).toBe('some new code');
    expect(sentinelReasonText(undefined)).toBe('');
  });
});

describe('strategy display names', () => {
  it('shows the live strategy under its public name', async () => {
    const { novaStrategyName } = await import('@/utils/novaPlain');
    expect(novaStrategyName('BreakoutRegimeKev')).toBe('Breakout + Sentinel');
    expect(novaStrategyName('SampleStrategy')).toBe('SampleStrategy');
    expect(novaStrategyName(null)).toBe('');
  });
});
