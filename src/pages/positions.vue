<script setup lang="ts">
/** Positions: open trades as a selectable list + full detail (chart, numbers, Sentinel, actions). */
import type { Trade } from '@/types';
import { exposureRatio, riskAtStops } from '@/utils/novaMetrics';

const botStore = useBotStore();
const { bot, equity, unrealized } = useNovaLive();
const { kevRecords } = useKevRecords();
const { confirm } = useConfirmBox();
const { simple } = useNovaMode();
const { t: tr } = useI18n();
const manualBuyOpen = ref(false);

const sortBy = useStorage<'pnl' | 'age' | 'risk'>('nova-positions-sort', 'pnl');
const currency = computed(() => bot.value?.botState?.stake_currency ?? '');
const openTrades = computed<Trade[]>(() => {
  const list = [...(bot.value?.openTrades ?? [])];
  if (sortBy.value === 'age') return list.sort((a, b) => b.open_timestamp - a.open_timestamp);
  if (sortBy.value === 'risk')
    return list.sort(
      (a, b) => (a.stoploss_current_dist_ratio ?? 1) - (b.stoploss_current_dist_ratio ?? 1),
    );
  return list.sort((a, b) => (b.profit_ratio ?? 0) - (a.profit_ratio ?? 0));
});
const selectedId = ref<number | null>(botStore.activeBot?.detailTradeId ?? null);
const selected = computed(
  () =>
    openTrades.value.find((t) => t.trade_id === selectedId.value) ?? openTrades.value[0] ?? null,
);
watch(
  () => botStore.activeBot?.detailTradeId,
  (id) => {
    if (id) selectedId.value = id;
  },
);

const exposure = computed(() => exposureRatio(openTrades.value, equity.value));
const atRisk = computed(() => riskAtStops(openTrades.value));
const maxTrades = computed(() => bot.value?.botState?.max_open_trades ?? 0);
const state = computed(() => bot.value?.botState?.state);

async function pauseEntries() {
  if (
    await confirm(
      simple.value
        ? {
            title: tr('positions.confirm.pauseSimpleTitle'),
            message: tr('positions.confirm.pauseSimpleMessage'),
          }
        : {
            title: tr('positions.confirm.pauseProTitle'),
            message: tr('positions.confirm.pauseProMessage'),
          },
    )
  )
    await bot.value.stopBuy();
}
async function startBot() {
  if (
    await confirm(
      simple.value && state.value === 'paused'
        ? {
            title: tr('positions.confirm.resumeTitle'),
            message: tr('positions.confirm.resumeMessage'),
          }
        : {
            title: tr('positions.confirm.startTitle'),
            message: tr('positions.confirm.startMessage'),
          },
    )
  )
    await bot.value.startBot();
}

