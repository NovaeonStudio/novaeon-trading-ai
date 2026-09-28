<script setup lang="ts">
import type { Trade } from '@/types';
import { sentinelOffline, sentinelReasonText, type KevRecord } from './kev';
import { distanceToLiquidation, distanceToStop, excursion, lossAtStop } from '@/utils/novaMetrics';

const props = defineProps<{ trade: Trade; currency: string; kev?: KevRecord | null }>();
const emit = defineEmits<{ open: [trade: Trade] }>();
const { simple } = useNovaMode();
const { t: tr } = useI18n();

const t = computed(() => props.trade);
const pnlTone = computed(() =>
  (t.value.profit_abs ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400',
);
const lev = computed(() => t.value.leverage ?? 1);
const coin = computed(() => t.value.base_currency ?? t.value.pair.split('/')[0]);
const stopDist = computed(() => distanceToStop(t.value));
const liqDist = computed(() => distanceToLiquidation(t.value));
const exc = computed(() => excursion(t.value));

/** Price ruler: stop … entry … current, plus the best price seen (MFE tick). */
const ruler = computed(() => {
  const cur = t.value.current_rate ?? t.value.open_rate;
  const pts = [
    t.value.stop_loss_abs,
    t.value.open_rate,
    cur,
    t.value.max_rate,
    t.value.min_rate,
  ].filter((v): v is number => typeof v === 'number' && v > 0);
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const pos = (v?: number) => (v && hi > lo ? ((v - lo) / (hi - lo)) * 100 : 50);
  return {
    stop: pos(t.value.stop_loss_abs),
    entry: pos(t.value.open_rate),
    current: pos(cur),
    best: pos(t.value.is_short ? t.value.min_rate : t.value.max_rate),
    up: (cur - t.value.open_rate) * (t.value.is_short ? -1 : 1) >= 0,
  };
});

const age = computed(() =>
  simple.value
    ? plainDuration(Date.now() - t.value.open_timestamp)
    : novaAge(t.value.open_timestamp),
);
const kevLabel = computed(() => {
  const k = props.kev;
  if (!k) return null;
  if (simple.value) {
    if (k.reason === 'no_news') return tr('positions.card.aiNoNews');
    if (sentinelOffline(k.reason)) return tr('positions.card.aiOffline');
    return tr('positions.card.aiNewsOk');
  }
  if (k.reason === 'no_news') return tr('positions.card.sentinelNoNews');
  if (sentinelOffline(k.reason)) return tr('positions.card.sentinelOffline');
  return tr('positions.card.sentinelRisk', { pct: Math.round((k.p_negative ?? 0) * 100) });
});
const kevHint = computed(() => {
  const k = props.kev;
  if (!k) return tr('positions.card.hintNoRecord');
  const out = k.outlook
    ? Object.entries(k.outlook)
        .map(([key, v]) => `${key.replaceAll('_', ' ')} ${Math.round(v * 100)}%`)
        .join(' · ')
    : tr('positions.card.hintNoOutlook');
  const lev = tr('positions.card.hintLeverage', {
    lev: k.leverage,
    reason: sentinelReasonText(k.leverage_reason),
  });
  return `${lev}\n${out}\n${(k.titles ?? []).slice(0, 3).join('\n')}`;
});
</script>

<template>
  <button
    type="button"
    class="nova-panel group w-full p-4 text-left transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:border-brand-400/40 hover:bg-accented/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
    @click="emit('open', t)"
  >
    <div class="flex items-center justify-between gap-2">
      <div class="flex min-w-0 items-center gap-2">
        <span
          v-if="!simple"
          class="flex size-10 shrink-0 items-center justify-center rounded-full bg-accented text-xs font-semibold text-highlighted"
          aria-hidden="true"
          >{{ coin.slice(0, 4) }}</span
        >
        <span class="truncate font-semibold text-highlighted">{{ coin }}</span>
        <span
          v-if="!simple"
          class="nova-num shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold"
          :class="
            lev > 1
              ? 'bg-brand-400/15 text-brand-600 dark:text-brand-300'
              : 'bg-accented text-muted'
          "
          >{{ lev }}x</span
        >
        <span
          v-if="t.is_short"
          class="shrink-0 rounded-full bg-rose-500/15 px-2 py-0.5 text-xs font-medium text-rose-400"
          >{{ tr('positions.card.short') }}</span
        >
      </div>
      <span class="nova-num shrink-0 text-xs text-dimmed">{{ age }}</span>
    </div>

    <div class="mt-3 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
      <span
        class="nova-num font-semibold tracking-tight"
        :class="[pnlTone, simple ? 'text-xl' : 'text-2xl']"
        >{{ novaPct(t.profit_ratio, 2, true) }}</span
      >
      <span class="nova-num nova-money text-sm font-medium" :class="pnlTone">{{
        novaMoney(t.profit_abs, currency, 2, true)
      }}</span>
    </div>

    <!-- stop … entry … now, with a tick at the best price so far -->
    <div
      class="relative mt-4 h-4"
      :title="
        tr('positions.card.rulerTitle', {
          stop: formatPrice(t.stop_loss_abs, 6),
          entry: formatPrice(t.open_rate, 6),
          now: formatPrice(t.current_rate ?? null, 6),
          best: formatPrice(t.max_rate ?? null, 6),
        })
      "
    >
      <div class="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-accented" />
      <div
        class="absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
        :class="ruler.up ? 'bg-emerald-500/70' : 'bg-rose-500/70'"
        :style="{
          left: `${Math.min(ruler.entry, ruler.current)}%`,
          width: `${Math.abs(ruler.current - ruler.entry)}%`,
        }"
      />
      <div
        class="absolute top-0 h-4 w-0.5 -translate-x-1/2 rounded-full bg-rose-400"
        :style="{ left: `${ruler.stop}%` }"
      />
      <div
        class="absolute top-0.5 h-3 w-0.5 -translate-x-1/2 rounded-full bg-muted"
        :style="{ left: `${ruler.entry}%` }"
      />
      <div
        class="absolute top-1 h-2 w-0.5 -translate-x-1/2 rounded-full bg-emerald-300/70"
        :style="{ left: `${ruler.best}%` }"
      />
      <div
        class="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-default"
        :class="ruler.up ? 'bg-emerald-400' : 'bg-rose-400'"
        :style="{ left: `${ruler.current}%` }"
      />
    </div>
    <div class="mt-1 flex justify-between gap-2 text-xs text-dimmed">
      <span>{{ simple ? tr('positions.card.safetyStop') : tr('positions.card.stop') }}</span
      ><span>{{ simple ? tr('positions.card.rulerSimple') : tr('positions.card.rulerPro') }}</span>
    </div>

    <dl class="mt-3 grid grid-cols-3 gap-2">
      <div class="min-w-0">
        <dt class="nova-label truncate">
          {{ simple ? tr('positions.card.roomToStop') : tr('positions.card.toStop') }}
        </dt>
        <dd class="nova-num mt-0.5 text-sm font-medium text-default">
          {{ novaPct(stopDist, 1) }}
        </dd>
      </div>
      <div class="min-w-0">
        <dt class="nova-label truncate">
          {{
            simple
              ? tr('positions.card.lossIfStop')
              : liqDist !== null
                ? tr('positions.card.toLiquidation')
                : tr('positions.card.atStop')
          }}
        </dt>
        <dd
          class="nova-num mt-0.5 text-sm font-medium text-default"
          :class="{ 'nova-money': simple || liqDist === null }"
        >
          {{ simple || liqDist === null ? novaMoney(-lossAtStop(t), '', 2) : novaPct(liqDist, 1) }}
        </dd>
      </div>
      <div class="min-w-0">
        <dt class="nova-label truncate">
          {{
            simple
              ? tr('positions.card.heldFor')
              : t.funding_fees
                ? tr('positions.card.funding')
                : tr('positions.card.bestRun')
          }}
        </dt>
        <dd
          class="nova-num mt-0.5 text-sm font-medium text-default"
          :class="{ 'nova-money': !simple && !!t.funding_fees }"
        >
          {{
            simple
              ? age
              : t.funding_fees
                ? novaMoney(t.funding_fees, '', 3, true)
                : novaPct(exc?.mfe, 1, true)
          }}
        </dd>
      </div>
    </dl>

    <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
      <span
        class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium"
        :class="kev ? 'bg-secondary/15 text-secondary' : 'bg-accented text-muted'"
        :title="kevHint"
      >
        <span class="size-1.5 rounded-full" :class="kev ? 'bg-secondary' : 'bg-dimmed'" />
        {{
          kevLabel ??
          (simple ? tr('positions.card.aiNotRecorded') : tr('positions.card.sentinelNoRecord'))
        }}
      </span>
      <span v-if="!simple" class="nova-num truncate text-xs text-dimmed">{{
        t.enter_tag ?? novaStrategyName(t.strategy)
      }}</span>
    </div>
  </button>
</template>
