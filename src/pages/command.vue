<script setup lang="ts">
import { I18nT } from 'vue-i18n';
import type { ClosedTrade, Trade } from '@/types';
import {
  edgeStats,
  equityCurve,
  exposureRatio,
  largestWinShare,
  recoveryNeeded,
  riskAtStops,
  sampleQuality,
} from '@/utils/novaMetrics';

const botStore = useBotStore();
const router = useRouter();
const bot = computed(() => botStore.activeBot);

// ---- live data: shared poller (health, regime, daily) + Sentinel records and pair performance here ------
const { regime, now, heartbeatAgeMs: heartbeatAge, healthy: botHealthy } = useNovaLive();
const { kevRecords, refreshKev } = useKevRecords();

async function refreshPage() {
  if (!bot.value?.isBotOnline) return;
  await Promise.allSettled([refreshKev(), bot.value.getPerformance()]);
}
useIntervalFn(refreshPage, 30_000);
onMounted(refreshPage);
watch(
  () => botStore.selectedBot,
  () => refreshPage(),
);

// ---- derived state --------------------------------------------------------------------------------
const currency = computed(() => bot.value.botState?.stake_currency ?? '');
const openTrades = computed<Trade[]>(() => bot.value.openTrades ?? []);
const closedTrades = computed<ClosedTrade[]>(() => bot.value.closedTrades ?? []);
const profit = computed(() => bot.value.profit);
const balance = computed(() => bot.value.balance);
const equity = computed(() => balance.value?.total ?? 0);
const startCapital = computed(() => balance.value?.starting_capital ?? equity.value);
const unrealized = computed(() => openTrades.value.reduce((s, t) => s + (t.profit_abs ?? 0), 0));

const days = computed(() => bot.value.dailyStats?.data ?? []);
const today = computed(() => days.value[0]?.abs_profit ?? 0);
const week = computed(() => days.value.slice(0, 7).reduce((s, d) => s + d.abs_profit, 0));

const curve = computed(() =>
  equityCurve(
    closedTrades.value,
    startCapital.value,
    profit.value?.bot_start_timestamp ?? profit.value?.first_trade_timestamp,
  ),
);

const edge = computed(() => edgeStats(closedTrades.value));
const nClosed = computed(() => closedTrades.value.length);
const quality = computed(() => sampleQuality(nClosed.value));

const exposure = computed(() => exposureRatio(openTrades.value, equity.value));
const atRisk = computed(() => riskAtStops(openTrades.value));
const maxTrades = computed(() => bot.value.botState?.max_open_trades ?? 0);
const levMix = computed(() => {
  const m = new Map<number, number>();
  for (const t of openTrades.value) m.set(t.leverage ?? 1, (m.get(t.leverage ?? 1) ?? 0) + 1);
  return [...m.entries()].sort(([a], [b]) => a - b);
});
const currentDd = computed(() => profit.value?.current_drawdown ?? 0);
const maxDd = computed(() => profit.value?.max_drawdown ?? 0);
const concentration = computed(() => largestWinShare(closedTrades.value));

const stateLabel = computed(() => bot.value.botState?.state ?? 'unknown');
const change = computed(() => equity.value - startCapital.value);
const changePct = computed(() => (startCapital.value ? equity.value / startCapital.value - 1 : 0));

function openTrade(trade: Trade) {
  bot.value.setDetailTrade(trade);
  router.push('/positions');
}
function openPair(pair: string) {
  bot.value.selectedPair = pair;
  router.push('/markets');
}
</script>

