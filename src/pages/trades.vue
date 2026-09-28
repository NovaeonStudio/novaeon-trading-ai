<script setup lang="ts">
/** Trades: closed-trade history with filters, summary, exit-reason breakdown, CSV export and detail drawer. */
import type { ClosedTrade } from '@/types';
import { edgeStats, excursion } from '@/utils/novaMetrics';

const { bot } = useNovaLive();
const { simple } = useNovaMode();
const { t: tr } = useI18n();
const currency = computed(() => bot.value?.botState?.stake_currency ?? '');

const query = ref('');
const result = ref<'all' | 'win' | 'loss'>('all');
const reason = ref<string>('all');
const selected = ref<ClosedTrade | null>(null);
const drawerOpen = computed({
  get: () => selected.value !== null,
  set: (v) => {
    if (!v) selected.value = null;
  },
});

const all = computed<ClosedTrade[]>(() =>
  [...(bot.value?.closedTrades ?? [])].sort((a, b) => b.close_timestamp - a.close_timestamp),
);
const reasons = computed(() => [
  'all',
  ...new Set(all.value.map((t) => t.exit_reason ?? 'unknown')),
]);
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase();
  return all.value.filter(
    (t) =>
      (!q || t.pair.toLowerCase().includes(q)) &&
      (result.value === 'all' ||
        (result.value === 'win' ? (t.profit_abs ?? 0) > 0 : (t.profit_abs ?? 0) <= 0)) &&
      (reason.value === 'all' || (t.exit_reason ?? 'unknown') === reason.value),
  );
});

const edge = computed(() => edgeStats(filtered.value));
const total = computed(() => filtered.value.reduce((s, t) => s + (t.profit_abs ?? 0), 0));
const avgDuration = computed(() => {
  const d = filtered.value.map((t) => t.close_timestamp - t.open_timestamp);
  return d.length ? d.reduce((s, v) => s + v, 0) / d.length : null;
});
const reasonLabel = (r: string) =>
  r === 'all' ? tr('trades.filter.allReasons') : novaExitReason(r);
const reasonItems = computed(() => reasons.value.map((r) => ({ label: reasonLabel(r), value: r })));
const byReason = computed(() => {
  const m = new Map<string, { n: number; profit: number }>();
  for (const t of all.value) {
    const k = t.exit_reason ?? 'unknown';
    const e = m.get(k) ?? { n: 0, profit: 0 };
    e.n += 1;
    e.profit += t.profit_abs ?? 0;
    m.set(k, e);
  }
  return [...m.entries()].sort((a, b) => b[1].n - a[1].n);
});

