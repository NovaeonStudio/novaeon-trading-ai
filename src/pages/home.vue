<script setup lang="ts">
/**
 * Home (Simple mode first): answers three questions in plain language, like a consumer money app.
 * 1. Is my money OK?  2. Is the bot OK?  3. What did it do?
 */
import { I18nT } from 'vue-i18n';
import { currentLocale, intlLocale } from '@/i18n';
import type { ClosedTrade, Trade } from '@/types';
import { edgeStats, equityCurve, riskAtStops } from '@/utils/novaMetrics';

/** `t` is the trade loop variable in this file, so the translate function is `tr`. */
const { t: tr } = useI18n();

const router = useRouter();
const { bot, healthy, equity, startCapital, todayPnl, unrealized, now } = useNovaLive();
const { kevRecords } = useKevRecords();
const { confirm } = useConfirmBox();
const { privacy, togglePrivacy } = useNovaPrivacy();

const currency = computed(() => bot.value?.botState?.stake_currency ?? '');
const openTrades = computed<Trade[]>(() =>
  [...(bot.value?.openTrades ?? [])].sort((a, b) => (b.profit_ratio ?? 0) - (a.profit_ratio ?? 0)),
);
const closedTrades = computed<ClosedTrade[]>(() => bot.value?.closedTrades ?? []);
const paper = computed(() => bot.value?.botState?.dry_run ?? true);
const state = computed(() => bot.value?.botState?.state);
/** Balance not loaded yet: show skeletons instead of a misleading 0. */
const loading = computed(() => bot.value?.balance?.total === undefined);
const change = computed(() => equity.value - startCapital.value);
const changePct = computed(() => (startCapital.value ? equity.value / startCapital.value - 1 : 0));
const atRiskShare = computed(() =>
  equity.value ? riskAtStops(openTrades.value) / equity.value : 0,
);
const drawdown = computed(() => bot.value?.profit?.current_drawdown ?? 0);
const watching = computed(() => bot.value?.whitelist?.length ?? 0);
/** Protection lock on all pairs = the strategy's emergency brake. */
const brake = computed(() =>
  (bot.value?.activeLocks ?? []).find(
    (l) => (l.pair === '*' || l.pair === 'all') && l.lock_end_timestamp > now.value.getTime(),
  ),
);
/** "Pause buying" puts the engine into the 'paused' state (open trades still managed); /start resumes. */
const buyingPaused = computed(() => state.value === 'paused');

/** Money over time: realized curve from sold coins, plus the live value as the last point. */
const sparkValues = computed(() => {
  if (loading.value || !equity.value) return [];
  const p = bot.value?.profit;
  const curve = equityCurve(
    closedTrades.value,
    startCapital.value,
    p?.bot_start_timestamp ?? p?.first_trade_timestamp,
  );
  return [...curve.map((x) => x.equity), equity.value];
});

/** The big number without currency, so the currency can be set smaller next to it. */
const moneyNumber = computed(() => novaMoney(equity.value, '', 2));

/** One status line, worst problem first. */
const status = computed(() => {
  if (!bot.value?.isBotOnline || !healthy.value)
    return {
      tone: 'bad' as const,
      title: tr('home.status.offlineTitle'),
      text: tr('home.status.offlineText'),
    };
  if (buyingPaused.value)
    return {
      tone: 'warn' as const,
      title: tr('home.status.pausedTitle'),
      text: tr('home.status.pausedText'),
    };
  if (state.value && state.value !== 'running')
    return {
      tone: 'warn' as const,
      title: tr('home.status.stoppedTitle'),
      text: tr('home.status.stoppedText'),
    };
  if (brake.value)
    return {
      tone: 'warn' as const,
      title: tr('home.status.brakeTitle'),
      text: tr('home.status.brakeText', {
        time: new Date(brake.value.lock_end_timestamp).toLocaleTimeString(intlLocale(), {
          hour: '2-digit',
          minute: '2-digit',
        }),
      }),
    };
  if (drawdown.value > 0.15)
    return {
      tone: 'warn' as const,
      title: tr('home.status.dipTitle'),
      text: tr('home.status.dipText', { pct: novaPct(drawdown.value, 0) }),
    };
  if (atRiskShare.value > 0.1)
    return {
      tone: 'warn' as const,
      title: tr('home.status.riskTitle'),
      text: tr('home.status.riskText', { pct: novaPct(atRiskShare.value, 0) }),
    };
  return {
    tone: 'good' as const,
    title: tr('home.status.goodTitle'),
    text: tr('home.status.goodText', { watching: watching.value }, openTrades.value.length),
  };
});
const statusBox = {
  good: 'border-default/70 bg-elevated/40',
  warn: 'border-brand-400/40 bg-brand-400/10',
  bad: 'border-rose-500/40 bg-rose-500/10',
};
const dotClass = { good: 'bg-emerald-400', warn: 'bg-brand-400', bad: 'bg-rose-500' };

