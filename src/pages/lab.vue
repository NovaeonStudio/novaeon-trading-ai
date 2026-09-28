<script setup lang="ts">
/**
 * Strategy Lab: what was tested, what won and why, and whether live trading matches the research.
 * Research data comes from the backtest scripts in bot/research and is bundled at build time.
 */
import research from '@/data/strategy-research.json';
import type { ClosedTrade } from '@/types';
import { edgeStats } from '@/utils/novaMetrics';
import { intlLocale } from '@/i18n';

const { bot } = useNovaLive();
const { simple } = useNovaMode();
const { t: tr, te } = useI18n();

type Variant = (typeof research.variants)[number];
const chosen = computed(() => research.variants.find((v) => v.id === research.chosen) as Variant);
const base = computed(() => research.variants.find((v) => v.verdict === 'baseline') as Variant);
const sortedVariants = computed(() =>
  [...research.variants].sort(
    (a, b) => (b.y1.profit ?? 0) + (b.y2.profit ?? 0) - ((a.y1.profit ?? 0) + (a.y2.profit ?? 0)),
  ),
);
/** Plain research number (drawdown %, profit factor) in the app language. */
const num = (v: number) => v.toLocaleString(intlLocale());
/** Variant name in the app language; research variants without a translation keep their English label. */
const variantLabel = (v: Variant) =>
  te(`lab.variant.${v.id}`) ? tr(`lab.variant.${v.id}`) : v.label;
const twoYear = (v: Variant) => ((1 + v.y1.profit / 100) * (1 + v.y2.profit / 100) - 1) * 100;

// ---- live vs expectation (closed trades since v2 went live) ----
const liveSince = new Date(research.live_since).getTime();
const liveTrades = computed<ClosedTrade[]>(() =>
  (bot.value?.closedTrades ?? []).filter((t) => t.open_timestamp >= liveSince),
);
const liveEdge = computed(() => edgeStats(liveTrades.value));
const liveDays = computed(() => Math.max(1 / 24, (Date.now() - liveSince) / 86_400_000));
const liveTradesPerDay = computed(() => liveTrades.value.length / liveDays.value);
const exp = research.expectation;
function within(v: number | null, [lo, hi]: number[]) {
  if (v === null) return 'wait';
  return v >= lo * 0.85 && v <= hi * 1.15 ? 'ok' : v < lo ? 'low' : 'high';
}
const checks = computed(() => [
  {
    label: simple.value ? tr('lab.check.winRateSimple') : tr('lab.check.winRate'),
    live: liveEdge.value.winRate,
    fmt: (v: number | null) => novaPct(v, 0),
    range: exp.win_rate,
    rangeFmt: `${novaPct(exp.win_rate[0], 0)}–${novaPct(exp.win_rate[1], 0)}`,
  },
  {
    label: simple.value ? tr('lab.check.profitFactorSimple') : tr('lab.check.profitFactor'),
    live: liveEdge.value.profitFactor,
    fmt: (v: number | null) => novaNum(v, 2),
    range: exp.profit_factor,
    rangeFmt: `${num(exp.profit_factor[0])}–${num(exp.profit_factor[1])}`,
  },
  {
    label: simple.value ? tr('lab.check.tradesPerDaySimple') : tr('lab.check.tradesPerDay'),
    live: liveTrades.value.length ? liveTradesPerDay.value : null,
    fmt: (v: number | null) => novaNum(v, 1),
    range: exp.trades_per_day,
    rangeFmt: `${num(exp.trades_per_day[0])}–${num(exp.trades_per_day[1])}`,
  },
]);
const enough = computed(() => liveTrades.value.length >= 30);
const verdictClass = {
  chosen: 'bg-brand-400/15 text-brand-700 dark:text-brand-300',
  better: 'bg-emerald-500/15 text-emerald-400',
  baseline: 'bg-accented text-muted',
  mixed: 'bg-secondary/15 text-secondary',
  rejected: 'bg-rose-500/15 text-rose-400',
} as Record<string, string>;
/** Verdict pill text; keys: lab.verdict.{chosen,better,baseline,mixed,rejected}. */
const verdictLabel = (v: string) =>
  te(`lab.verdict.${v}`) ? tr(`lab.verdict.${v}`) : v.charAt(0).toUpperCase() + v.slice(1);

/** Live vs expected: one status per check (pill text + tone). */
function checkStatus(live: number | null, range: number[]) {
  const w = within(live, range);
  if (!enough.value || w === 'wait')
    return { text: tr('lab.status.collecting'), cls: 'bg-accented text-muted' };
  if (w === 'ok')
    return { text: tr('lab.status.asExpected'), cls: 'bg-emerald-500/15 text-emerald-400' };
  return {
    text: w === 'low' ? tr('lab.status.below') : tr('lab.status.above'),
    cls: 'bg-rose-500/15 text-rose-400',
  };
}

