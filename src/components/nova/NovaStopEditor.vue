<script setup lang="ts">
/**
 * Stop editor for one open trade: presets (break-even, lock in a profit) or a custom price, with a live
 * preview line on the chart (v-model:preview). Sends the new stop to the control service; the engine only
 * lets a stop move up, so the editor explains and checks that before sending.
 */
import type { Trade } from '@/types';
import type { NovaManualStop, NovaTradeLevels } from '@/composables/useNovaControl';
import {
  breakEvenPrice,
  checkNewStop,
  novaPriceText,
  priceForProfit,
  profitAtPrice,
} from '@/utils/novaPosition';

const props = defineProps<{
  trade: Trade;
  currency: string;
  manualStop: NovaManualStop | null;
  /** Engine-side levels (break-even incl. funding, liquidation, price tick) when the control service has them. */
  engineLevels?: NovaTradeLevels | null;
  /** Price picked on the chart (right-click "set stop here"): starts the editor on a custom price. */
  initialPrice?: number | null;
}>();
const preview = defineModel<number | null>('preview', { default: null });
const emit = defineEmits<{ close: [] }>();

const { t: tr } = useI18n();
const { simple } = useNovaMode();
const { setStop } = useNovaControl();

const now = computed(() => props.trade.current_rate ?? null);
const stop = computed(() => props.trade.stop_loss_abs || null);
const inProfit = computed(() => (props.trade.profit_ratio ?? 0) > 0);
const liquidation = computed(
  () => props.engineLevels?.liquidation ?? props.trade.liquidation_price ?? null,
);
const tick = computed(() => props.engineLevels?.price_tick ?? null);
/** Round to the market tick (the service does the same), so the preview shows the real price. */
function toTick(p: number): number {
  const tk = tick.value;
  if (!tk) return p;
  return Number((Math.round(p / tk) * tk).toFixed(Math.max(0, Math.ceil(-Math.log10(tk)))));
}
const valid = (p: number | null | undefined) =>
  checkNewStop(p, stop.value, now.value, liquidation.value).ok;

type Choice = { key: string; label: string; sub: string; price: number };
const presets = computed<Choice[]>(() => {
  const t = props.trade;
  const out: Choice[] = [];
  const beRaw = props.engineLevels?.break_even ?? breakEvenPrice(t);
  // Round up so break-even really covers the fees.
  const be = beRaw && tick.value ? toTick(beRaw + tick.value / 2) : beRaw;
  if (be && valid(be))
    out.push({
      key: 'be',
      label: tr('stop.preset.breakeven'),
      sub: simple.value ? tr('stop.preset.breakevenSimple') : tr('stop.preset.breakevenPro'),
      price: be,
    });
  if (inProfit.value) {
    for (const pct of [0.01, 0.02, 0.05, 0.1]) {
      const raw = priceForProfit(t, pct);
      const p = raw ? toTick(raw) : null;
      if (p && valid(p))
        out.push({
          key: `lock-${pct}`,
          label: tr('stop.preset.lockIn', { pct: pct * 100 }),
          sub: tr('stop.preset.keeps', {
            money: novaMoney(profitAtPrice(t, p).abs, props.currency, 2, true),
          }),
          price: p,
        });
    }
  }
  return out.slice(0, 4);
});

const choice = ref<string | null>(null);
const custom = ref<number | undefined>(undefined);
const busy = ref<'set' | 'remove' | null>(null);
const problem = ref<string | null>(null);

const target = computed<number | null>(() => {
  if (choice.value === 'custom') return custom.value ?? null;
  return presets.value.find((p) => p.key === choice.value)?.price ?? null;
});
watch(
  target,
  (p) => {
    preview.value = p;
    problem.value = null;
  },
  { immediate: true },
);
onBeforeUnmount(() => (preview.value = null));
watch(
  () => props.initialPrice,
  (p) => {
    if (!p) return;
    custom.value = toTick(p);
    choice.value = 'custom';
  },
  { immediate: true },
);

