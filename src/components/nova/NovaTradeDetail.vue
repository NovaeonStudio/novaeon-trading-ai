<script setup lang="ts">
/** Full trade view: chart, numbers, Sentinel reasoning, actions. Used by Positions and Trades. */
import type { ClosedTrade, Trade } from '@/types';
import { sentinelReasonText, type KevRecord } from './kev';
import { distanceToLiquidation, distanceToStop, excursion } from '@/utils/novaMetrics';
import { I18nT } from 'vue-i18n';
import { intlLocale } from '@/i18n';

const props = defineProps<{ trade: Trade | ClosedTrade; currency: string }>();

const botStore = useBotStore();
const { confirm } = useConfirmBox();
const { simple } = useNovaMode();
const { t: tr } = useI18n();
const { manualStops, loadStops, tradeLevels } = useNovaControl();
const kev = ref<KevRecord | null>(null);
const busy = ref(false);

/** Stop editor (inline under the chart) with a live preview line, and the buy-more dialog. */
const editingStop = ref(false);
const previewStop = ref<number | null>(null);
const buyOpen = ref(false);
const manual = computed(() => {
  const m = manualStops.value[String(props.trade.trade_id)];
  return m && m.active !== false ? m : null;
});
const openTrade = computed(() => (props.trade.is_open ? (props.trade as Trade) : null));
/** Engine-side levels from the control service (break-even incl. funding, exit level, tick); null = compute locally. */
const levels = ref<NovaTradeLevels | null>(null);
async function loadLevels() {
  if (!props.trade.is_open) {
    levels.value = null;
    return;
  }
  levels.value = await tradeLevels(props.trade.trade_id).catch(() => null);
}
onMounted(() => {
  if (props.trade.is_open) loadStops().catch(() => undefined);
});
watch(() => props.trade.trade_id, loadLevels, { immediate: true });
// Re-read after the stop moved (the trade's stop comes back with the next refresh).
watch(() => (props.trade.is_open ? props.trade.stop_loss_abs : null), loadLevels);
useIntervalFn(() => {
  if (props.trade.is_open) loadLevels();
}, 60_000);
watch(
  () => props.trade.trade_id,
  () => {
    editingStop.value = false;
    previewStop.value = null;
  },
);
function toggleStopEditor() {
  editingStop.value = !editingStop.value;
  if (!editingStop.value) previewStop.value = null;
}
function closeStopEditor() {
  editingStop.value = false;
  previewStop.value = null;
}

watch(
  () => props.trade.trade_id,
  async (id) => {
    kev.value = null;
    const res = await botStore.activeBot.getCustomDataQuiet(id);
    kev.value = (res?.[0]?.custom_data.find((c) => c.key === 'kev')?.value as KevRecord) ?? null;
  },
  { immediate: true },
);

const t = computed(() => props.trade);
const up = computed(() => (t.value.profit_abs ?? 0) >= 0);
const exc = computed(() => excursion(t.value));
const kept = computed(() =>
  exc.value && exc.value.mfe > 0 ? (t.value.profit_ratio ?? 0) / exc.value.mfe : null,
);
const duration = computed(() => {
  const end =
    'close_timestamp' in t.value && t.value.close_timestamp ? t.value.close_timestamp : Date.now();
  return novaAge(t.value.open_timestamp, end);
});