/** Plain verdict on the strategy, honest about sample size. */
const verdict = computed(() => {
  const e = edgeStats(closedTrades.value);
  const n = closedTrades.value.length;
  if (!n) return tr('home.verdict.none');
  const main =
    e.payoff === null
      ? tr('home.verdict.wins', { wins: e.wins }, n)
      : e.payoff >= 1
        ? tr('home.verdict.winsBigger', { wins: e.wins }, n)
        : tr('home.verdict.lossesBigger', { wins: e.wins }, n);
  return n < 30 ? `${main} ${tr('home.verdict.early')}` : main;
});

/** Recent activity as plain sentences. */
const events = computed(() => {
  const out: {
    key: string;
    ts: number;
    icon: string;
    color: string;
    text: string;
    money: boolean;
  }[] = [];
  const all: (Trade | ClosedTrade)[] = [...openTrades.value, ...closedTrades.value];
  for (const t of all) {
    const coin = t.pair.split('/')[0];
    out.push({
      key: `b${t.trade_id}`,
      ts: t.open_timestamp,
      icon: 'i-mdi-cart-arrow-down',
      color: 'text-brand-400',
      text: tr('home.events.bought', {
        coin,
        amount: novaMoney(t.stake_amount, currency.value, 0),
      }),
      money: true,
    });
    const k = kevRecords.value.get(t.trade_id);
    if (k)
      out.push({
        key: `k${t.trade_id}`,
        ts: t.open_timestamp - 1,
        icon: 'i-mdi-newspaper-variant-outline',
        color: 'text-secondary',
        text:
          k.reason === 'no_news'
            ? tr('home.events.newsNone', { coin })
            : tr('home.events.newsRead', { coin }, k.headlines ?? 0),
        money: false,
      });
    if ('close_timestamp' in t && t.close_timestamp) {
      const win = (t.profit_abs ?? 0) >= 0;
      const reason = plainExitReason(t.exit_reason);
      out.push({
        key: `s${t.trade_id}`,
        ts: t.close_timestamp,
        icon: win ? 'i-mdi-trending-up' : 'i-mdi-trending-down',
        color: win ? 'text-emerald-400' : 'text-rose-400',
        text: tr(win ? 'home.events.soldProfit' : 'home.events.soldLoss', {
          coin,
          amount: novaMoney(Math.abs(t.profit_abs ?? 0), currency.value, 2),
          // German capitalizes nouns, so only lower-case the reason in English and Romanian.
          reason: currentLocale() === 'de' ? reason : reason.toLowerCase(),
        }),
        money: true,
      });
    }
  }
  return out.sort((a, b) => b.ts - a.ts).slice(0, 6);
});