function pick(key: string) {
  choice.value = key;
}
function onCustom(v: number | null | undefined) {
  custom.value = v ?? undefined;
  choice.value = 'custom';
}

const check = computed(() => checkNewStop(target.value, stop.value, now.value, liquidation.value));
/** Price step for the custom input: the market tick, else about 0.1 % of the price as a power of ten. */
const step = computed(() => {
  if (tick.value) return tick.value;
  const p = now.value ?? props.trade.open_rate;
  return 10 ** Math.floor(Math.log10(Math.max(p * 0.001, 1e-8)));
});
const decimals = computed(() =>
  Math.min(10, Math.max(0, Math.ceil(-Math.log10(step.value) - 1e-9))),
);

const outcome = computed(() => {
  const p = target.value;
  if (!p || !check.value.ok) return null;
  const res = profitAtPrice(props.trade, p);
  const dist = now.value ? p / now.value - 1 : 0;
  const money = novaMoney(res.abs, props.currency, 2, true);
  if (!simple.value)
    return tr('stop.outcome.pro', {
      dist: novaPct(dist, 1, true),
      money,
      pct: novaPct(res.ratio, 1, true),
    });
  const vars = {
    pct: novaPct(-dist, 1),
    price: novaPriceText(p),
    money: novaMoney(Math.abs(res.abs), props.currency, 2),
  };
  return res.abs >= 0 ? tr('stop.outcome.keep', vars) : tr('stop.outcome.lose', vars);
});

const currentText = computed(() => {
  const s = stop.value;
  if (!s) return simple.value ? tr('stop.current.noneSimple') : tr('stop.current.nonePro');
  const res = profitAtPrice(props.trade, s);
  const dist = now.value ? s / now.value - 1 : 0;
  return simple.value
    ? tr('stop.current.simple', {
        price: novaPriceText(s),
        pct: novaPct(-dist, 1),
        money: novaMoney(res.abs, props.currency, 2, true),
      })
    : tr('stop.current.pro', {
        price: novaPriceText(s),
        dist: novaPct(dist, 1, true),
        money: novaMoney(res.abs, props.currency, 2, true),
      });
});

async function apply() {
  const p = target.value;
  if (!p || !check.value.ok) return;
  busy.value = 'set';
  problem.value = null;
  try {
    const res = await setStop(props.trade.trade_id, toTick(Number(p.toPrecision(10))));
    const coin = props.trade.pair.split('/')[0];
    if (res.closed)
      showAlert(
        simple.value
          ? tr('stop.toast.soldSimple', { price: novaPriceText(res.manual_stop ?? p), coin })
          : tr('stop.toast.soldPro', { pair: props.trade.pair }),
        'warning',
      );
    else {
      const vars = { coin, price: novaPriceText(res.stop_loss_abs ?? res.manual_stop ?? p) };
      const done = simple.value ? tr('stop.toast.setSimple', vars) : tr('stop.toast.setPro', vars);
      showAlert(res.note ? `${done} ${res.note}` : done, 'success');
    }
    emit('close');
  } catch (e) {
    problem.value = controlErrorText(e);
  } finally {
    busy.value = null;
  }
}

async function removeOverride() {
  busy.value = 'remove';
  problem.value = null;
  try {
    const res = await setStop(props.trade.trade_id, null);
    showAlert(res.note ?? tr('stop.toast.removed', { pair: props.trade.pair }), 'success');
    emit('close');
  } catch (e) {
    problem.value = controlErrorText(e);
  } finally {
    busy.value = null;
  }
}
</script>

