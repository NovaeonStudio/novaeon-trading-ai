<script setup lang="ts">
import type { ForceEnterPayload } from '@/types';
import { OrderSides } from '@/types';

export interface ForceEntryFormProps {
  pair?: string;
  positionIncrease?: boolean;
}

const props = withDefaults(defineProps<ForceEntryFormProps>(), {
  pair: '',
  positionIncrease: false,
});

const emit = defineEmits<{
  close: [value: boolean];
}>();

const { t } = useI18n();
const botStore = useBotStore();

const form = ref<HTMLFormElement>();
const selectedPair = ref('');
const price = ref<number | undefined>(undefined);
const stakeAmount = ref<number | undefined>(undefined);
const leverage = ref<number | undefined>(undefined);

const ordertype = ref('');
const orderSide = ref<OrderSides>(OrderSides.long);
const enterTag = ref('force_entry');

const availableStake = computed<number | undefined>(() => {
  const stakeBalance = botStore.activeBot.balance.currencies?.find(
    (curr) => curr.currency === botStore.activeBot.stakeCurrency,
  );
  if (!stakeBalance) {
    return undefined;
  }
  return botStore.activeBot.botFeatures.hasBotBalance
    ? (stakeBalance.bot_owned ?? stakeBalance.free)
    : stakeBalance.free;
});

const availableStakeText = computed<string | undefined>(() =>
  availableStake.value === undefined
    ? undefined
    : t('forceTrade.entry.available', {
        amount: formatPriceCurrency(
          availableStake.value,
          botStore.activeBot.stakeCurrency,
          botStore.activeBot.stakeCurrencyDecimals,
        ),
      }),
);

function roundToStakePrecision(value: number): number {
  return Number(value.toFixed(botStore.activeBot.stakeCurrencyDecimals));
}

/** Slider proxy - an empty stake-amount (use the bot's configured amount) equals 0 on the slider. */
const stakeAmountSlider = computed<number>({
  get: () => stakeAmount.value ?? 0,
  set: (value) => {
    stakeAmount.value = value === 0 ? undefined : value;
  },
});

const stakeStep = computed<number>(() => {
  const precision = 10 ** -botStore.activeBot.stakeCurrencyDecimals;
  return Math.max(roundToStakePrecision((availableStake.value ?? 0) / 100), precision);
});

const stakeRatios = [0.25, 0.5, 0.75, 1];

function applyStakeRatio(ratio: number) {
  if (!availableStake.value) {
    return;
  }
  stakeAmount.value = roundToStakePrecision(availableStake.value * ratio);
}

const orderTypeOptions = computed(() => [
  { value: 'market', text: t('forceTrade.market') },
  { value: 'limit', text: t('forceTrade.limit') },
]);
const orderSideOptions = computed(() => [
  { value: 'long', text: t('forceTrade.long') },
  { value: 'short', text: t('forceTrade.short') },
]);

function checkFormValidity() {
  const valid = form.value?.checkValidity();

  return valid;
}

async function handleEntry() {
  // Exit when the form isn't valid
  if (!checkFormValidity()) {
    return;
  }

  // call forceentry
  const payload: ForceEnterPayload = { pair: selectedPair.value };
  if (price.value) {
    payload.price = Number(price.value);
  }
  if (ordertype.value) {
    payload.ordertype = ordertype.value;
  }
  if (stakeAmount.value) {
    payload.stakeamount = stakeAmount.value;
  }
  if (botStore.activeBot.botFeatures.forceEnterShort && botStore.activeBot.shortAllowed) {
    payload.side = orderSide.value;
  }
  if (botStore.activeBot.botFeatures.forceEntryTag && enterTag.value) {
    payload.entry_tag = enterTag.value;
  }

  if (leverage.value) {
    payload.leverage = leverage.value;
  }
  botStore.activeBot.forceentry(payload);
  emit('close', true);
}

function resetForm() {
  selectedPair.value = props.pair;
  price.value = undefined;
  stakeAmount.value = undefined;
  ordertype.value =
    botStore.activeBot.botState?.order_types?.forcebuy ||
    botStore.activeBot.botState?.order_types?.force_entry ||
    botStore.activeBot.botState?.order_types?.buy ||
    botStore.activeBot.botState?.order_types?.entry ||
    'limit';
}