/** Simple mode on phones: the detail sits below the list, so bring it into view after a tap. */
const detailEl = ref<HTMLElement | null>(null);
function pick(id: number) {
  selectedId.value = id;
  if (simple.value && window.matchMedia('(max-width: 1023px)').matches)
    nextTick(() => detailEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
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
    <!-- Simple mode: calm header with two big numbers -->
    <section
      v-if="simple"
      class="flex flex-col gap-6 rounded-2xl border border-default/70 bg-elevated/60 p-6 lg:flex-row lg:items-center"
    >
      <div class="min-w-0 flex-1">
        <h1 class="text-2xl font-semibold text-highlighted">{{ tr('positions.simple.title') }}</h1>
        <p class="mt-1 text-sm text-pretty text-muted">
          {{ tr('positions.simple.holding', { max: maxTrades }, openTrades.length) }}
        </p>
      </div>
      <dl class="grid grid-cols-2 gap-3 lg:w-auto">
        <div class="rounded-xl bg-default/50 p-4">
          <dt class="text-xs text-muted">{{ tr('positions.simple.nowLabel') }}</dt>
          <dd
            class="nova-num nova-money mt-1 text-2xl font-semibold"
            :class="unrealized >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ novaMoney(unrealized, currency, 2, true) }}
          </dd>
          <dd class="mt-1 text-xs text-dimmed">{{ tr('positions.simple.notFinal') }}</dd>
        </div>
        <div class="rounded-xl bg-default/50 p-4">
          <dt class="text-xs text-muted">{{ tr('positions.simple.maxLossLabel') }}</dt>
          <dd
            class="nova-num nova-money mt-1 text-2xl font-semibold"
            :class="equity && atRisk / equity > 0.1 ? 'text-rose-400' : 'text-highlighted'"
          >
            {{ novaMoney(-atRisk, currency, 2) }}
          </dd>
          <dd class="mt-1 text-xs text-pretty text-dimmed">
            {{
              tr('positions.simple.maxLossHint', { pct: novaPct(equity ? atRisk / equity : 0, 0) })
            }}
          </dd>
        </div>
      </dl>
      <div class="flex flex-col gap-2 lg:w-auto">
        <UButton
          v-if="bot?.isBotOnline"
          color="neutral"
          variant="outline"
          size="lg"
          icon="i-mdi-cart-plus"
          class="w-full justify-center rounded-xl font-semibold"
          @click="manualBuyOpen = true"
          >{{ tr('positions.simple.buyCoin') }}</UButton
        >
        <UButton
          v-if="state === 'running'"
          color="neutral"
          variant="outline"
          size="lg"
          icon="i-mdi-pause"
          class="w-full justify-center rounded-xl font-semibold"
          @click="pauseEntries"
          >{{ tr('positions.simple.pauseBuying') }}</UButton
        >
        <UButton
          v-else-if="bot?.isBotOnline"
          color="primary"
          variant="solid"
          size="lg"
          icon="i-mdi-play"
          class="w-full justify-center rounded-xl font-semibold"
          @click="startBot"
          >{{
            state === 'paused' ? tr('positions.simple.resumeBuying') : tr('positions.simple.start')
          }}</UButton
        >
      </div>
    </section>

    <!-- Pro: same structure as Simple, with the risk numbers -->
    <section v-else class="nova-panel p-4 sm:p-6">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div class="min-w-0">
          <h1 class="text-2xl font-semibold text-balance text-highlighted">
            {{ tr('positions.pro.title') }}
          </h1>
          <p class="mt-1 text-sm text-pretty text-muted">
            {{
              tr('positions.pro.slotsInUse', {
                open: openTrades.length,
                max: maxTrades,
                strategy:
                  novaStrategyName(bot?.botState?.strategy) || tr('positions.pro.noStrategy'),
              })
            }}
          </p>
        </div>
        <div class="grid grid-cols-2 gap-2 sm:flex">
          <UButton
            v-if="bot?.isBotOnline"
            color="neutral"
            variant="outline"
            size="lg"
            icon="i-mdi-cart-plus"
            class="justify-center rounded-xl font-semibold"
            @click="manualBuyOpen = true"
            >{{ tr('positions.pro.manualBuy') }}</UButton
          >
          <UButton
            v-if="state === 'running'"
            color="neutral"
            variant="outline"
            size="lg"
            icon="i-mdi-pause"
            class="justify-center rounded-xl font-semibold"
            @click="pauseEntries"
            >{{ tr('positions.pro.pauseEntries') }}</UButton
          >
          <UButton
            v-else-if="bot?.isBotOnline"
            color="primary"
            variant="solid"
            size="lg"
            icon="i-mdi-play"
            class="justify-center rounded-xl font-semibold"
            @click="startBot"
            >{{ tr('positions.pro.startBot') }}</UButton
          >
        </div>
      </div>
      <dl class="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <NovaStat
          class="nova-tile p-4"
          :label="tr('positions.pro.unrealized')"
          :value="novaMoney(unrealized, currency, 2, true)"
          :tone="novaTone(unrealized)"
          :sub="tr('positions.pro.notFinal')"
          money
        />
        <NovaStat
          class="nova-tile p-4"
          :label="tr('positions.pro.exposure')"
          :value="`${novaNum(exposure, 2)}×`"
          :sub="tr('positions.pro.exposureHint')"
        />
        <NovaStat
          class="nova-tile p-4"
          :label="tr('positions.pro.atRisk')"
          :value="novaMoney(-atRisk, currency, 2)"
          :sub="
            tr('positions.pro.atRiskHint', { pct: novaPct(-(equity ? atRisk / equity : 0), 1) })
          "
          :tone="equity && atRisk / equity > 0.1 ? 'neg' : 'neutral'"
          money
        />
        <NovaStat
          class="nova-tile p-4"
          :label="tr('positions.pro.slots')"
          :value="`${openTrades.length} / ${maxTrades}`"
          :sub="
            maxTrades - openTrades.length > 0
              ? tr('positions.pro.slotsFree', { n: maxTrades - openTrades.length })
              : tr('positions.pro.allInUse')
          "
        />
      </dl>
    </section>

    <div class="grid gap-6 lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
      <div class="flex min-w-0 flex-col" :class="simple ? 'gap-3' : 'gap-4'">
        <div v-if="simple" class="flex items-center justify-between px-1">
          <span class="text-[0.65rem] tracking-[0.18em] text-muted uppercase">{{
            tr('positions.sort.label')
          }}</span>
          <div class="flex gap-1 text-sm">
            <button
              v-for="opt in ['pnl', 'age', 'risk'] as const"
              :key="opt"
              type="button"
              class="rounded-full px-3 py-2 font-medium"
              :class="
                sortBy === opt ? 'bg-brand-400/15 text-brand-300' : 'text-muted hover:text-default'
              "
              @click="sortBy = opt"
            >
              {{
                opt === 'pnl'
                  ? tr('positions.sort.bestFirst')
                  : opt === 'age'
                    ? tr('positions.sort.newest')
                    : tr('positions.sort.closestSafetyStop')
              }}
            </button>
          </div>
        </div>
        <div v-else class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-base font-semibold text-highlighted">
            {{ tr('positions.pro.openPositions') }}
          </h2>
          <div class="nova-seg text-sm" role="group" :aria-label="tr('positions.sort.aria')">
            <button
              v-for="opt in ['pnl', 'age', 'risk'] as const"
              :key="opt"
              type="button"
              :aria-pressed="sortBy === opt"
              @click="sortBy = opt"
            >
              {{
                opt === 'pnl'
                  ? tr('positions.sort.pnl')
                  : opt === 'age'
                    ? tr('positions.sort.newest')
                    : tr('positions.sort.closestStop')
              }}
            </button>
          </div>
        </div>
        <p v-if="!openTrades.length && simple" class="nova-panel p-5 text-sm text-muted">
          {{ tr('positions.simple.empty') }}
        </p>
        <div v-else-if="!openTrades.length" class="nova-panel flex items-center gap-3 p-4 sm:p-6">
          <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
            <UIcon name="i-mdi-radar" class="size-5 text-muted" />
          </span>
          <p class="text-sm text-pretty text-muted">
            {{ tr('positions.pro.empty') }}
          </p>
        </div>
        <div
          v-for="t in openTrades"
          :key="t.trade_id"
          class="rounded-2xl transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]"
          :class="selected?.trade_id === t.trade_id ? 'ring-2 ring-brand-400/60' : ''"
        >
          <NovaPositionCard
            :trade="t"
            :currency="currency"
            :kev="kevRecords.get(t.trade_id) ?? null"
            @open="pick(t.trade_id)"
          />
        </div>
      </div>

      <div
        ref="detailEl"
        class="nova-panel min-w-0 scroll-mt-4"
        :class="simple ? 'p-6' : 'p-4 sm:p-6'"
      >
        <NovaTradeDetail
          v-if="selected"
          :key="selected.trade_id"
          :trade="selected"
          :currency="currency"
        />
        <p v-else class="text-sm text-muted">
          {{ simple ? tr('positions.simple.pickCoin') : tr('positions.pro.selectPosition') }}
        </p>
      </div>
    </div>
    <NovaBuyDialog v-model:open="manualBuyOpen" :currency="currency" />
  </div>
</template>
