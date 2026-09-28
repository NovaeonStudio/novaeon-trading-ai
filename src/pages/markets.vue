<script setup lang="ts">
/** Markets: watchlist (open positions first, realized P&L per pair) + full chart engine. */
import { I18nT } from 'vue-i18n';

const botStore = useBotStore();
const { bot } = useNovaLive();
const query = ref('');

onMounted(() => {
  if (bot.value?.isBotOnline) bot.value.getPerformance();
});

const rows = computed(() => {
  const open = new Map((bot.value?.openTrades ?? []).map((t) => [t.pair, t]));
  const perf = new Map((bot.value?.performanceStats ?? []).map((p) => [p.pair, p]));
  const q = query.value.trim().toLowerCase();
  return (bot.value?.whitelist ?? [])
    .filter((pair) => !q || pair.toLowerCase().includes(q))
    .map((pair) => ({ pair, coin: pair.split('/')[0], open: open.get(pair), perf: perf.get(pair) }))
    .sort((a, b) => Number(!!b.open) - Number(!!a.open) || a.coin.localeCompare(b.coin));
});

function select(pair: string) {
  botStore.activeBot.selectedPair = pair;
}
onMounted(() => {
  if (!botStore.activeBot?.selectedPair && rows.value[0]) select(rows.value[0].pair);
});
</script>

<template>
  <div
    class="flex min-h-full flex-col gap-4 p-4 text-left sm:p-6 lg:h-full lg:min-h-[600px] lg:flex-row"
  >
    <!-- watchlist: a horizontal strip on phones and tablets, a sidebar on desktop -->
    <aside class="nova-panel flex min-w-0 shrink-0 flex-col p-4 lg:w-72">
      <div class="flex items-baseline justify-between gap-2">
        <h1 class="text-lg font-semibold text-highlighted">{{ $t('markets.title') }}</h1>
        <span class="nova-num text-xs text-muted">{{
          $t('markets.count', { timeframe: bot?.botState?.timeframe ?? '' }, rows.length)
        }}</span>
      </div>
      <UInput
        v-model="query"
        icon="i-mdi-magnify"
        :placeholder="$t('markets.filter')"
        class="mt-3"
        :ui="{ base: 'rounded-xl' }"
      />
      <div
        class="-mx-1 mt-3 flex min-h-0 gap-2 overflow-x-auto px-1 pb-1 lg:mx-0 lg:flex-1 lg:flex-col lg:gap-0.5 lg:overflow-x-visible lg:overflow-y-auto lg:px-0 lg:pb-0"
      >
        <button
          v-for="r in rows"
          :key="r.pair"
          type="button"
          class="flex w-56 shrink-0 items-center gap-3 rounded-xl px-3 py-2 text-left transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98] lg:w-full"
          :class="
            bot?.selectedPair === r.pair
              ? 'bg-brand-400/10 ring-1 ring-brand-400/40'
              : 'bg-default/40 hover:bg-accented/60 lg:bg-transparent'
          "
          :aria-pressed="bot?.selectedPair === r.pair"
          @click="select(r.pair)"
        >
          <span
            class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented text-xs font-semibold text-highlighted"
            aria-hidden="true"
            >{{ r.coin.slice(0, 4) }}</span
          >
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-semibold text-highlighted">{{ r.coin }}</span>
            <span
              v-if="r.open"
              class="nova-num mt-0.5 inline-block rounded-full bg-secondary/15 px-2 py-px text-xs font-medium whitespace-nowrap text-secondary"
              :title="$t('markets.openTitle')"
              >{{ $t('markets.openBadge', { leverage: r.open.leverage ?? 1 }) }}</span
            >
            <span v-else-if="r.perf" class="nova-num block text-xs text-dimmed">{{
              $t('markets.trades', r.perf.count)
            }}</span>
          </span>
          <span class="nova-num shrink-0 text-right text-xs leading-tight">
            <span
              v-if="r.open"
              class="block text-sm font-semibold"
              :class="(r.open.profit_ratio ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'"
              >{{ novaPct(r.open.profit_ratio, 2, true) }}</span
            >
            <span
              v-if="r.perf"
              class="nova-money mt-0.5 block"
              :class="r.perf.profit_abs >= 0 ? 'text-emerald-400/80' : 'text-rose-400/80'"
              :title="$t('markets.closedTitle', r.perf.count)"
              >{{ novaMoney(r.perf.profit_abs, '', 2, true) }}</span
            >
          </span>
        </button>
        <p v-if="!rows.length" class="px-2 py-4 text-sm text-muted">
          {{ $t('markets.empty') }}
        </p>
      </div>
      <I18nT
        keypath="markets.legend"
        tag="p"
        scope="global"
        class="mt-3 hidden text-xs text-pretty text-dimmed lg:block"
      >
        <template #now>
          <span class="text-brand-400">{{ $t('markets.legendNow') }}</span>
        </template>
        <template #entry>
          <span class="text-emerald-400">{{ $t('markets.legendEntry') }}</span>
        </template>
        <template #stop>
          <span class="text-rose-400">{{ $t('markets.legendStop') }}</span>
        </template>
      </I18nT>
    </aside>
    <section class="nova-panel h-[70vh] min-h-[28rem] min-w-0 p-2 lg:h-auto lg:min-h-0 lg:flex-1">
      <ChartView />
    </section>
  </div>
</template>
