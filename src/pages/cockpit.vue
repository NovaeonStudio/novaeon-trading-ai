<script setup lang="ts">
import { intlLocale } from '@/i18n';
/**
 * Cockpit: single-screen, no-scroll instrument panel for a second monitor / TV.
 * Left: risk dials. Center: equity + curve + positions. Right: regime, activity feed, controls.
 */
import type { ClosedTrade, Trade } from '@/types';
import {
  edgeStats,
  equityCurve,
  exposureRatio,
  riskAtStops,
  sampleQuality,
} from '@/utils/novaMetrics';

const router = useRouter();
// `t` is the trade loop variable in the template, so the translator is aliased.
const { t: tr } = useI18n();
const { bot, now, regime, healthy, heartbeatAgeMs, equity, startCapital, todayPnl, unrealized } =
  useNovaLive();
const { kevRecords } = useKevRecords();
const { confirm } = useConfirmBox();

const root = ref<HTMLElement | null>(null);
const { isFullscreen, toggle: toggleFullscreen } = useFullscreen(root);

const currency = computed(() => bot.value?.botState?.stake_currency ?? '');
const openTrades = computed<Trade[]>(() =>
  [...(bot.value?.openTrades ?? [])].sort((a, b) => (b.profit_ratio ?? 0) - (a.profit_ratio ?? 0)),
);
const closedTrades = computed<ClosedTrade[]>(() => bot.value?.closedTrades ?? []);
const profit = computed(() => bot.value?.profit);
const change = computed(() => (startCapital.value ? equity.value / startCapital.value - 1 : 0));
const curve = computed(() =>
  equityCurve(
    closedTrades.value,
    startCapital.value,
    profit.value?.bot_start_timestamp ?? profit.value?.first_trade_timestamp,
  ),
);
const exposure = computed(() => exposureRatio(openTrades.value, equity.value));
const atRisk = computed(() => riskAtStops(openTrades.value));
const maxTrades = computed(() => bot.value?.botState?.max_open_trades ?? 0);
const currentDd = computed(() => profit.value?.current_drawdown ?? 0);
const edge = computed(() => edgeStats(closedTrades.value));
const quality = computed(() => sampleQuality(closedTrades.value.length));
const week = computed(() =>
  (bot.value?.dailyStats?.data ?? []).slice(0, 7).reduce((s, d) => s + d.abs_profit, 0),
);