<template>
  <section class="nova-tile flex flex-col gap-4 p-4" data-testid="nova-stop-editor">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h3 class="text-base font-semibold text-highlighted">
          {{ simple ? tr('stop.title.simple') : tr('stop.title.pro') }}
        </h3>
        <p class="nova-money mt-1 text-sm text-pretty text-muted">{{ currentText }}</p>
      </div>
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        icon="i-mdi-close"
        :aria-label="tr('stop.closeAria')"
        @click="emit('close')"
      />
    </div>

    <div class="flex items-start gap-2 text-sm text-pretty text-muted">
      <UIcon name="i-mdi-arrow-up-bold-outline" class="mt-0.5 size-4 shrink-0 text-brand-400" />
      <p>
        {{ simple ? tr('stop.rule.simple') : tr('stop.rule.pro') }}
      </p>
    </div>

    <div v-if="presets.length" class="grid gap-2 sm:grid-cols-2">
      <button
        v-for="p in presets"
        :key="p.key"
        type="button"
        class="flex min-h-10 flex-col items-start rounded-xl border px-3 py-2 text-left transition duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 active:scale-[0.98]"
        :class="
          choice === p.key
            ? 'border-brand-400/60 bg-brand-400/10'
            : 'border-default/70 hover:bg-accented/60'
        "
        :aria-pressed="choice === p.key"
        @click="pick(p.key)"
      >
        <span class="flex w-full items-baseline justify-between gap-2">
          <span class="text-sm font-semibold text-highlighted">{{ p.label }}</span>
          <span class="nova-num text-sm text-default">{{ novaPriceText(p.price) }}</span>
        </span>
        <span class="nova-money text-xs text-muted">{{ p.sub }}</span>
      </button>
    </div>
    <p v-else-if="!inProfit" class="text-sm text-pretty text-muted">
      {{ simple ? tr('stop.notInProfit.simple') : tr('stop.notInProfit.pro') }}
    </p>

    <UFormField
      :label="simple ? tr('stop.custom.labelSimple') : tr('stop.custom.labelPro')"
      :error="
        choice === 'custom' && custom !== undefined && !check.ok ? (check.reason ?? true) : false
      "
    >
      <UInputNumber
        :model-value="custom"
        :step="step"
        :step-snapping="false"
        :format-options="{ maximumFractionDigits: decimals + 2, useGrouping: false }"
        :placeholder="
          stop ? tr('stop.custom.above', { price: novaPriceText(stop) }) : tr('stop.custom.price')
        "
        class="w-full sm:w-64"
        @update:model-value="onCustom"
        @focus="choice = 'custom'"
      />
    </UFormField>

    <p v-if="outcome" class="nova-num nova-money text-sm text-pretty text-default">
      {{ outcome }}
    </p>

    <p v-if="busy" class="flex items-center gap-2 text-sm text-muted">
      <UIcon name="i-mdi-timer-sand" class="size-4 shrink-0" />
      {{ simple ? tr('stop.waiting.simple') : tr('stop.waiting.pro') }}
    </p>

    <UAlert
      v-if="problem"
      color="error"
      variant="subtle"
      icon="i-mdi-alert-circle-outline"
      :title="tr('stop.problem')"
      :description="problem"
    />

    <div class="flex flex-wrap items-center gap-2">
      <UButton
        color="primary"
        variant="solid"
        icon="i-mdi-shield-check-outline"
        class="justify-center rounded-xl font-semibold max-sm:min-h-10 max-sm:w-full"
        :disabled="!target || !check.ok"
        :loading="busy === 'set'"
        @click="apply"
        >{{
          target && check.ok
            ? simple
              ? tr('stop.apply.setSimple', { price: novaPriceText(target) })
              : tr('stop.apply.setPro', { price: novaPriceText(target) })
            : simple
              ? tr('stop.apply.pickSimple')
              : tr('stop.apply.pickPro')
        }}</UButton
      >
      <UButton
        color="neutral"
        variant="ghost"
        class="justify-center max-sm:min-h-10 max-sm:w-full"
        @click="emit('close')"
        >{{ tr('common.cancel') }}</UButton
      >
      <div v-if="manualStop" class="flex items-center gap-2 sm:ms-auto">
        <UButton
          color="neutral"
          variant="outline"
          icon="i-mdi-restore"
          class="justify-center max-sm:min-h-10 max-sm:w-full"
          :loading="busy === 'remove'"
          :title="simple ? tr('stop.remove.titleSimple') : tr('stop.remove.titlePro')"
          @click="removeOverride"
          >{{ tr('stop.remove.button') }}</UButton
        >
      </div>
    </div>
  </section>
</template>