const facts = computed(() => {
  const x = t.value;
  const nowRate = ('current_rate' in x ? x.current_rate : x.close_rate) ?? null;
  const fees = (x.fee_open_cost ?? 0) + (('fee_close_cost' in x ? x.fee_close_cost : 0) ?? 0);
  const rows: [string, string, boolean?][] = [];
  if (simple.value) {
    rows.push([tr('tradeDetail.simple.boughtAt'), novaPriceText(x.open_rate)]);
    rows.push([
      x.is_open ? tr('tradeDetail.simple.priceNow') : tr('tradeDetail.simple.soldAt'),
      novaPriceText(nowRate),
    ]);
    rows.push([
      tr('tradeDetail.simple.moneyPutIn'),
      novaMoney(x.stake_amount, props.currency, 2),
      true,
    ]);
    rows.push([
      x.is_open ? tr('tradeDetail.simple.heldFor') : tr('tradeDetail.simple.wasHeldFor'),
      duration.value,
    ]);
    if (x.is_open && x.stop_loss_abs)
      rows.push([
        manual.value
          ? tr('tradeDetail.simple.safetyStopByYou')
          : tr('tradeDetail.simple.safetyStop'),
        tr('tradeDetail.simple.safetyStopValue', {
          price: novaPriceText(x.stop_loss_abs),
          pct: novaPct(distanceToStop(x as Trade), 0),
        }),
      ]);
    if (!x.is_open) rows.push([tr('tradeDetail.simple.whySold'), plainExitReason(x.exit_reason)]);
    const costs = fees - (x.funding_fees ?? 0);
    if (costs)
      rows.push([
        tr('tradeDetail.simple.costs'),
        novaMoney(-Math.abs(costs), props.currency, 2),
        true,
      ]);
    return rows;
  }
  rows.push([tr('tradeDetail.pro.entry'), novaPriceText(x.open_rate)]);
  rows.push([
    x.is_open ? tr('tradeDetail.pro.now') : tr('tradeDetail.pro.exit'),
    novaPriceText(nowRate),
  ]);
  rows.push([tr('tradeDetail.pro.amount'), formatNumber(x.amount, 6)]);
  rows.push([tr('tradeDetail.pro.stake'), novaMoney(x.stake_amount, props.currency, 2), true]);
  rows.push([tr('tradeDetail.pro.leverage'), `${x.leverage ?? 1}x`]);
  rows.push([tr('tradeDetail.pro.duration'), duration.value]);
  if (x.is_open) {
    rows.push([
      manual.value ? tr('tradeDetail.pro.stopManual') : tr('tradeDetail.pro.stop'),
      `${novaPriceText(x.stop_loss_abs)} (${novaPct(distanceToStop(x as Trade), 1)})`,
    ]);
    if (x.liquidation_price)
      rows.push([
        tr('tradeDetail.pro.liquidation'),
        `${novaPriceText(x.liquidation_price)} (${novaPct(distanceToLiquidation(x as Trade), 1)})`,
      ]);
  } else {
    rows.push([tr('tradeDetail.pro.exitReason'), novaExitReason(x.exit_reason)]);
  }
  rows.push([tr('tradeDetail.pro.bestRun'), novaPct(exc.value?.mfe, 2, true)]);
  rows.push([tr('tradeDetail.pro.worstDip'), novaPct(exc.value?.mae, 2, true)]);
  if (x.funding_fees)
    rows.push([
      tr('tradeDetail.pro.funding'),
      novaMoney(x.funding_fees, props.currency, 3, true),
      true,
    ]);
  if (fees) rows.push([tr('tradeDetail.pro.fees'), novaMoney(-fees, props.currency, 3), true]);
  return rows;
});

async function close(fraction: 1 | 0.5) {
  const x = t.value;
  const coin = x.pair.split('/')[0];
  const title = simple.value
    ? fraction === 1
      ? tr('tradeDetail.close.sellAllTitle', { coin })
      : tr('tradeDetail.close.sellHalfTitle', { coin })
    : fraction === 1
      ? tr('tradeDetail.close.closeAllTitle')
      : tr('tradeDetail.close.closeHalfTitle');
  const paper = !!botStore.activeBot.botState?.dry_run;
  const ok = await confirm({
    title,
    message:
      fraction === 1
        ? paper
          ? tr('tradeDetail.close.fullPaper', { pair: x.pair })
          : tr('tradeDetail.close.fullReal', { pair: x.pair })
        : paper
          ? tr('tradeDetail.close.halfPaper', { pair: x.pair })
          : tr('tradeDetail.close.halfReal', { pair: x.pair }),
  });
  if (!ok) return;
  busy.value = true;
  try {
    await botStore.activeBot.forceexit({
      tradeid: String(x.trade_id),
      ordertype: 'market',
      ...(fraction < 1
        ? { amount: Number((x.amount * fraction).toFixed(x.amount_precision ?? 8)) }
        : {}),
    });
  } finally {
    busy.value = false;
  }
}

function outlookRows(k: KevRecord) {
  return Object.entries(k.outlook ?? {}).sort((a, b) => b[1] - a[1]);
}
</script>

