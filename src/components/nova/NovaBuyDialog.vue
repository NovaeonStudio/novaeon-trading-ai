<script setup lang="ts">
/**
 * Manual buy: a new position (pick a coin, amount, leverage: Sentinel decides or 1–3×) or "buy more" for an open one.
 * "Let Sentinel decide" is only offered while AI leverage is on (Settings); otherwise the default is 1×.
 * Goes through the control service (POST /control/buy): new coins pass Sentinel's news check (it can block the buy),
 * an open position keeps its leverage and allows at most 4 buys. The dialog itself is the confirmation, in plain
 * words, and says "real money" only when the bot is not in practice mode.
 */
import type { Trade } from '@/types';
import { NOVA_MAX_BUYS } from '@/composables/useNovaControl';
import { novaPriceText } from '@/utils/novaPosition';

const props = defineProps<{
  /** Open position to add to; without it the dialog opens a new position. */
  trade?: Trade | null;
  currency: string;
}>();
const open = defineModel<boolean>('open', { default: false });

const { t: tr } = useI18n();
const botStore = useBotStore();
const { simple } = useNovaMode();
const { buy: controlBuy, botSettings, loadSettings } = useNovaControl();
/** Sentinel may pick the leverage (AI leverage switched on and not locked on this Mac). */
const aiLeverage = computed(() => !!botSettings.value?.ai_leverage);
const aiLocked = computed(() => !!botSettings.value && !botSettings.value.ai_leverage_allowed);

const bot = computed(() => botStore.activeBot);
const state = computed(() => bot.value.botState);
const adding = computed(() => !!props.trade);
const dryRun = computed(() => state.value?.dry_run !== false);
const futures = computed(() => state.value?.trading_mode === 'futures');
/** Buys already in the open position (the service allows NOVA_MAX_BUYS). */
const entries = computed(() => {
  const t = props.trade;
  if (!t) return 0;
  return (
    t.nr_of_successful_entries ??
    (t.orders ?? []).filter((o) => o.ft_is_entry && (o.filled ?? 0) > 0).length
  );
});

const heldPairs = computed(() => new Set((bot.value.openTrades ?? []).map((t) => t.pair)));
const coins = computed(() =>
  (bot.value.whitelist ?? [])
    .filter((p) => !heldPairs.value.has(p))
    .map((p) => ({ label: p.split('/')[0] ?? p, value: p, description: p })),
);

const pair = ref<string | undefined>(undefined);
const amount = ref<number | undefined>(50);
/** 'ai' = omit leverage and let Sentinel pick 1–3× (only while AI leverage is on). */
const leverage = ref<'ai' | 1 | 2 | 3>(1);
const leverageOptions = computed(() =>
  aiLeverage.value ? (['ai', 1, 2, 3] as const) : ([1, 2, 3] as const),
);
const busy = ref(false);
const problem = ref<string | null>(null);

watch(open, (o) => {
  if (!o) return;
  pair.value = props.trade?.pair ?? coins.value[0]?.value;
  amount.value = 50;
  leverage.value = aiLeverage.value ? 'ai' : 1;
  problem.value = null;
  loadSettings().catch(() => undefined);
});
/** The setting can arrive (or change) after the dialog opened: never keep "Sentinel decides" while it is off. */
watch(aiLeverage, (onNow, before) => {
  if (!onNow && leverage.value === 'ai') leverage.value = 1;
  else if (onNow && !before && leverage.value === 1) leverage.value = 'ai';
});
watch([pair, amount, leverage], () => (problem.value = null));

const coin = computed(() => (pair.value ?? '').split('/')[0] ?? '');
/** Known leverage (null while the AI decides). */
const lev = computed<number | null>(() =>
  adding.value
    ? (props.trade?.leverage ?? 1)
    : !futures.value
      ? 1
      : leverage.value === 'ai'
        ? null
        : leverage.value,
);
const free = computed(
  () => bot.value.balance?.currencies?.find((c) => c.currency === props.currency)?.free ?? null,
);
const MIN = 10;
const amountProblem = computed(() => {
  const a = amount.value;
  if (!a || a <= 0) return tr('buy.amount.empty');
  if (a < MIN) return tr('buy.amount.min', { min: MIN, currency: props.currency });
  if (free.value !== null && a > free.value)
    return tr('buy.amount.tooMuch', { money: novaMoney(free.value, props.currency, 2) });
  return null;
});
const blocked = computed(() => {
  if (adding.value && entries.value >= NOVA_MAX_BUYS)
    return tr('buy.blocked', { count: entries.value, max: NOVA_MAX_BUYS });
  return null;
});
const canBuy = computed(() => !!pair.value && !amountProblem.value && !blocked.value);