/** Edge at a glance under the dials; the second row only when the regime dial is absent (keeps no-scroll). */
const edgeFacts = computed(() => {
  const pf = profit.value?.profit_factor ?? edge.value.profitFactor;
  const facts: { label: string; value: string; tone?: string; money?: boolean }[] = [
    { label: tr('widgets.metrics.winRate'), value: novaPct(edge.value.winRate, 0) },
    {
      label: tr('widgets.metrics.payoff'),
      value: edge.value.payoff !== null ? `${novaNum(edge.value.payoff, 2)}×` : '–',
    },
    { label: tr('widgets.metrics.profitFactor'), value: novaNum(pf, 2) },
  ];
  if (!regime.value)
    facts.push(
      {
        label: tr('widgets.metrics.expectancy'),
        value: novaMoney(edge.value.expectancyAbs, '', 2, true),
        tone: (edge.value.expectancyAbs ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400',
        money: true,
      },
      {
        label: tr('widgets.metrics.maxDrawdown'),
        value: novaPct(-(profit.value?.max_drawdown ?? 0), 1),
      },
      { label: tr('widgets.metrics.closedTrades'), value: String(closedTrades.value.length) },
    );
  return facts;
});

const clock = computed(() =>
  now.value.toLocaleTimeString(intlLocale() === 'en-US' ? 'en-GB' : intlLocale(), {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }),
);
const running = computed(() => bot.value?.botState?.state === 'running');

async function pauseEntries() {
  if (
    await confirm({
      title: tr('cockpit.pauseTitle'),
      message: tr('cockpit.pauseMessage'),
    })
  ) {
    await bot.value.stopBuy();
  }
}
function openTrade(trade: Trade) {
  bot.value.setDetailTrade(trade);
  router.push('/positions');
}
</script>

<template>
  <div
    ref="root"
    class="nova-cockpit flex min-h-full flex-col gap-4 p-4 text-left xl:h-full xl:min-h-[680px]"
    :class="{ 'xl:p-6': isFullscreen }"
  >
    <!-- top band -->
    <section class="nova-panel flex flex-wrap items-center gap-x-8 gap-y-4 p-4">
      <div class="flex items-center gap-3">
        <AppIcon class="size-9" />
        <div class="leading-tight">
          <div class="nova-label">{{ $t('cockpit.title') }}</div>
          <div class="nova-num text-lg font-semibold text-highlighted">{{ clock }}</div>
        </div>
      </div>

      <div class="min-w-0 leading-tight">
        <div class="nova-label">{{ $t('widgets.metrics.equity') }}</div>
        <div class="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span class="flex items-baseline gap-2 whitespace-nowrap">
            <span
              class="nova-num nova-money text-4xl font-semibold tracking-tight text-highlighted"
              >{{ novaMoney(equity, '', 2) }}</span
            >
            <span class="text-sm font-medium text-muted">{{ currency }}</span>
          </span>
          <span
            class="nova-num rounded-full px-2 py-0.5 text-sm font-semibold"
            :class="
              change >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-rose-500/15 text-rose-400'
            "
          >
            {{ novaPct(change, 2, true) }}
          </span>
        </div>
      </div>

      <dl class="nova-num grid grid-cols-3 gap-6">
        <div>
          <dt class="nova-label">{{ $t('widgets.metrics.today') }}</dt>
          <dd
            class="nova-money mt-1 text-xl font-semibold"
            :class="todayPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ novaMoney(todayPnl, '', 2, true) }}
          </dd>
        </div>
        <div>
          <dt class="nova-label">{{ $t('widgets.metrics.sevenDays') }}</dt>
          <dd
            class="nova-money mt-1 text-xl font-semibold"
            :class="week >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ novaMoney(week, '', 2, true) }}
          </dd>
        </div>
        <div>
          <dt class="nova-label">{{ $t('widgets.metrics.unrealized') }}</dt>
          <dd
            class="nova-money mt-1 text-xl font-semibold"
            :class="unrealized >= 0 ? 'text-emerald-400' : 'text-rose-400'"
          >
            {{ novaMoney(unrealized, '', 2, true) }}
          </dd>
        </div>
      </dl>

      <div class="flex flex-wrap items-center gap-2 xl:ms-auto">
        <span
          class="nova-num inline-flex items-center gap-2 rounded-full bg-accented px-3 py-1 text-xs font-medium"
          :title="
            $t('widgets.heartbeatTitle', {
              age: novaAge(
                heartbeatAgeMs !== null ? now.getTime() - heartbeatAgeMs : null,
                now.getTime(),
              ),
            })
          "
        >
          <span class="relative flex size-2">
            <span
              v-if="healthy"
              class="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/60"
            />
            <span
              class="relative inline-flex size-2 rounded-full"
              :class="healthy ? 'bg-emerald-400' : 'bg-rose-500'"
            />
          </span>
          <span class="text-default capitalize">{{
            $te(`widgets.botState.${bot?.botState?.state ?? 'offline'}`)
              ? $t(`widgets.botState.${bot?.botState?.state ?? 'offline'}`)
              : bot?.botState?.state
          }}</span>
        </span>
        <span
          class="rounded-full px-3 py-1 text-xs font-semibold"
          :class="
            bot?.botState?.dry_run
              ? 'bg-secondary/15 text-secondary'
              : 'bg-rose-500/15 text-rose-400'
          "
          >{{ bot?.botState?.dry_run ? $t('widgets.mode.paper') : $t('widgets.mode.live') }}</span
        >
        <UButton
          v-if="running"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-mdi-pause"
          class="rounded-lg"
          @click="pauseEntries"
          >{{ $t('cockpit.pauseEntries') }}</UButton
        >
        <UButton
          color="neutral"
          variant="ghost"
          size="sm"
          :icon="isFullscreen ? 'i-mdi-fullscreen-exit' : 'i-mdi-fullscreen'"
          :aria-label="isFullscreen ? $t('cockpit.exitFullscreen') : $t('cockpit.fullscreen')"
          @click="toggleFullscreen"
        />
      </div>
    </section>

    <!-- instruments -->
    <div
      class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(17rem,1fr)_minmax(0,2.2fr)_minmax(17rem,1fr)]"
    >
      <!-- left: risk dials + edge at a glance -->
      <section class="nova-panel flex min-h-0 flex-col gap-4 overflow-y-auto p-4">
        <h2 class="text-sm font-semibold text-highlighted">{{ $t('cockpit.risk') }}</h2>
        <div class="grid flex-1 grid-cols-2 content-evenly gap-x-2 gap-y-4">
          <NovaDial
            :label="$t('widgets.metrics.drawdown')"
            :value="currentDd"
            :max="0.25"
            :display="novaPct(-currentDd, 1)"
            :sub="$t('cockpit.dial.budget')"
          />
          <NovaDial
            :label="$t('widgets.metrics.exposure')"
            :value="exposure"
            :max="1.5"
            :display="`${novaNum(exposure, 2)}×`"
            :sub="$t('cockpit.dial.softCap')"
          />
          <NovaDial
            :label="$t('cockpit.dial.atRisk')"
            :value="equity ? atRisk / equity : 0"
            :max="0.1"
            :display="novaPct(-(equity ? atRisk / equity : 0), 1)"
            :sub="$t('cockpit.dial.ifAllStops')"
          />
          <NovaDial
            :label="$t('cockpit.dial.slots')"
            :value="openTrades.length"
            :max="maxTrades || 1"
            :warn-at="0.75"
            :bad-at="1.01"
            :display="`${openTrades.length}/${maxTrades}`"
            :sub="$t('cockpit.dial.positions')"
          />
          <NovaDial
            v-if="regime"
            class="col-span-2"
            :label="$t('cockpit.dial.marketRegime')"
            centered
            :value="regime.strength"
            :min="-0.2"
            :max="0.2"
            :display="
              $t('cockpit.dial.regimeDisplay', {
                state: regime.strength >= 0 ? $t('widgets.regime.on') : $t('widgets.regime.off'),
                pct: novaPct(regime.strength, 1, true),
              })
            "
            :sub="$t('cockpit.dial.regimeSub', { price: novaMoney(regime.btc, '', 0) })"
          />
        </div>
        <div>
          <div class="mb-2 flex items-center justify-between gap-2">
            <h2 class="text-sm font-semibold text-highlighted">{{ $t('cockpit.edge') }}</h2>
            <span
              v-if="quality !== 'solid'"
              class="rounded-full bg-accented px-2 py-0.5 text-xs font-medium text-muted"
              :title="$t('widgets.sample.hint')"
              >{{
                quality === 'early' ? $t('widgets.sample.early') : $t('widgets.sample.low')
              }}</span
            >
          </div>
          <dl class="nova-num grid grid-cols-3 gap-2 xl:grid-cols-2">
            <div v-for="f in edgeFacts" :key="f.label" class="nova-tile min-w-0 px-2 py-2">
              <dt class="nova-label truncate" :title="f.label">{{ f.label }}</dt>
              <dd
                class="mt-0.5 truncate text-base font-semibold"
                :class="[f.tone ?? 'text-highlighted', { 'nova-money': f.money }]"
              >
                {{ f.value }}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <!-- center: curve + positions -->
      <div class="flex min-h-0 flex-col gap-4">
        <section class="nova-panel flex h-80 flex-col p-4 xl:h-auto xl:min-h-[14rem] xl:flex-1">
          <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-sm font-semibold text-highlighted">{{ $t('cockpit.equityTitle') }}</h2>
            <span class="nova-num text-xs text-dimmed">{{
              $t('cockpit.closedCount', closedTrades.length)
            }}</span>
          </div>
          <div class="min-h-0 flex-1">
            <NovaEquityChart :points="curve" :currency="currency" :live-equity="equity" />
          </div>
        </section>
        <section class="nova-panel flex min-h-0 flex-col p-2 xl:max-h-[42%]">
          <div class="flex flex-wrap items-center justify-between gap-2 px-3 pt-2 pb-1">
            <h2 class="text-sm font-semibold text-highlighted">
              {{ $t('cockpit.positions') }}
              <span class="nova-num font-normal text-muted">{{
                $t('cockpit.positionsOf', { n: openTrades.length, max: maxTrades })
              }}</span>
            </h2>
            <span class="text-xs text-dimmed">{{ $t('cockpit.positionsLegend') }}</span>
          </div>
          <div class="min-h-0 overflow-auto">
            <div v-if="!openTrades.length" class="flex items-center gap-3 px-3 py-3">
              <span
                class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented"
              >
                <UIcon name="i-mdi-radar" class="size-5 text-muted" />
              </span>
              <p class="text-sm text-muted">{{ $t('cockpit.empty') }}</p>
            </div>
            <NovaPositionRow
              v-for="t in openTrades"
              :key="t.trade_id"
              :trade="t"
              @open="openTrade"
            />
          </div>
        </section>
      </div>

      <!-- right: feed -->
      <section class="nova-panel flex max-h-[32rem] min-h-0 flex-col p-4 xl:max-h-none">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-sm font-semibold text-highlighted">{{ $t('cockpit.activity') }}</h2>
          <span class="nova-num text-xs text-dimmed">{{
            $t('cockpit.activityCount', { closed: closedTrades.length, checks: kevRecords.size })
          }}</span>
        </div>
        <div class="min-h-0 flex-1 overflow-auto pe-1">
          <NovaEventFeed
            :open-trades="openTrades"
            :closed-trades="closedTrades"
            :kev="kevRecords"
            :limit="40"
          />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.nova-cockpit:fullscreen {
  background: var(--ui-bg);
}
</style>
