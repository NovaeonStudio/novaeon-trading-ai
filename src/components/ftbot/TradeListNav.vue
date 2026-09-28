<script setup lang="ts">
import type { Trade } from '@/types';

const props = withDefaults(
  defineProps<{
    trades: Trade[];
    backtestMode?: boolean;
  }>(),
  {
    backtestMode: false,
  },
);
const emit = defineEmits<{ 'trade-select': [trade: Trade] }>();

const { t } = useI18n();
const botStore = useBotStore();
const selectedTrade = ref({} as Trade);
const sortDescendingOrder = ref(true);
const sortMethod = ref('openDate');
const sortMethodOptions = computed(() => [
  { text: t('tradeList.nav.openDate'), value: 'openDate' },
  { text: t('tradeList.nav.profit'), value: 'profit' },
]);

const onTradeSelect = (trade: Trade) => {
  selectedTrade.value = trade;
  emit('trade-select', trade);
};

const sortedTrades = computed(() => {
  const field: keyof Trade = sortMethod.value === 'profit' ? 'profit_ratio' : 'open_timestamp';
  return sortDescendingOrder.value
    ? props.trades.slice().sort((a, b) => (b[field] ?? 0) - (a[field] ?? 0))
    : props.trades.slice().sort((a, b) => (a[field] ?? 0) - (b[field] ?? 0));
});

const ordersVisible = ref(sortedTrades.value.map(() => false));

watch(
  () => botStore.activeBot.selectedPair,
  () => {
    ordersVisible.value = sortedTrades.value.map(() => false);
  },
);
</script>

<template>
  <div>
    <div class="flex justify-center">
      <span class="me-2">{{ t('tradeList.nav.sortBy') }}</span>
      <URadioGroup
        v-model="sortMethod"
        :items="sortMethodOptions.map((o) => ({ label: o.text, value: o.value }))"
        orientation="horizontal"
      />
    </div>
    <ul
      class="divide-y divide-default/50 divide-solid border-x border-y rounded-xl border-default/70"
    >
      <UButton
        color="neutral"
        variant="ghost"
        class="w-full justify-center"
        :title="t('tradeList.nav.title')"
        @click="sortDescendingOrder = !sortDescendingOrder"
        :trailing-icon="sortDescendingOrder ? 'mdi:arrow-down' : 'mdi:arrow-up'"
        >{{ t('tradeList.nav.title') }}
      </UButton>
      <li
        v-for="(trade, i) in sortedTrades"
        :key="trade.open_timestamp"
        class="flex flex-col py-1 px-1 items-stretch"
        :title="`${trade.pair}`"
        :class="{
          'bg-brand-400/10 text-highlighted': trade.open_timestamp === selectedTrade.open_timestamp,
        }"
        @click="onTradeSelect(trade)"
      >
        <div class="flex">
          <div class="flex flex-col">
            <div>
              <span v-if="botStore.activeBot.botState.trading_mode !== 'spot'">{{
                trade.is_short ? 'S-' : 'L-'
              }}</span>
              <DateTimeTZ :date="trade.open_timestamp" />
            </div>
            <TradeProfit :trade="trade" class="my-1" />
            <ProfitPill
              v-if="backtestMode"
              :profit-ratio="trade.profit_ratio"
              :stake-currency="botStore.activeBot.stakeCurrency"
            />
          </div>
          <UButton
            class="ms-auto mt-auto"
            variant="outline"
            color="neutral"
            @click="ordersVisible[i] = !ordersVisible[i]"
            :icon="ordersVisible[i] ? 'mdi:chevron-down' : 'mdi:chevron-right'"
          />
        </div>
        <Transition>
          <div v-if="ordersVisible[i]">
            <ul class="px-3 m-0 list-disc list-inside text-start">
              <li
                v-for="order in trade.orders?.filter((o) => o.order_filled_timestamp !== null)"
                :key="order.order_timestamp"
              >
                {{
                  t('tradeList.nav.orderLine', {
                    side: order.ft_order_side,
                    amount: String(order.amount ?? ''),
                    price: String(order.safe_price ?? ''),
                  })
                }}
              </li>
            </ul>
          </div>
        </Transition>
      </li>
      <div v-if="trades.length === 0">{{ t('tradeList.nav.empty') }}</div>
    </ul>
  </div>
</template>

<style scoped>
.list-group {
  text-align: left;
}
</style>