const steps = computed(() => [
  {
    id: 'mood',
    title: tr('lab.steps.mood.title'),
    text: tr('lab.steps.mood.text'),
    badge: 'bg-brand-400/15 text-brand-700 dark:text-brand-300',
  },
  {
    id: 'breakout',
    title: tr('lab.steps.breakout.title'),
    text: tr('lab.steps.breakout.text'),
    badge: 'bg-brand-400/15 text-brand-700 dark:text-brand-300',
  },
  {
    id: 'volume',
    title: tr('lab.steps.volume.title'),
    isNew: true,
    text: tr('lab.steps.volume.text'),
    badge: 'bg-emerald-500/15 text-emerald-400',
  },
  {
    id: 'sentinel',
    title: tr('lab.steps.sentinel.title'),
    text: tr('lab.steps.sentinel.text'),
    badge: 'bg-secondary/15 text-secondary',
  },
]);
</script>

<template>
  <div class="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8">
    <header>
      <h1 class="text-2xl font-semibold text-balance text-highlighted">{{ tr('lab.title') }}</h1>
      <p class="mt-1 text-sm text-pretty text-muted">
        {{ simple ? tr('lab.intro.simple') : tr('lab.intro.pro') }}
      </p>
    </header>

    <!-- How it works -->
    <section class="nova-panel p-4 sm:p-6">
      <h2 class="text-lg font-semibold text-balance text-highlighted">{{ tr('lab.how.title') }}</h2>
      <ol class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <li v-for="(step, i) in steps" :key="step.id" class="nova-tile p-4">
          <div class="flex items-center gap-3">
            <span
              class="nova-num flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold"
              :class="step.badge"
              aria-hidden="true"
              >{{ i + 1 }}</span
            >
            <h3 class="text-sm font-semibold text-highlighted">{{ step.title }}</h3>
            <span
              v-if="step.isNew"
              class="rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-semibold text-emerald-400"
              >{{ tr('lab.steps.new') }}</span
            >
          </div>
          <p class="mt-3 text-sm text-pretty text-muted">{{ step.text }}</p>
        </li>
      </ol>
      <p class="mt-4 text-sm text-pretty text-muted">
        {{ tr('lab.how.exit') }}
      </p>
    </section>

    <!-- Result of the research: before and after -->
    <div class="flex flex-col gap-3">
      <div class="grid gap-6 md:grid-cols-2">
        <section class="nova-panel p-4 sm:p-6">
          <div class="flex flex-wrap items-center gap-2">
            <span class="rounded-full bg-accented px-3 py-1 text-xs font-semibold text-muted">{{
              tr('lab.result.before')
            }}</span>
            <span class="text-sm text-muted">{{ variantLabel(base) }}</span>
          </div>
          <div class="nova-num mt-4 text-4xl font-semibold tracking-tight text-highlighted">
            {{ novaPct(twoYear(base) / 100, 0, true) }}
          </div>
          <p class="mt-1 text-sm text-muted">{{ tr('lab.result.overTwoYears') }}</p>
          <div
            class="nova-tile nova-num mt-4 flex items-baseline justify-between gap-2 p-3 text-sm"
          >
            <span class="text-muted">{{ tr('lab.result.worstDip') }}</span>
            <span class="font-semibold text-rose-400"
              >{{ num(Math.max(base.y1.dd, base.y2.dd)) }}%</span
            >
          </div>
        </section>
        <section class="rounded-2xl border border-brand-400/50 bg-brand-400/5 p-4 sm:p-6">
          <div class="flex flex-wrap items-center gap-2">
            <span
              class="rounded-full bg-brand-400/15 px-3 py-1 text-xs font-semibold text-brand-700 dark:text-brand-300"
              >{{ tr('lab.result.nowLive') }}</span
            >
            <span class="text-sm text-muted">{{ variantLabel(chosen) }}</span>
          </div>
          <div class="nova-num mt-4 text-4xl font-semibold tracking-tight text-emerald-400">
            {{ novaPct(twoYear(chosen) / 100, 0, true) }}
          </div>
          <p class="mt-1 text-sm text-muted">{{ tr('lab.result.overTwoYearsSame') }}</p>
          <div
            class="nova-tile nova-num mt-4 flex items-baseline justify-between gap-2 p-3 text-sm"
          >
            <span class="text-muted">{{ tr('lab.result.worstDip') }}</span>
            <span
              ><span class="font-semibold text-emerald-400"
                >{{ num(Math.max(chosen.y1.dd, chosen.y2.dd)) }}%</span
              >
              <span class="text-muted">
                {{
                  tr('lab.result.was', { value: `${num(Math.max(base.y1.dd, base.y2.dd))}%` })
                }}</span
              ></span
            >
          </div>
        </section>
      </div>
      <p class="text-xs text-pretty text-muted">
        {{ tr('lab.result.disclaimer') }}
        {{ research.setup }}
      </p>
    </div>

    <!-- Live vs expectation -->
    <section class="nova-panel p-4 sm:p-6">
      <h2 class="text-lg font-semibold text-balance text-highlighted">
        {{ tr('lab.live.title') }}
      </h2>
      <p class="nova-num mt-1 text-sm text-pretty text-muted">
        {{
          tr(
            'lab.live.closedSince',
            {
              n: liveTrades.length,
              date: new Date(research.live_since).toLocaleString(intlLocale()),
            },
            liveTrades.length,
          )
        }}
        {{ enough ? tr('lab.live.enough') : tr('lab.live.tooEarly') }}
      </p>
      <div class="mt-4 grid gap-3 sm:grid-cols-3">
        <div v-for="c in checks" :key="c.label" class="nova-tile flex flex-col p-4">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <span class="nova-label">{{ c.label }}</span>
            <span
              class="rounded-full px-2 py-0.5 text-xs font-semibold"
              :class="checkStatus(c.live, c.range).cls"
              >{{ checkStatus(c.live, c.range).text }}</span
            >
          </div>
          <div class="nova-num mt-2 text-2xl font-semibold text-highlighted">
            {{ c.fmt(c.live) }}
          </div>
          <div class="nova-num mt-1 text-xs text-muted">
            {{ tr('lab.check.expected', { range: c.rangeFmt }) }}
          </div>
        </div>
      </div>
    </section>

    <!-- All variants -->
    <section class="nova-panel p-4 sm:p-6">
      <h2 class="text-lg font-semibold text-balance text-highlighted">
        {{ tr('lab.tested.title') }}
      </h2>
      <p class="mt-1 text-sm text-pretty text-muted">
        {{ simple ? tr('lab.tested.simple') : tr('lab.tested.pro') }}
      </p>
      <div class="-mx-4 mt-4 overflow-x-auto sm:-mx-6">
        <table class="nova-num w-full text-sm" :class="simple ? 'min-w-[36rem]' : 'min-w-[48rem]'">
          <thead>
            <tr class="text-left text-xs font-medium text-muted">
              <th class="py-2 ps-4 pe-3 font-medium sm:ps-6">{{ tr('lab.table.idea') }}</th>
              <th class="py-2 pe-3 text-right font-medium">
                {{ simple ? tr('lab.table.year1Simple') : tr('lab.table.year1') }}
              </th>
              <th class="py-2 pe-3 text-right font-medium">
                {{ simple ? tr('lab.table.year2Simple') : tr('lab.table.year2') }}
              </th>
              <th class="py-2 pe-3 text-right font-medium">
                {{ simple ? tr('lab.result.worstDip') : tr('lab.table.maxDrawdown') }}
              </th>
              <th v-if="!simple" class="py-2 pe-3 text-right font-medium">
                {{ tr('lab.table.profitFactor') }}
              </th>
              <th v-if="!simple" class="py-2 pe-3 text-right font-medium">Hyperliquid</th>
              <th class="py-2 pe-4 font-medium sm:pe-6">{{ tr('lab.table.verdict') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="v in sortedVariants"
              :key="v.id"
              class="border-t border-default/50 transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40"
            >
              <td class="py-3 ps-4 pe-3 text-default sm:ps-6">{{ variantLabel(v) }}</td>
              <td
                class="py-3 pe-3 text-right"
                :class="v.y1.profit >= 0 ? 'text-emerald-400' : 'text-rose-400'"
              >
                {{ novaPct(v.y1.profit / 100, 1, true) }}
              </td>
              <td
                class="py-3 pe-3 text-right"
                :class="v.y2.profit >= 0 ? 'text-emerald-400' : 'text-rose-400'"
              >
                {{ novaPct(v.y2.profit / 100, 1, true) }}
              </td>
              <td class="py-3 pe-3 text-right text-muted">
                {{ num(Math.max(v.y1.dd, v.y2.dd)) }}%
              </td>
              <td v-if="!simple" class="py-3 pe-3 text-right text-muted">
                {{ num(v.y1.pf) }} / {{ num(v.y2.pf) }}
              </td>
              <td v-if="!simple" class="py-3 pe-3 text-right whitespace-nowrap text-muted">
                {{ v.hl ? `${novaPct(v.hl.profit / 100, 0, true)} · DD ${num(v.hl.dd)}%` : '–' }}
              </td>
              <td class="py-3 pe-4 sm:pe-6">
                <span
                  class="rounded-full px-2 py-0.5 text-xs font-semibold whitespace-nowrap"
                  :class="verdictClass[v.verdict]"
                  >{{ verdictLabel(v.verdict) }}</span
                >
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