function exportCsv() {
  const head = [
    'id',
    'pair',
    'leverage',
    'open',
    'close',
    'entry',
    'exit',
    'profit_pct',
    'profit_abs',
    'exit_reason',
    'mfe_pct',
    'mae_pct',
  ];
  const lines = filtered.value.map((t) => {
    const e = excursion(t);
    return [
      t.trade_id,
      t.pair,
      t.leverage ?? 1,
      t.open_date,
      t.close_date,
      t.open_rate,
      t.close_rate,
      ((t.profit_ratio ?? 0) * 100).toFixed(3),
      (t.profit_abs ?? 0).toFixed(4),
      t.exit_reason,
      e ? (e.mfe * 100).toFixed(3) : '',
      e ? (e.mae * 100).toFixed(3) : '',
    ].join(',');
  });
  const blob = new Blob([[head.join(','), ...lines].join('\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `novaeon-trading-ai-trades-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}
</script>

<template>
  <div
    class="mx-auto flex flex-col text-left"
    :class="
      simple
        ? 'w-full max-w-6xl gap-6 px-4 py-6 sm:px-6 sm:py-8'
        : 'w-full max-w-[1680px] gap-6 px-4 py-6 sm:px-6 sm:py-8'
    "
  >
    <!-- Simple mode: calm header with three plain numbers -->
    <section v-if="simple" class="rounded-2xl border border-default/70 bg-elevated/60 p-6">
      <h1 class="text-2xl font-semibold text-highlighted">{{ tr('trades.simple.title') }}</h1>
      <p class="mt-1 text-sm text-muted">
        {{ tr('trades.simple.count', all.length) }}
      </p>
      <dl class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div class="col-span-2 rounded-xl bg-default/50 p-4 sm:col-span-1">
          <dt class="text-xs text-muted">{{ tr('trades.simple.profit') }}</dt>
          <dd
            class="nova-num nova-money mt-1 text-2xl font-semibold"
            :class="total >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ novaMoney(total, currency, 2, true) }}
          </dd>
        </div>
        <div class="rounded-xl bg-default/50 p-4">
          <dt class="text-xs text-muted">{{ tr('trades.simple.soldWithProfit') }}</dt>
          <dd class="nova-num mt-1 text-2xl font-semibold text-highlighted">
            {{ tr('trades.simple.winsOf', { wins: edge.wins, total: edge.wins + edge.losses }) }}
          </dd>
        </div>
        <div class="rounded-xl bg-default/50 p-4">
          <dt class="text-xs text-muted">{{ tr('trades.simple.usuallyHeld') }}</dt>
          <dd class="mt-1 text-2xl font-semibold text-highlighted">
            {{ avgDuration !== null ? plainDuration(avgDuration) : '–' }}
          </dd>
        </div>
      </dl>
    </section>

    <!-- Pro: title, the headline numbers as tiles, export -->
    <section v-else class="nova-panel p-4 sm:p-6">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="min-w-0">
          <h1 class="text-2xl font-semibold text-balance text-highlighted">
            {{ tr('trades.pro.title') }}
          </h1>
          <p class="mt-1 text-sm text-muted">
            {{ tr('trades.pro.shown', { shown: filtered.length, total: all.length }) }}
          </p>
        </div>
        <UButton
          color="neutral"
          variant="outline"
          icon="i-mdi-download"
          class="rounded-xl"
          :disabled="!filtered.length"
          @click="exportCsv"
          >{{ tr('trades.pro.exportCsv') }}</UButton
        >
      </div>
      <div class="mt-6 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <NovaStat
          class="nova-tile col-span-2 p-4 sm:col-span-1"
          :label="tr('trades.pro.realized')"
          :value="novaMoney(total, currency, 2, true)"
          :tone="novaTone(total)"
          money
        />
        <NovaStat
          class="nova-tile p-4"
          :label="tr('trades.pro.winRate')"
          :value="novaPct(edge.winRate, 0)"
          :sub="tr('trades.pro.wonLost', { won: edge.wins, lost: edge.losses })"
        />
        <NovaStat
          class="nova-tile p-4"
          :label="tr('trades.pro.avgWinLoss')"
          :value="`${novaMoney(edge.avgWin, '', 2)} / ${novaMoney(edge.avgLoss, '', 2)}`"
          :sub="
            edge.payoff !== null
              ? tr('trades.pro.payoff', { x: novaNum(edge.payoff, 2) })
              : undefined
          "
          money
        />
        <NovaStat
          class="nova-tile col-span-2 p-4 sm:col-span-1"
          :label="tr('trades.pro.avgDuration')"
          :value="avgDuration !== null ? novaAge(Date.now() - avgDuration) : '–'"
        />
      </div>
    </section>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_18rem]">
      <div class="nova-panel min-w-0" :class="simple ? 'p-2' : 'p-4 sm:p-6'">
        <!-- Pro filters: one row that wraps -->
        <div v-if="!simple" class="mb-4 flex flex-wrap items-center gap-3">
          <UInput
            v-model="query"
            icon="i-mdi-magnify"
            :placeholder="tr('trades.filter.pairPlaceholder')"
            class="w-full sm:w-56"
            :ui="{ base: 'rounded-xl' }"
          />
          <div class="nova-seg text-sm" role="group" :aria-label="tr('trades.filter.resultAria')">
            <button
              v-for="opt in ['all', 'win', 'loss'] as const"
              :key="opt"
              type="button"
              :aria-pressed="result === opt"
              @click="result = opt"
            >
              {{
                opt === 'all'
                  ? tr('common.all')
                  : opt === 'win'
                    ? tr('trades.filter.winners')
                    : tr('trades.filter.losers')
              }}
            </button>
          </div>
          <USelect
            v-model="reason"
            :items="reasonItems"
            class="w-full sm:w-auto sm:min-w-48"
            :ui="{ base: 'rounded-xl' }"
            :aria-label="tr('trades.filter.reasonAria')"
          />
        </div>
        <div v-else class="mb-3 flex flex-wrap items-center gap-2 px-2 pt-2">
          <UInput
            v-model="query"
            size="lg"
            icon="i-mdi-magnify"
            :placeholder="tr('trades.filter.coinPlaceholder')"
            class="w-full sm:w-56"
          />
          <div class="flex rounded-full border border-default/70 p-0.5 text-sm">
            <button
              v-for="opt in ['all', 'win', 'loss'] as const"
              :key="opt"
              type="button"
              class="rounded-full px-4 py-2 font-medium capitalize"
              :class="result === opt ? 'bg-brand-400/15 text-brand-300' : 'text-muted'"
              @click="result = opt"
            >
              {{
                opt === 'all'
                  ? tr('common.all')
                  : opt === 'win'
                    ? tr('trades.filter.winners')
                    : tr('trades.filter.losers')
              }}
            </button>
          </div>
          <button
            v-if="reason !== 'all'"
            type="button"
            class="inline-flex items-center gap-1 rounded-full bg-brand-400/15 px-4 py-2 text-sm font-medium text-brand-300"
            :aria-label="tr('trades.filter.clearReasonAria', { reason: plainExitReason(reason) })"
            @click="reason = 'all'"
          >
            {{ plainExitReason(reason) }}<UIcon name="i-mdi-close" class="size-4" />
          </button>
        </div>
        <!-- Simple mode: one tappable row per sold coin -->
        <ul v-if="simple">
          <li v-for="t in filtered" :key="t.trade_id">
            <button
              type="button"
              class="flex min-h-16 w-full items-center gap-3 rounded-lg px-4 py-3 text-left transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
              @click="selected = t"
            >
              <span
                class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented text-xs font-semibold text-highlighted"
                >{{ t.pair.split('/')[0].slice(0, 4) }}</span
              >
              <span class="min-w-0 flex-1">
                <span class="block truncate font-semibold text-highlighted">{{
                  t.pair.split('/')[0]
                }}</span>
                <span class="block text-xs text-muted">{{
                  tr('trades.simple.rowMeta', {
                    ago: plainAgo(t.close_timestamp),
                    duration: plainDuration(t.close_timestamp - t.open_timestamp),
                  })
                }}</span>
                <span class="block truncate text-xs text-dimmed">{{
                  plainExitReason(t.exit_reason)
                }}</span>
              </span>
              <span class="nova-num text-right">
                <span
                  class="block text-base font-semibold"
                  :class="(t.profit_abs ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
                  >{{ novaPct(t.profit_ratio, 1, true) }}</span
                >
                <span
                  class="nova-money block text-xs"
                  :class="(t.profit_abs ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
                  >{{ novaMoney(t.profit_abs, currency, 2, true) }}</span
                >
              </span>
            </button>
          </li>
          <li v-if="!filtered.length" class="px-4 py-6 text-center text-sm text-muted">
            {{ all.length ? tr('trades.simple.noMatch') : tr('trades.simple.empty') }}
          </li>
        </ul>
        <div v-else class="-mx-4 overflow-x-auto sm:-mx-6">
          <table class="nova-num w-full min-w-[44rem] text-sm">
            <thead>
              <tr class="text-left text-xs font-medium text-muted">
                <th class="py-2 ps-4 pe-3 font-medium sm:ps-6">{{ tr('trades.table.pair') }}</th>
                <th class="py-2 pe-3 font-medium">{{ tr('trades.table.closed') }}</th>
                <th class="py-2 pe-3 text-right font-medium">{{ tr('trades.table.held') }}</th>
                <th class="py-2 pe-3 text-right font-medium">{{ tr('trades.table.entryExit') }}</th>
                <th class="py-2 pe-3 text-right font-medium">{{ tr('trades.table.pnl') }}</th>
                <th class="py-2 pe-3 text-right font-medium">{{ tr('trades.table.bestRun') }}</th>
                <th class="py-2 pe-4 font-medium sm:pe-6">{{ tr('trades.table.exit') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="t in filtered"
                :key="t.trade_id"
                class="cursor-pointer border-t border-default/50 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40 focus:outline-none focus-visible:bg-accented/40 focus-visible:ring-2 focus-visible:ring-brand-400/60 focus-visible:ring-inset"
                tabindex="0"
                @click="selected = t"
                @keydown.enter="selected = t"
              >
                <td class="py-2 ps-4 pe-3 sm:ps-6">
                  <span class="inline-flex items-center gap-2">
                    <span class="font-semibold text-highlighted">{{ t.pair.split('/')[0] }}</span>
                    <span
                      class="rounded-full px-2 py-0.5 text-xs font-medium"
                      :class="
                        (t.leverage ?? 1) > 1
                          ? 'bg-brand-400/15 text-brand-600 dark:text-brand-300'
                          : 'bg-accented text-muted'
                      "
                      >{{ t.leverage ?? 1 }}x</span
                    >
                  </span>
                </td>
                <td class="py-2 pe-3 whitespace-nowrap text-muted">
                  {{ t.close_date?.slice(5, 16) }}
                </td>
                <td class="py-2 pe-3 text-right whitespace-nowrap text-muted">
                  {{ novaAge(t.open_timestamp, t.close_timestamp) }}
                </td>
                <td class="py-2 pe-3 text-right whitespace-nowrap text-muted">
                  {{ novaPlainNumber(t.open_rate, 5) }} → {{ novaPlainNumber(t.close_rate, 5) }}
                </td>
                <td
                  class="py-2 pe-3 text-right whitespace-nowrap"
                  :class="(t.profit_abs ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
                >
                  <span class="font-semibold">{{ novaPct(t.profit_ratio, 2, true) }}</span>
                  <span class="nova-money ms-2 inline-block min-w-12 text-xs">{{
                    novaMoney(t.profit_abs, '', 2, true)
                  }}</span>
                </td>
                <td class="py-2 pe-3 text-right text-muted">
                  {{ novaPct(excursion(t)?.mfe, 1, true) }}
                </td>
                <td class="py-2 pe-4 whitespace-nowrap text-muted sm:pe-6">
                  {{ reasonLabel(t.exit_reason ?? 'unknown') }}
                </td>
              </tr>
              <tr v-if="!filtered.length">
                <td colspan="7" class="px-4 py-8 sm:px-6">
                  <div class="flex items-center justify-center gap-3">
                    <span
                      class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented"
                    >
                      <UIcon name="i-mdi-filter-remove-outline" class="size-5 text-muted" />
                    </span>
                    <p class="text-sm text-muted">
                      {{ all.length ? tr('trades.pro.noMatch') : tr('trades.pro.empty') }}
                    </p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="nova-panel h-fit" :class="simple ? 'p-6' : 'p-4 sm:p-6'">
        <h2
          class="font-semibold text-highlighted"
          :class="simple ? 'mb-3 text-sm' : 'mb-4 text-base'"
        >
          {{ simple ? tr('trades.reasons.simpleTitle') : tr('trades.reasons.proTitle') }}
        </h2>
        <div v-for="[r, v] in byReason" :key="r" :class="simple ? 'mb-2' : 'mb-4 last:mb-0'">
          <div class="flex items-baseline justify-between gap-2 text-sm">
            <button
              type="button"
              class="rounded text-left text-default transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:text-brand-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
              :aria-pressed="reason === r"
              @click="reason = r"
            >
              {{ simple ? plainExitReason(r) : reasonLabel(r) }}
            </button>
            <span class="nova-num text-xs text-muted">{{
              simple ? `${v.n} ×` : tr('trades.reasons.count', v.n)
            }}</span>
          </div>
          <div class="mt-1 rounded-full bg-accented" :class="simple ? 'h-1.5' : 'h-1'">
            <div
              class="h-full rounded-full"
              :class="v.profit >= 0 ? 'bg-emerald-500/80' : 'bg-rose-500/80'"
              :style="{ width: `${(v.n / Math.max(1, all.length)) * 100}%` }"
            />
          </div>
          <div
            class="nova-num nova-money mt-1 text-xs"
            :class="v.profit >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ novaMoney(v.profit, currency, 2, true) }}
          </div>
        </div>
        <p v-if="!byReason.length" class="text-sm text-muted">{{ tr('trades.pro.empty') }}</p>
      </div>
    </div>

    <USlideover
      v-model:open="drawerOpen"
      side="right"
      :ui="{ content: 'max-w-3xl' }"
      :title="tr('trades.detailTitle')"
    >
      <template #body>
        <NovaTradeDetail v-if="selected" :trade="selected" :currency="currency" />
      </template>
    </USlideover>
  </div>
</template>