<template>
  <div class="flex flex-col gap-4" :class="{ 'sm:gap-6': !simple }">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h2 class="text-2xl font-semibold text-highlighted">{{ t.pair.split('/')[0] }}</h2>
          <span class="text-sm text-muted">{{ t.pair }}</span>
          <span
            class="nova-num rounded-full bg-brand-400/15 px-2 py-0.5 text-xs font-semibold text-brand-600 dark:text-brand-300"
            >{{ t.leverage ?? 1 }}x</span
          >
          <span
            class="rounded-full px-2 py-0.5 text-xs font-semibold"
            :class="t.is_open ? 'bg-secondary/15 text-secondary' : 'bg-accented text-muted'"
            >{{ t.is_open ? tr('tradeDetail.badge.open') : tr('tradeDetail.badge.closed') }}</span
          >
          <span
            v-if="t.enter_tag === 'manual'"
            class="rounded-full bg-accented px-2 py-0.5 text-xs font-semibold text-default"
            >{{
              simple ? tr('tradeDetail.badge.boughtByYou') : tr('tradeDetail.badge.manual')
            }}</span
          >
        </div>
        <div class="nova-num mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span
            class="font-semibold tracking-tight"
            :class="[up ? 'text-emerald-400' : 'text-rose-400', simple ? 'text-3xl' : 'text-4xl']"
            >{{ novaPct(t.profit_ratio, 2, true) }}</span
          >
          <span class="nova-money text-lg" :class="up ? 'text-emerald-400' : 'text-rose-400'">{{
            novaMoney(t.profit_abs, currency, 2, true)
          }}</span>
          <span v-if="kept !== null" class="text-xs text-muted">{{
            simple
              ? tr('tradeDetail.keptSimple', { pct: novaPct(kept, 0) })
              : tr('tradeDetail.keptPro', { pct: novaPct(kept, 0) })
          }}</span>
        </div>
      </div>
      <div v-if="t.is_open" class="flex w-full flex-wrap gap-2 sm:w-auto">
        <UButton
          color="neutral"
          variant="outline"
          :size="simple ? 'sm' : 'md'"
          icon="i-mdi-circle-half-full"
          :class="{ 'flex-1 justify-center rounded-xl sm:flex-none': !simple }"
          :loading="busy"
          @click="close(0.5)"
          >{{
            simple ? tr('tradeDetail.action.sellHalf') : tr('tradeDetail.action.closeHalf')
          }}</UButton
        >
        <UButton
          color="error"
          variant="soft"
          :size="simple ? 'sm' : 'md'"
          icon="i-mdi-close-circle-outline"
          :class="{ 'flex-1 justify-center rounded-xl sm:flex-none': !simple }"
          :loading="busy"
          @click="close(1)"
          >{{
            simple ? tr('tradeDetail.action.sellNow') : tr('tradeDetail.action.closeAll')
          }}</UButton
        >
      </div>
    </div>

    <div class="nova-panel flex flex-col gap-4 p-3 sm:p-4">
      <NovaTradeChart
        :trade="t"
        :kev="kev"
        :preview-stop="editingStop ? previewStop : null"
        :manual-stop="!!manual"
        :engine-levels="levels"
        :editable-stop="!!openTrade"
        @edit-stop="editingStop = true"
      />
      <!-- Position actions right under the chart -->
      <div
        v-if="openTrade"
        class="flex flex-col gap-3 border-t border-default/50 pt-4 sm:flex-row sm:items-center"
      >
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-2 text-sm text-muted">
          <span
            v-if="manual"
            class="nova-num inline-flex items-center gap-1 rounded-full bg-rose-500/15 px-3 py-1 text-xs font-semibold text-rose-400"
          >
            <UIcon name="i-mdi-hand-back-right-outline" class="size-3.5" />
            {{
              simple ? tr('tradeDetail.action.stopSetByYou') : tr('tradeDetail.action.manualStop')
            }}
            ·
            {{ novaPriceText(manual.price) }}
          </span>
          <span v-else class="text-pretty">{{
            simple ? tr('tradeDetail.action.hintSimple') : tr('tradeDetail.action.hintPro')
          }}</span>
        </div>
        <div class="grid gap-2 sm:flex" :class="simple ? 'grid-cols-1' : 'grid-cols-2'">
          <UButton
            color="neutral"
            :variant="editingStop ? 'soft' : 'outline'"
            icon="i-mdi-shield-edit-outline"
            class="justify-center rounded-xl max-sm:min-h-10"
            :aria-expanded="editingStop"
            @click="toggleStopEditor"
            >{{
              simple ? tr('tradeDetail.action.changeStop') : tr('tradeDetail.action.moveStop')
            }}</UButton
          >
          <UButton
            color="neutral"
            variant="outline"
            icon="i-mdi-cart-plus"
            class="justify-center rounded-xl max-sm:min-h-10"
            @click="buyOpen = true"
            >{{ tr('tradeDetail.action.buyMore') }}</UButton
          >
        </div>
      </div>
      <NovaStopEditor
        v-if="openTrade && editingStop"
        v-model:preview="previewStop"
        :trade="openTrade"
        :currency="currency"
        :manual-stop="manual"
        :engine-levels="levels"
        @close="closeStopEditor"
      />
    </div>
    <NovaBuyDialog
      v-if="openTrade"
      v-model:open="buyOpen"
      :trade="openTrade"
      :currency="currency"
    />

    <!-- Simple: plain rows. Pro: compact key/value tiles. -->
    <dl v-if="simple" class="nova-num grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
      <div
        v-for="[k, v, money] in facts"
        :key="k"
        class="flex justify-between gap-2 border-b border-default/50 pb-1"
      >
        <dt class="text-muted">{{ k }}</dt>
        <dd class="text-right text-default" :class="{ 'nova-money': money }">{{ v }}</dd>
      </div>
    </dl>
    <dl v-else class="grid grid-cols-2 gap-2 sm:grid-cols-3 2xl:grid-cols-4">
      <div v-for="[k, v, money] in facts" :key="k" class="nova-tile min-w-0 px-3 py-2">
        <dt class="nova-label truncate">{{ k }}</dt>
        <dd
          class="nova-num mt-0.5 truncate text-sm font-semibold text-highlighted"
          :class="{ 'nova-money': money }"
          :title="v"
        >
          {{ v }}
        </dd>
      </div>
    </dl>

    <section class="nova-panel p-4" :class="{ 'sm:p-6': !simple }">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 class="text-sm font-semibold text-highlighted">
          {{
            simple ? tr('tradeDetail.sentinel.titleSimple') : tr('tradeDetail.sentinel.titlePro')
          }}
        </h3>
        <span v-if="kev" class="nova-num text-xs text-muted">{{
          new Date(kev.time).toLocaleString(intlLocale())
        }}</span>
      </div>
      <p v-if="!kev" class="text-sm text-pretty text-muted">
        {{
          simple
            ? tr('tradeDetail.sentinel.noRecordSimple')
            : tr('tradeDetail.sentinel.noRecordPro')
        }}
      </p>
      <template v-else>
        <div class="nova-num flex flex-wrap items-center gap-2 text-xs">
          <span
            class="rounded-full px-3 py-1 font-semibold"
            :class="
              kev.decision === 'veto'
                ? 'bg-rose-500/15 text-rose-400'
                : 'bg-emerald-500/15 text-emerald-400'
            "
            >{{
              kev.decision === 'veto'
                ? tr('tradeDetail.sentinel.vetoed')
                : tr('tradeDetail.sentinel.allowed')
            }}</span
          >
          <I18nT
            keypath="tradeDetail.sentinel.leverage"
            tag="span"
            scope="global"
            class="rounded-full bg-accented px-3 py-1 text-muted"
          >
            <template #lev
              ><b class="font-semibold text-brand-600 dark:text-brand-300"
                >{{ kev.leverage ?? 1 }}x</b
              ></template
            >
            <template #reason>{{ sentinelReasonText(kev.leverage_reason ?? kev.reason) }}</template>
          </I18nT>
          <I18nT
            v-if="(kev.leverage_suggested ?? 1) > (kev.leverage ?? 1)"
            keypath="tradeDetail.sentinel.wouldHavePicked"
            tag="span"
            scope="global"
            class="rounded-full bg-accented px-3 py-1 text-muted"
          >
            <template #lev
              ><b class="font-semibold text-default">{{ kev.leverage_suggested }}x</b></template
            >
          </I18nT>
          <span class="rounded-full bg-accented px-3 py-1 text-muted">{{
            tr('tradeDetail.sentinel.headlines', kev.headlines ?? 0)
          }}</span>
          <I18nT
            v-if="kev.p_negative !== null && kev.p_negative !== undefined"
            keypath="tradeDetail.sentinel.badNewsRisk"
            tag="span"
            scope="global"
            class="rounded-full bg-accented px-3 py-1 text-muted"
          >
            <template #risk
              ><b class="font-semibold text-default"
                >{{ Math.round(kev.p_negative * 100) }}%</b
              ></template
            >
          </I18nT>
        </div>
        <div v-if="kev.outlook" class="mt-4 grid gap-2">
          <div
            v-for="[label, p] in outlookRows(kev)"
            :key="label"
            class="grid grid-cols-[minmax(0,9rem)_1fr_3rem] items-center gap-3 text-xs"
          >
            <span class="truncate text-muted">{{ label.replaceAll('_', ' ') }}</span>
            <span class="h-1 rounded-full bg-accented">
              <span
                class="block h-full rounded-full bg-secondary"
                :style="{ width: `${p * 100}%` }"
              />
            </span>
            <span class="nova-num text-right text-default">{{ Math.round(p * 100) }}%</span>
          </div>
        </div>
        <ul
          v-if="kev.titles?.length"
          class="mt-4 list-disc space-y-1 ps-5 text-xs text-pretty text-muted"
        >
          <li v-for="title in kev.titles" :key="title">{{ title }}</li>
        </ul>
      </template>
    </section>
  </div>
</template>