<template>
  <div
    class="mx-auto flex w-full max-w-[1680px] flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8"
  >
    <!-- page header: title + the live status facts -->
    <header class="flex flex-wrap items-end justify-between gap-4">
      <div class="min-w-0">
        <h1 class="text-2xl font-semibold text-balance text-highlighted">
          {{ $t('command.title') }}
        </h1>
        <div class="nova-num mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted">
          <span class="inline-flex items-center gap-2">
            <span class="relative flex size-2">
              <span
                v-if="botHealthy"
                class="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/60"
              />
              <span
                class="relative inline-flex size-2 rounded-full"
                :class="botHealthy ? 'bg-emerald-400' : 'bg-rose-500'"
              />
            </span>
            <span class="font-medium text-highlighted capitalize">{{
              $te(`widgets.botState.${stateLabel}`)
                ? $t(`widgets.botState.${stateLabel}`)
                : stateLabel
            }}</span>
          </span>
          <span
            class="rounded-full px-3 py-0.5 text-xs font-semibold"
            :class="
              bot.botState?.dry_run
                ? 'bg-secondary/15 text-secondary'
                : 'bg-rose-500/15 text-rose-400'
            "
            >{{
              bot.botState?.dry_run ? $t('widgets.mode.paper') : $t('widgets.mode.liveReal')
            }}</span
          >
          <span>{{
            $t('command.header.heartbeat', {
              age: novaAge(
                heartbeatAge !== null ? now.getTime() - heartbeatAge : null,
                now.getTime(),
              ),
            })
          }}</span>
          <span v-if="regime" :title="$t('command.header.regimeTitle')">
            {{ $t('command.header.regime') }}
            <span
              class="font-medium"
              :class="regime.strength >= 0 ? 'text-emerald-400' : 'text-rose-400'"
            >
              {{
                $t('command.header.regimeState', {
                  state: regime.strength >= 0 ? $t('widgets.regime.on') : $t('widgets.regime.off'),
                  pct: novaPct(regime.strength, 1, true),
                })
              }}
            </span>
          </span>
          <span
            >{{ novaStrategyName(bot.botState?.strategy) }} · {{ bot.botState?.timeframe }}</span
          >
          <span>{{
            $t(
              'command.header.pairsOn',
              { exchange: bot.botState?.exchange ?? '' },
              bot.whitelist?.length ?? 0,
            )
          }}</span>
        </div>
      </div>
      <p class="hidden items-center gap-1 text-xs text-dimmed lg:flex">
        <UKbd value="meta" size="sm" /><UKbd value="K" size="sm" />
        <span class="ms-1 me-3">{{ $t('command.header.kbdCommands') }}</span>
        <UKbd value="shift" size="sm" /><UKbd value="P" size="sm" />
        <span class="ms-1">{{ $t('command.header.kbdPrivacy') }}</span>
      </p>
    </header>

    <!-- hero: equity is the one big number, the rest are tiles -->
    <section
      class="nova-panel grid gap-6 p-4 sm:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)] xl:items-center"
      aria-labelledby="nova-equity-title"
    >
      <div class="min-w-0">
        <h2 id="nova-equity-title" class="text-sm font-medium text-muted">
          {{ $t('widgets.metrics.equity') }}
        </h2>
        <div class="mt-2 flex items-baseline gap-2 whitespace-nowrap">
          <span
            class="nova-num nova-money text-4xl font-semibold tracking-tight text-highlighted sm:text-5xl"
            >{{ novaMoney(equity, '', 2) }}</span
          >
          <span class="text-lg font-medium text-muted">{{ currency }}</span>
        </div>
        <div class="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span
            class="nova-num inline-flex items-center gap-1 rounded-full px-3 py-1 font-semibold"
            :class="
              change >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
            "
          >
            <UIcon
              :name="change >= 0 ? 'i-mdi-arrow-top-right' : 'i-mdi-arrow-bottom-right'"
              class="size-4"
            />
            <span class="nova-money">{{ novaMoney(change, currency, 2, true) }}</span>
            <span>({{ novaPct(changePct, 2, true) }})</span>
          </span>
          <I18nT
            keypath="command.hero.sinceStart"
            tag="span"
            scope="global"
            class="nova-num text-muted"
          >
            <template #capital>
              <span class="nova-money">{{ novaMoney(startCapital, '', 0) }}</span>
            </template>
          </I18nT>
        </div>
      </div>
      <div class="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
        <NovaStat
          class="nova-tile p-4"
          :label="$t('widgets.metrics.today')"
          :value="novaMoney(today, currency, 2, true)"
          :tone="novaTone(today)"
          money
          :sub="$t('command.hero.realized')"
        />
        <NovaStat
          class="nova-tile p-4"
          :label="$t('command.hero.last7')"
          :value="novaMoney(week, currency, 2, true)"
          :tone="novaTone(week)"
          money
          :sub="$t('command.hero.realized')"
        />
        <NovaStat
          class="nova-tile p-4"
          :label="$t('widgets.metrics.unrealized')"
          :value="novaMoney(unrealized, currency, 2, true)"
          :tone="novaTone(unrealized)"
          money
          :sub="$t('command.hero.openPositions', openTrades.length)"
        />
        <NovaStat
          class="nova-tile p-4"
          :label="$t('command.hero.allTime')"
          :value="novaMoney(profit?.profit_all_coin, currency, 2, true)"
          :tone="novaTone(profit?.profit_all_coin)"
          money
          :sub="
            profit?.bot_start_date
              ? $t(
                  'command.hero.tradesSince',
                  { date: profit.bot_start_date.slice(0, 10) },
                  profit?.trade_count ?? 0,
                )
              : $t('command.hero.tradesSinceStart', profit?.trade_count ?? 0)
          "
        />
      </div>
    </section>

    <!-- risk + edge -->
    <div class="grid gap-6 xl:grid-cols-2">
      <NovaPanel :title="$t('command.risk.title')" :subtitle="$t('command.risk.subtitle')">
        <div class="grid gap-6 sm:grid-cols-2">
          <NovaGauge
            :label="$t('command.risk.drawdownNow')"
            :value="currentDd / 0.25"
            :display="novaPct(-currentDd, 1)"
            :sub="
              $t('command.risk.drawdownSub', {
                max: novaPct(-maxDd, 1),
                recover: novaPct(recoveryNeeded(-currentDd), 1),
              })
            "
          />
          <NovaGauge
            :label="$t('widgets.metrics.exposure')"
            :value="exposure / 1.5"
            :display="`${novaNum(exposure, 2)}×`"
            :sub="$t('command.risk.exposureSub')"
          />
          <NovaGauge
            :label="$t('command.risk.atRisk')"
            :value="atRisk / equity / 0.1"
            :display="novaPct(-atRisk / (equity || 1), 1)"
            :sub="$t('command.risk.atRiskSub', { amount: novaMoney(-atRisk, currency, 2) })"
          />
          <NovaGauge
            :label="$t('command.risk.slotsUsed')"
            :value="maxTrades ? openTrades.length / maxTrades : 0"
            :display="`${openTrades.length} / ${maxTrades}`"
            :warn-at="0.75"
            :bad-at="1.01"
            :sub="
              levMix.length
                ? $t('command.risk.leverageMix', {
                    mix: levMix.map(([l, n]) => `${n}×${l}x`).join(' · '),
                  })
                : $t('command.risk.noPositions')
            "
          />
        </div>
      </NovaPanel>

      <NovaPanel :title="$t('command.edge.title')" :subtitle="$t('command.edge.subtitle', nClosed)">
        <template #actions>
          <span
            v-if="quality !== 'solid'"
            class="rounded-full bg-accented px-3 py-1 text-xs font-medium text-muted"
            :title="$t('widgets.sample.hint')"
            >{{ quality === 'early' ? $t('widgets.sample.early') : $t('widgets.sample.low') }}</span
          >
        </template>
        <div
          class="grid grid-cols-2 gap-3 sm:grid-cols-4"
          :class="{ 'opacity-60': quality === 'early' }"
        >
          <NovaStat
            class="nova-tile p-3"
            :label="$t('widgets.metrics.winRate')"
            :value="novaPct(edge.winRate, 0)"
            :sub="$t('command.edge.winsLosses', { wins: edge.wins, losses: edge.losses })"
          />
          <NovaStat
            class="nova-tile p-3"
            :label="$t('widgets.metrics.payoff')"
            :value="edge.payoff !== null ? `${novaNum(edge.payoff, 2)}×` : '–'"
            :sub="$t('command.edge.payoffSub')"
          />
          <NovaStat
            class="nova-tile p-3"
            :label="$t('widgets.metrics.expectancy')"
            :value="novaMoney(edge.expectancyAbs, '', 2, true)"
            :tone="novaTone(edge.expectancyAbs)"
            :sub="$t('command.edge.perTrade')"
            money
          />
          <NovaStat
            class="nova-tile p-3"
            :label="$t('widgets.metrics.profitFactor')"
            :value="novaNum(profit?.profit_factor ?? edge.profitFactor, 2)"
            :tone="(profit?.profit_factor ?? 0) >= 1 ? 'pos' : 'neg'"
            :sub="$t('command.edge.profitFactorSub')"
          />
          <NovaStat
            class="nova-tile p-3"
            label="Sharpe"
            :value="quality === 'early' ? '—' : novaNum(profit?.sharpe, 2)"
            :sub="quality === 'early' ? $t('command.edge.from30') : undefined"
          />
          <NovaStat
            class="nova-tile p-3"
            label="Sortino"
            :value="quality === 'early' ? '—' : novaNum(profit?.sortino, 2)"
            :sub="quality === 'early' ? $t('command.edge.from30') : undefined"
          />
          <NovaStat
            class="nova-tile p-3"
            label="Calmar"
            :value="quality === 'early' ? '—' : novaNum(profit?.calmar, 2)"
            :sub="quality === 'early' ? $t('command.edge.from30') : undefined"
          />
          <NovaStat
            class="nova-tile p-3"
            :label="$t('command.edge.topWinShare')"
            :value="novaPct(concentration, 0)"
            :sub="$t('command.edge.ofGrossProfit')"
            :tone="(concentration ?? 0) > 0.5 ? 'warn' : 'neutral'"
            :hint="$t('command.edge.topWinHint')"
          />
        </div>
      </NovaPanel>
    </div>

    <!-- positions -->
    <NovaPanel :title="$t('command.positions.title')" :subtitle="$t('command.positions.subtitle')">
      <template #actions>
        <span class="nova-num rounded-full bg-accented px-3 py-1 text-xs font-medium text-muted">{{
          $t('command.positions.slots', { n: openTrades.length, max: maxTrades })
        }}</span>
      </template>
      <div v-if="!openTrades.length" class="flex items-center gap-3">
        <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
          <UIcon name="i-mdi-radar" class="size-5 text-muted" />
        </span>
        <p class="text-sm text-pretty text-muted">
          {{ $t('command.positions.empty') }}
        </p>
      </div>
      <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        <NovaPositionCard
          v-for="t in openTrades"
          :key="t.trade_id"
          :trade="t"
          :currency="currency"
          :kev="kevRecords.get(t.trade_id) ?? null"
          @open="openTrade"
        />
      </div>
    </NovaPanel>

    <!-- performance: charts paired by height -->
    <div class="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
      <NovaPanel :title="$t('command.equity.title')" :subtitle="$t('command.equity.subtitle')">
        <div class="h-96 xl:h-[28rem]">
          <NovaEquityChart :points="curve" :currency="currency" :live-equity="equity" />
        </div>
      </NovaPanel>
      <NovaPanel :title="$t('command.pairs.title')" :subtitle="$t('command.pairs.subtitle')">
        <NovaPairBoard
          :performance="bot.performanceStats ?? []"
          :open-trades="openTrades"
          :currency="currency"
          @pair="openPair"
        />
      </NovaPanel>
    </div>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.7fr)]">
      <NovaPanel :title="$t('command.daily.title')" :subtitle="$t('command.daily.subtitle')">
        <div class="flex h-full flex-col justify-center">
          <NovaPnlCalendar :days="days" :currency="currency" :weeks="12" />
        </div>
      </NovaPanel>
      <NovaPanel
        :title="$t('command.excursion.title')"
        :subtitle="$t('command.excursion.subtitle')"
      >
        <div class="h-80">
          <NovaExcursionMap :trades="closedTrades" />
        </div>
      </NovaPanel>
    </div>

    <NovaPanel :title="$t('command.sentinel.title')" :subtitle="$t('command.sentinel.subtitle')">
      <NovaKevPanel
        :records="kevRecords"
        :open-trades="openTrades"
        :closed-trades="closedTrades"
        :currency="currency"
      />
    </NovaPanel>
  </div>
</template>