const price = computed(() => props.trade?.current_rate ?? null);
const averagingDown = computed(
  () => adding.value && price.value !== null && price.value < (props.trade?.open_rate ?? 0),
);
const newAverage = computed(() => {
  const t = props.trade;
  const p = price.value;
  const a = amount.value;
  if (!t || !p || !a) return null;
  const qty = (a * (lev.value ?? 1)) / p;
  return (t.amount * t.open_rate + qty * p) / (t.amount + qty);
});

const summary = computed(() => {
  const a = novaMoney(amount.value ?? 0, props.currency, 2);
  if (adding.value) {
    const l = lev.value ?? 1;
    const qty = price.value && amount.value ? (amount.value * l) / price.value : null;
    const vars = {
      coin: coin.value,
      amount: a,
      lev: l,
      nr: entries.value + 1,
      max: NOVA_MAX_BUYS,
    };
    const main = qty
      ? tr('buy.summary.addQty', {
          ...vars,
          qty: novaNum(qty, 4),
          price: novaPriceText(price.value),
        })
      : tr('buy.summary.add', vars);
    const avg = newAverage.value
      ? tr('buy.summary.average', {
          from: novaPriceText(props.trade?.open_rate),
          to: novaPriceText(newAverage.value),
        })
      : '';
    return avg ? `${main} ${avg}` : main;
  }
  const name = coin.value || tr('buy.summary.theCoin');
  const levText = !futures.value
    ? ''
    : lev.value === null
      ? tr('buy.summary.levAi')
      : lev.value > 1
        ? tr('buy.summary.levUses', {
            lev: lev.value,
            money: novaMoney((amount.value ?? 0) * lev.value, props.currency, 2),
          })
        : tr('buy.summary.levNone');
  return [tr('buy.summary.newCheck', { name, amount: a }), levText, tr('buy.summary.newAfter')]
    .filter(Boolean)
    .join(' ');
});

const leverageHelp = computed(() => {
  if (aiLeverage.value)
    return simple.value ? tr('buy.leverageHelp.aiSimple') : tr('buy.leverageHelp.aiPro');
  if (aiLocked.value)
    return simple.value ? tr('buy.leverageHelp.lockedSimple') : tr('buy.leverageHelp.lockedPro');
  return simple.value ? tr('buy.leverageHelp.offSimple') : tr('buy.leverageHelp.offPro');
});

const title = computed(() =>
  adding.value
    ? simple.value
      ? tr('buy.title.addSimple', { coin: coin.value })
      : tr('buy.title.addPro', { coin: coin.value })
    : simple.value
      ? tr('buy.title.newSimple')
      : tr('buy.title.newPro'),
);

