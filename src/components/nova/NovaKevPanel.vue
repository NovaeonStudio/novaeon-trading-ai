<script setup lang="ts">
import type { ClosedTrade, Trade } from '@/types';
import { I18nT } from 'vue-i18n';
import { sentinelReasonText, type KevRecord } from './kev';

/** Sentinel decision log (from trade custom data) + does its leverage choice pay off (closed trades by leverage). */
const props = defineProps<{
  records: Map<number, KevRecord>;
  openTrades: Trade[];
  closedTrades: ClosedTrade[];
  currency: string;
}>();
const { t: tr } = useI18n();

const rows = computed(() => {
  const all = [...props.openTrades, ...props.closedTrades];
  return all
    .filter((t) => props.records.has(t.trade_id))
    .map((t) => ({
      trade: t,
      kev: props.records.get(t.trade_id) as KevRecord,
      open: 'current_rate' in t && !t.close_timestamp,
    }))
    .sort((a, b) => (b.trade.open_timestamp ?? 0) - (a.trade.open_timestamp ?? 0))
    .slice(0, 8);
});

const cohorts = computed(() => {
  const groups = new Map<number, ClosedTrade[]>();
  for (const t of props.closedTrades) {
    const lev = t.leverage ?? 1;
    groups.set(lev, [...(groups.get(lev) ?? []), t]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a - b)
    .map(([lev, trades]) => {
      const e = edgeStats(trades);
      return {
        lev,
        n: trades.length,
        winRate: e.winRate,
        avg: trades.reduce((s, t) => s + (t.profit_ratio ?? 0), 0) / trades.length,
        total: trades.reduce((s, t) => s + (t.profit_abs ?? 0), 0),
      };
    });
});

const counts = computed(() => {
  const recs = [...props.records.values()];
  return {
    total: recs.length,
    news: recs.filter((r) => (r.headlines ?? 0) > 0).length,
    levered: recs.filter((r) => (r.leverage ?? 1) > 1).length,
  };
});

function outlookTop(k: KevRecord) {
  if (!k.outlook) return null;
  const [key, v] = Object.entries(k.outlook).sort((a, b) => b[1] - a[1])[0] ?? [];
  return key ? `${key.replaceAll('_', ' ')} ${Math.round((v as number) * 100)}%` : null;
}
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
    <div class="min-w-0">
      <div class="nova-num flex flex-wrap items-center gap-2 text-xs">
        <I18nT
          keypath="kev.panel.entriesChecked"
          :plural="counts.total"
          tag="span"
          scope="global"
          class="rounded-full bg-accented px-3 py-1 text-muted"
        >
          <template #n
            ><span class="font-semibold text-highlighted">{{ counts.total }}</span></template
          >
        </I18nT>
        <I18nT
          keypath="kev.panel.withNews"
          :plural="counts.news"
          tag="span"
          scope="global"
          class="rounded-full bg-accented px-3 py-1 text-muted"
        >
          <template #n
            ><span class="font-semibold text-highlighted">{{ counts.news }}</span></template
          >
        </I18nT>
        <I18nT
          keypath="kev.panel.aboveOneX"
          :plural="counts.levered"
          tag="span"
          scope="global"
          class="rounded-full bg-accented px-3 py-1 text-muted"
        >
          <template #n
            ><span class="font-semibold text-highlighted">{{ counts.levered }}</span></template
          >
        </I18nT>
      </div>
      <p class="mt-2 text-xs text-pretty text-dimmed">
        {{ tr('kev.panel.vetoNote') }}
      </p>
      <div v-if="!rows.length" class="mt-4 flex items-center gap-3">
        <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
          <UIcon name="i-mdi-newspaper-variant-outline" class="size-5 text-muted" />
        </span>
        <p class="text-sm text-pretty text-muted">
          {{ tr('kev.panel.empty') }}
        </p>
      </div>
      <ul v-else class="mt-2 flex flex-col">
        <li
          v-for="r in rows"
          :key="r.trade.trade_id"
          class="border-t border-default/50 py-3 first:border-t-0"
        >
          <div class="flex items-center justify-between gap-2">
            <div class="flex min-w-0 items-center gap-2">
              <span class="font-semibold text-highlighted">{{ r.trade.pair.split('/')[0] }}</span>
              <span
                class="nova-num shrink-0 rounded-full bg-brand-400/15 px-2 py-0.5 text-xs font-semibold text-brand-600 dark:text-brand-300"
                >{{ r.kev.leverage ?? 1 }}x</span
              >
              <span class="truncate text-xs text-muted">{{
                sentinelReasonText(r.kev.leverage_reason ?? r.kev.reason)
              }}</span>
            </div>
            <span
              class="nova-num shrink-0 text-sm font-medium"
              :class="(r.trade.profit_ratio ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
            >
              {{ novaPct(r.trade.profit_ratio, 2, true)
              }}<span class="text-xs font-normal text-dimmed">{{
                r.open ? ` ${tr('kev.panel.open')}` : ''
              }}</span>
            </span>
          </div>
          <div
            class="nova-num mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-dimmed"
          >
            <span>{{ tr('kev.panel.headlines', r.kev.headlines ?? 0) }}</span>
            <I18nT
              v-if="r.kev.p_negative !== null && r.kev.p_negative !== undefined"
              keypath="kev.panel.risk"
              tag="span"
              scope="global"
            >
              <template #pct
                ><span class="text-default"
                  >{{ Math.round(r.kev.p_negative * 100) }}%</span
                ></template
              >
            </I18nT>
            <span v-if="outlookTop(r.kev)">{{ outlookTop(r.kev) }}</span>
          </div>
          <p
            v-if="r.kev.titles?.length"
            class="mt-1 truncate text-xs text-muted"
            :title="r.kev.titles.join('\n')"
          >
            “{{ r.kev.titles[0] }}”
          </p>
        </li>
      </ul>
    </div>
    <div class="min-w-0">
      <h3 class="text-sm font-semibold text-highlighted">{{ tr('kev.panel.payTitle') }}</h3>
      <p class="mt-1 text-xs text-pretty text-muted">
        {{ tr('kev.panel.payHint') }}
      </p>
      <p v-if="!cohorts.length" class="mt-3 text-sm text-muted">
        {{ tr('kev.panel.payEmpty') }}
      </p>
      <div class="mt-3 flex flex-col gap-2">
        <div v-for="c in cohorts" :key="c.lev" class="nova-tile p-3">
          <div class="flex items-baseline justify-between gap-2">
            <span class="nova-num text-base font-semibold text-highlighted">{{ c.lev }}x</span>
            <span class="nova-num text-xs text-muted">{{ tr('kev.panel.trades', c.n) }}</span>
          </div>
          <div class="nova-num mt-1 grid grid-cols-3 gap-2 text-xs">
            <span class="text-muted">{{
              tr('kev.panel.win', { pct: novaPct(c.winRate, 0) })
            }}</span>
            <span :class="c.avg >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{
              tr('kev.panel.avg', { pct: novaPct(c.avg, 2, true) })
            }}</span>
            <span
              class="nova-money text-right"
              :class="c.total >= 0 ? 'text-emerald-400' : 'text-rose-400'"
              >{{ novaMoney(c.total, '', 2, true) }}</span
            >
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