resetForm();
// Ensure the available balance is up to date when opening the dialog.
botStore.activeBot.getBalance();
</script>

<template>
  <UModal
    :title="
      positionIncrease ? t('forceTrade.entry.titleIncrease', { pair }) : t('forceTrade.entry.title')
    "
    :description="
      positionIncrease ? t('forceTrade.entry.descIncrease') : t('forceTrade.entry.desc')
    "
  >
    <template #body>
      <form ref="form" class="space-y-4" @submit.prevent="handleEntry">
        <UFormField
          v-if="botStore.activeBot.botFeatures.forceEnterShort && botStore.activeBot.shortAllowed"
          :label="t('forceTrade.entry.direction')"
        >
          <USegmentedControl
            v-model="orderSide"
            :items="orderSideOptions"
            label-key="text"
            value-key="value"
            size="sm"
            class="w-full"
          />
        </UFormField>

        <UFormField :label="t('forceTrade.entry.pair')" required>
          <UInput
            v-model="selectedPair"
            :disabled="positionIncrease"
            required
            class="w-full"
            @keydown.enter="handleEntry"
            @focus="($event.target as HTMLInputElement).select()"
          />
        </UFormField>

        <UFormField :label="t('forceTrade.entry.price')">
          <UInputNumber
            v-model="price"
            show-buttons
            :min="0"
            :stepSnapping="false"
            :format-options="{
              maximumFractionDigits: 8,
            }"
            :step="0.1"
            class="w-full"
            @keydown.enter="handleEntry"
          />
        </UFormField>

        <UFormField
          :label="t('forceTrade.entry.stakeAmount', { currency: botStore.activeBot.stakeCurrency })"
          :hint="availableStakeText"
        >
          <div class="space-y-2">
            <UInputNumber
              v-model="stakeAmount"
              show-buttons
              :min="0"
              :stepSnapping="false"
              :step="['USDC', 'USDT'].includes(botStore.activeBot.stakeCurrency) ? 10 : 1"
              class="w-full"
              :format-options="{
                maximumFractionDigits: 5,
              }"
            />
            <template v-if="availableStake">
              <USlider
                v-model="stakeAmountSlider"
                :min="0"
                :max="availableStake"
                :step="stakeStep"
                class="w-full"
              />
              <div class="flex gap-1">
                <UButton
                  v-for="ratio in stakeRatios"
                  :key="ratio"
                  size="xs"
                  color="neutral"
                  variant="soft"
                  class="grow justify-center"
                  @click="applyStakeRatio(ratio)"
                >
                  {{ formatPercent(ratio, 0) }}
                </UButton>
                <UButton
                  size="xs"
                  color="neutral"
                  variant="soft"
                  icon="mdi:close"
                  :title="t('forceTrade.entry.useDefaultStake')"
                  :disabled="stakeAmount === undefined"
                  @click="stakeAmount = undefined"
                />
              </div>
            </template>
          </div>
        </UFormField>

        <UFormField
          v-if="botStore.activeBot.botFeatures.forceEnterShort && botStore.activeBot.shortAllowed"
          :label="t('forceTrade.entry.leverage')"
        >
          <UInputNumber
            id="leverage-input"
            v-model="leverage"
            show-buttons
            :min="1"
            :step="1"
            :max-fraction-digits="1"
            class="w-full"
            @keydown.enter="handleEntry"
          />
        </UFormField>

        <UFormField :label="t('forceTrade.orderType')">
          <USegmentedControl
            v-model="ordertype"
            :items="orderTypeOptions"
            label-key="text"
            value-key="value"
            size="sm"
            class="w-full"
          />
        </UFormField>

        <UFormField
          v-if="botStore.activeBot.botFeatures.forceEntryTag"
          :label="t('forceTrade.entry.entryTag')"
        >
          <UInput id="enterTag-input" v-model="enterTag" class="w-full" />
        </UFormField>
      </form>
    </template>
    <template #footer>
      <div class="ms-auto flex justify-end gap-2">
        <UButton color="neutral" @click="$emit('close', false)" icon="mdi:close">
          {{ t('common.cancel') }}
        </UButton>
        <UButton @click="handleEntry" icon="mdi:check">
          {{ t('forceTrade.entry.submit') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>