async function buy() {
  if (!canBuy.value || !pair.value || !amount.value) return;
  busy.value = true;
  problem.value = null;
  try {
    const res = await controlBuy({
      pair: pair.value,
      stake_amount: amount.value,
      ...(!adding.value && futures.value && lev.value !== null ? { leverage: lev.value } : {}),
      ordertype: 'market',
    });
    const c = res.pair.split('/')[0];
    const money = novaMoney(res.stake_amount, props.currency, 2);
    const done = res.added_to_existing
      ? tr('buy.toast.addedMore', { coin: c, money, nr: res.entries, max: NOVA_MAX_BUYS })
      : res.news_checked
        ? tr('buy.toast.boughtChecked', { coin: c, money, lev: res.leverage })
        : tr('buy.toast.bought', { coin: c, money, lev: res.leverage });
    showAlert(res.order_open ? `${done} ${tr('buy.toast.waiting')}` : done, 'success');
    open.value = false;
  } catch (e) {
    problem.value = controlErrorText(e);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <UModal v-model:open="open" :title="title" :ui="{ content: 'max-w-lg rounded-2xl' }">
    <template #body>
      <div class="flex flex-col gap-4 text-left" data-testid="nova-buy-dialog">
        <UAlert
          v-if="blocked"
          color="warning"
          variant="subtle"
          icon="i-mdi-lock-outline"
          :title="blocked"
        />

        <UFormField
          v-if="!adding"
          :label="simple ? tr('buy.form.coinSimple') : tr('buy.form.coinPro')"
          :help="
            heldPairs.size
              ? simple
                ? tr('buy.form.heldSimple')
                : tr('buy.form.heldPro')
              : undefined
          "
        >
          <USelectMenu
            v-model="pair"
            :items="coins"
            value-key="value"
            :search-input="{ placeholder: tr('buy.form.search') }"
            class="w-full"
          />
        </UFormField>

        <UFormField
          :label="simple ? tr('buy.form.amountSimple') : tr('buy.form.amountPro', { currency })"
          :help="
            free !== null ? tr('buy.form.free', { money: novaMoney(free, currency, 2) }) : undefined
          "
          :error="amount !== undefined && amountProblem ? amountProblem : false"
        >
          <div class="flex flex-col gap-2">
            <UInputNumber
              v-model="amount"
              :min="0"
              :step="10"
              :step-snapping="false"
              size="lg"
              class="w-full"
              :format-options="{ maximumFractionDigits: 2 }"
            />
            <div class="flex flex-wrap gap-2">
              <UButton
                v-for="q in [25, 50, 100, 250]"
                :key="q"
                size="sm"
                color="neutral"
                :variant="amount === q ? 'soft' : 'outline'"
                class="nova-num max-sm:min-h-10"
                @click="amount = q"
                >{{ q }} {{ currency }}</UButton
              >
            </div>
          </div>
        </UFormField>

        <UFormField
          v-if="futures && !adding"
          :label="simple ? tr('buy.form.leverageSimple') : tr('buy.form.leveragePro')"
          :help="leverageHelp"
        >
          <div class="nova-seg text-sm" role="group" :aria-label="tr('buy.form.leveragePro')">
            <button
              v-for="l in leverageOptions"
              :key="l"
              type="button"
              class="nova-num max-sm:min-h-10"
              :aria-pressed="leverage === l"
              @click="leverage = l"
            >
              {{
                l === 'ai'
                  ? tr('buy.form.levAi')
                  : simple && l === 1
                    ? tr('buy.form.levNone')
                    : `${l}×`
              }}
            </button>
          </div>
        </UFormField>

        <UAlert
          v-if="averagingDown"
          color="warning"
          variant="subtle"
          icon="i-mdi-alert-outline"
          :title="simple ? tr('buy.averaging.titleSimple') : tr('buy.averaging.titlePro')"
          :description="simple ? tr('buy.averaging.textSimple') : tr('buy.averaging.textPro')"
        />

        <UAlert
          v-if="problem"
          color="error"
          variant="subtle"
          icon="i-mdi-alert-circle-outline"
          :title="simple ? tr('buy.problem.simple') : tr('buy.problem.pro')"
          :description="problem"
        />

        <div class="nova-tile flex flex-col gap-2 p-4">
          <p class="nova-money text-sm text-pretty text-default">{{ summary }}</p>
          <p v-if="dryRun" class="flex items-center gap-2 text-sm text-muted">
            <UIcon name="i-mdi-school-outline" class="size-4 shrink-0 text-secondary" />
            {{ tr('buy.practice') }}
          </p>
          <p v-else class="flex items-center gap-2 text-sm font-semibold text-rose-400">
            <UIcon name="i-mdi-cash-multiple" class="size-4 shrink-0" />
            {{ tr('buy.real') }}
          </p>
        </div>
      </div>
    </template>
    <template #footer>
      <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <UButton
          color="neutral"
          variant="outline"
          class="justify-center max-sm:min-h-10"
          autofocus
          @click="open = false"
          >{{ tr('common.cancel') }}</UButton
        >
        <UButton
          :color="dryRun ? 'primary' : 'error'"
          variant="solid"
          icon="i-mdi-cart-plus"
          class="justify-center font-semibold max-sm:min-h-10"
          :disabled="!canBuy"
          :loading="busy"
          @click="buy"
          >{{
            tr('buy.button', {
              coin: coin || tr('buy.coinFallback'),
              money: novaMoney(amount ?? 0, currency, 2),
            })
          }}</UButton
        >
      </div>
    </template>
  </UModal>
</template>
