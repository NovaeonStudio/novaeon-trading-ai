<script setup lang="ts">
/** Live timeline: entries, exits and Sentinel decisions, newest first. */
import type { ClosedTrade, Trade } from '@/types';
import { sentinelReasonText, type KevRecord } from './kev';

// `t` is the trade loop variable below, so the translator is aliased.
const { t: tr } = useI18n();

const props = defineProps<{
  openTrades: Trade[];
  closedTrades: ClosedTrade[];
  kev: Map<number, KevRecord>;
  limit?: number;
}>();

interface FeedEvent {
  key: string;
  ts: number;
  kind: 'entry' | 'win' | 'loss' | 'kev';
  title: string;
  detail: string;
}

const events = computed<FeedEvent[]>(() => {
  const out: FeedEvent[] = [];
  const all: (Trade | ClosedTrade)[] = [...props.openTrades, ...props.closedTrades];
  for (const t of all) {
    const coin = t.pair.split('/')[0];
    out.push({
      key: `e${t.trade_id}`,
      ts: t.open_timestamp,
      kind: 'entry',
      title: tr('widgets.feed.bought', { coin, leverage: t.leverage ?? 1 }),
      detail: tr('widgets.feed.boughtDetail', {
        price: formatPrice(t.open_rate, 6),
        stake: novaMoney(t.stake_amount, '', 0),
      }),
    });
    const k = props.kev.get(t.trade_id);
    if (k) {
      out.push({
        key: `k${t.trade_id}`,
        ts: t.open_timestamp - 1,
        kind: 'kev',
        title: tr('widgets.feed.kevChecked', { coin }),
        detail:
          k.reason === 'no_news'
            ? tr('widgets.feed.kevNoNews')
            : tr(
                'widgets.feed.kevDetail',
                {
                  risk: Math.round((k.p_negative ?? 0) * 100),
                  reason: sentinelReasonText(k.leverage_reason),
                },
                k.headlines ?? 0,
              ),
      });
    }
    if ('close_timestamp' in t && t.close_timestamp) {
      const win = (t.profit_abs ?? 0) >= 0;
      out.push({
        key: `x${t.trade_id}`,
        ts: t.close_timestamp,
        kind: win ? 'win' : 'loss',
        title: tr('widgets.feed.sold', { coin, pct: novaPct(t.profit_ratio, 2, true) }),
        detail: `${novaMoney(t.profit_abs, '', 2, true)} · ${(t.exit_reason ?? '').replaceAll('_', ' ')}`,
      });
    }
  }
  return out.sort((a, b) => b.ts - a.ts).slice(0, props.limit ?? 30);
});

const dot = {
  entry: 'bg-brand-400',
  win: 'bg-emerald-400',
  loss: 'bg-rose-400',
  kev: 'bg-secondary',
};
</script>

<template>
  <div v-if="!events.length" class="flex items-center gap-3 py-2">
    <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
      <UIcon name="i-mdi-timeline-clock-outline" class="size-5 text-muted" />
    </span>
    <p class="text-sm text-pretty text-muted">
      {{ $t('widgets.feed.empty') }}
    </p>
  </div>
  <ol v-else>
    <li v-for="(e, i) in events" :key="e.key" class="relative flex gap-3 pb-4 last:pb-0">
      <span
        v-if="i < events.length - 1"
        class="absolute top-4 bottom-0 left-1 w-px bg-accented"
        aria-hidden="true"
      />
      <span class="relative mt-1.5 size-2 shrink-0 rounded-full" :class="dot[e.kind]" />
      <div class="min-w-0 flex-1">
        <div class="flex items-baseline justify-between gap-2">
          <span class="truncate text-sm font-medium text-default">{{ e.title }}</span>
          <time class="nova-num shrink-0 text-xs text-dimmed">{{ novaAge(e.ts) }}</time>
        </div>
        <p
          class="nova-num mt-0.5 truncate text-xs text-muted"
          :class="{ 'nova-money': e.kind !== 'kev' }"
          :title="e.detail"
        >
          {{ e.detail }}
        </p>
      </div>
    </li>
  </ol>
</template>