async function pauseBuying() {
  if (
    await confirm({
      title: tr('home.confirm.pauseTitle'),
      message: tr('home.confirm.pauseMessage'),
    })
  )
    await bot.value.stopBuy();
}
async function resumeBuying() {
  if (
    await confirm({
      title: tr('home.confirm.resumeTitle'),
      message: tr('home.confirm.resumeMessage'),
    })
  )
    await bot.value.startBot();
}
async function startBot() {
  if (
    await confirm({
      title: tr('home.confirm.startTitle'),
      message: tr('home.confirm.startMessage'),
    })
  )
    await bot.value.startBot();
}
function openCoin(t: Trade) {
  bot.value.setDetailTrade(t);
  router.push('/positions');
}
const coinOf = (t: Trade) => t.base_currency ?? t.pair.split('/')[0];
const tone = (v: number | null | undefined) =>
  (v ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400';
const ease = 'transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)]';
</script>

<template>
  <div
    class="mx-auto flex w-full max-w-5xl flex-col gap-6 px-4 py-6 text-left sm:px-6 sm:py-8 lg:py-12"
  >
    <!-- Is the bot OK? One status line with a colored dot. -->
    <section
      class="flex flex-col gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center sm:p-6"
      :class="statusBox[status.tone]"
      aria-live="polite"
    >
      <div class="flex min-w-0 flex-1 items-start gap-3">
        <span class="relative mt-2 flex size-3 shrink-0">
          <span
            v-if="status.tone === 'good'"
            class="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400/60"
          />
          <span class="relative inline-flex size-3 rounded-full" :class="dotClass[status.tone]" />
        </span>
        <div class="min-w-0">
          <h1 class="text-lg font-semibold text-balance text-highlighted">{{ status.title }}</h1>
          <p class="mt-1 text-sm text-pretty text-muted">{{ status.text }}</p>
        </div>
      </div>
      <UButton
        v-if="buyingPaused"
        color="primary"
        variant="solid"
        size="lg"
        icon="i-mdi-play"
        class="w-full justify-center rounded-xl font-semibold sm:w-auto"
        @click="resumeBuying"
        >{{ tr('home.actions.resumeBuying') }}</UButton
      >
      <UButton
        v-else-if="state === 'running'"
        color="neutral"
        variant="outline"
        size="lg"
        icon="i-mdi-pause"
        class="w-full justify-center rounded-xl font-semibold sm:w-auto"
        @click="pauseBuying"
        >{{ tr('home.actions.pauseBuying') }}</UButton
      >
      <UButton
        v-else-if="bot?.isBotOnline && state === 'stopped'"
        color="primary"
        variant="solid"
        size="lg"
        icon="i-mdi-play"
        class="w-full justify-center rounded-xl font-semibold sm:w-auto"
        @click="startBot"
        >{{ tr('home.actions.start') }}</UButton
      >
    </section>

    <!-- Is my money OK? The hero card. -->
    <section
      class="grid gap-6 rounded-2xl border border-default/70 bg-elevated/60 p-6 sm:p-8 lg:grid-cols-2 lg:gap-8"
      aria-labelledby="nova-money-title"
    >
      <div class="flex min-w-0 flex-col">
        <div class="flex items-center justify-between gap-3">
          <h2 id="nova-money-title" class="text-sm font-medium text-muted">
            {{ tr('home.money.title') }}
          </h2>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="flex size-8 items-center justify-center rounded-full text-muted hover:bg-accented hover:text-default focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
              :class="ease"
              :aria-label="privacy ? tr('home.money.showAmounts') : tr('home.money.hideAmounts')"
              :title="privacy ? tr('home.money.showAmounts') : tr('home.money.hideAmounts')"
              @click="togglePrivacy"
            >
              <UIcon
                :name="privacy ? 'i-mdi-eye-off-outline' : 'i-mdi-eye-outline'"
                class="size-4"
              />
            </button>
            <span
              v-if="paper"
              class="inline-flex items-center gap-1 rounded-full bg-secondary/15 px-3 py-1 text-xs font-semibold text-secondary"
              :title="tr('home.money.practiceHint')"
            >
              <UIcon name="i-mdi-school-outline" class="size-4" />{{ tr('common.practiceMoney') }}
            </span>
            <RouterLink
              v-if="paper"
              to="/wallet#practice"
              class="inline-flex h-8 min-w-8 shrink-0 items-center justify-center gap-1 rounded-full text-xs font-medium whitespace-nowrap text-muted hover:bg-accented hover:text-default focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98] sm:px-2"
              :class="ease"
              :title="tr('home.money.addPracticeTitle')"
              :aria-label="tr('home.money.addPracticeAria')"
            >
              <UIcon name="i-mdi-plus" class="size-4" /><span class="hidden sm:inline">{{
                tr('home.money.addMoney')
              }}</span>
            </RouterLink>
            <span
              v-else
              class="inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-3 py-1 text-xs font-semibold text-rose-300"
              :title="tr('home.money.realHint')"
            >
              <UIcon name="i-mdi-cash" class="size-4" />{{ tr('common.realMoney') }}
            </span>
          </div>
        </div>

        <USkeleton v-if="loading" class="mt-4 h-12 w-56 rounded-xl" />
        <div v-else class="mt-4 flex flex-wrap items-baseline gap-x-2">
          <span
            class="nova-num nova-money text-5xl font-semibold tracking-tight text-highlighted sm:text-6xl"
            >{{ moneyNumber }}</span
          >
          <span class="text-xl font-medium text-muted">{{ currency }}</span>
        </div>

        <USkeleton v-if="loading" class="mt-4 h-8 w-64 rounded-full" />
        <div v-else class="mt-4 flex flex-wrap items-center gap-2 text-sm">
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
            <span>({{ novaPct(changePct, 1, true) }})</span>
          </span>
          <span class="text-muted">{{ tr('home.money.sinceStart') }}</span>
        </div>

        <I18nT
          v-if="paper"
          keypath="home.money.practiceNote"
          tag="p"
          scope="global"
          class="mt-4 text-sm text-pretty text-muted"
        >
          <template #label
            ><span class="font-semibold text-secondary">{{
              tr('home.money.practiceLabel')
            }}</span></template
          >
        </I18nT>
        <I18nT
          v-else
          keypath="home.money.realNote"
          tag="p"
          scope="global"
          class="mt-4 text-sm text-pretty text-muted"
        >
          <template #label
            ><span class="font-semibold text-rose-300">{{
              tr('home.money.realLabel')
            }}</span></template
          >
        </I18nT>

        <dl class="mt-6 grid grid-cols-2 gap-3 lg:mt-auto lg:pt-6">
          <div class="rounded-xl bg-default/50 p-4">
            <dt class="text-xs text-muted">{{ tr('home.money.today') }}</dt>
            <dd class="nova-num nova-money mt-1 text-xl font-semibold" :class="tone(todayPnl)">
              {{ novaMoney(todayPnl, currency, 2, true) }}
            </dd>
            <dd class="mt-1 text-xs text-dimmed">{{ tr('home.money.todaySub') }}</dd>
          </div>
          <div class="rounded-xl bg-default/50 p-4">
            <dt class="text-xs text-muted">{{ tr('home.money.holding') }}</dt>
            <dd class="nova-num nova-money mt-1 text-xl font-semibold" :class="tone(unrealized)">
              {{ novaMoney(unrealized, currency, 2, true) }}
            </dd>
            <dd class="mt-1 text-xs text-dimmed">{{ tr('home.money.holdingSub') }}</dd>
          </div>
        </dl>
      </div>

      <div class="flex min-h-40 flex-col">
        <USkeleton v-if="loading" class="h-full min-h-40 w-full rounded-xl" />
        <NovaSparkline v-else :values="sparkValues" class="nova-money min-h-40 w-full flex-1" />
        <p class="mt-2 text-xs text-dimmed">{{ tr('home.money.chartCaption') }}</p>
      </div>
    </section>

    <!-- What does it hold, what did it do? -->
    <div class="grid gap-6 lg:grid-cols-2">
      <section class="rounded-2xl border border-default/70 bg-elevated/40 p-2">
        <div class="flex items-center justify-between px-4 pt-4 pb-2">
          <h2 class="text-lg font-semibold text-highlighted">{{ tr('home.coins.title') }}</h2>
          <RouterLink
            to="/positions"
            class="inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-semibold text-brand-300 hover:bg-brand-400/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60"
            :class="ease"
            >{{ tr('common.seeAll') }}<UIcon name="i-mdi-chevron-right" class="size-4"
          /></RouterLink>
        </div>
        <div v-if="!openTrades.length" class="flex items-center gap-3 px-4 pt-2 pb-4">
          <span class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented">
            <UIcon name="i-mdi-hand-coin-outline" class="size-5 text-muted" />
          </span>
          <p class="text-sm text-pretty text-muted">
            {{ tr('home.coins.empty') }}
          </p>
        </div>
        <ul v-else>
          <li v-for="t in openTrades" :key="t.trade_id">
            <button
              type="button"
              class="flex min-h-16 w-full items-center gap-3 rounded-lg px-4 py-3 text-left hover:bg-accented/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
              :class="ease"
              @click="openCoin(t)"
            >
              <span
                class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented text-xs font-semibold text-highlighted"
                >{{ coinOf(t).slice(0, 4) }}</span
              >
              <span class="min-w-0 flex-1">
                <span class="block truncate font-semibold text-highlighted">{{ coinOf(t) }}</span>
                <span class="block text-xs text-muted">{{
                  tr('home.coins.bought', { ago: plainAgo(t.open_timestamp, now.getTime()) })
                }}</span>
              </span>
              <span class="nova-num text-right">
                <span class="block text-base font-semibold" :class="tone(t.profit_ratio)">{{
                  novaPct(t.profit_ratio, 1, true)
                }}</span>
                <span class="nova-money block text-xs" :class="tone(t.profit_abs)">{{
                  novaMoney(t.profit_abs, currency, 2, true)
                }}</span>
              </span>
            </button>
          </li>
        </ul>
      </section>

      <section class="rounded-2xl border border-default/70 bg-elevated/40 p-6">
        <h2 class="text-lg font-semibold text-highlighted">{{ tr('home.events.title') }}</h2>
        <p v-if="!events.length" class="mt-4 text-sm text-muted">
          {{ tr('home.events.empty') }}
        </p>
        <ol v-else class="mt-4">
          <li v-for="(e, i) in events" :key="e.key" class="relative flex gap-3 pb-4 last:pb-0">
            <span
              v-if="i < events.length - 1"
              class="absolute top-8 bottom-0 left-4 w-px -translate-x-1/2 bg-accented"
              aria-hidden="true"
            />
            <span
              class="relative flex size-8 shrink-0 items-center justify-center rounded-full bg-accented"
            >
              <UIcon :name="e.icon" class="size-4" :class="e.color" />
            </span>
            <div class="min-w-0 flex-1 pt-1">
              <p class="text-sm text-pretty text-default" :class="{ 'nova-money': e.money }">
                {{ e.text }}
              </p>
              <p class="mt-1 text-xs text-dimmed">{{ plainAgo(e.ts, now.getTime()) }}</p>
            </div>
          </li>
        </ol>
      </section>
    </div>

    <!-- The strategy verdict, collapsed to one quiet line. -->
    <section class="flex items-start gap-3 rounded-2xl border border-default/70 px-6 py-4">
      <UIcon name="i-mdi-chart-timeline-variant" class="mt-1 size-5 shrink-0 text-brand-400" />
      <div class="min-w-0 text-sm">
        <h2 class="font-semibold text-highlighted">{{ tr('home.verdict.title') }}</h2>
        <p class="mt-1 text-pretty text-muted">
          {{ verdict }}
          <I18nT keypath="home.verdict.proHint" tag="span" scope="global">
            <template #pro
              ><span class="font-semibold text-default">{{ tr('common.pro') }}</span></template
            >
          </I18nT>
        </p>
      </div>
    </section>
  </div>
</template>
