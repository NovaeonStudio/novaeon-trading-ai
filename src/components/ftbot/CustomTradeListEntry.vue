<script setup lang="ts">
import type { Trade } from '@/types';
import TradeProfit from './TradeProfit.vue';

withDefaults(
  defineProps<{
    trade: Trade;
    stakeCurrencyDecimals: number;
    showDetails?: boolean;
  }>(),
  {
    showDetails: false,
  },
);
const { t } = useI18n();
const classLabel = 'w-6/12 text-muted text-sm';
</script>

<template>
  <div class="flex items-center">
    <div class="px-1 flex w-7/12 flex-col text-start justify-between">
      <span>
        <span class="me-1 font-semibold">{{ trade.pair }}</span>
        <small class="text-muted">(#{{ trade.trade_id }})</small>
      </span>
      <ValuePair :description="t('tradeList.entry.amount')" :class-label="classLabel">
        {{ trade.amount }}
      </ValuePair>
      <ValuePair :description="t('tradeList.entry.openRate')" :class-label="classLabel">
        {{ formatPrice(trade.open_rate) }}
      </ValuePair>
      <ValuePair
        v-if="trade.is_open && trade.current_rate"
        :description="t('tradeList.entry.currentRate')"
        :class-label="classLabel"
      >
        {{ formatPrice(trade.current_rate) }}
      </ValuePair>
      <ValuePair :description="t('tradeList.entry.openDate')" :class-label="classLabel">
        <DateTimeTZ :date="trade.open_timestamp" :date-only="true" />
      </ValuePair>
      <ValuePair
        v-if="trade.close_timestamp"
        :description="t('tradeList.entry.closeDate')"
        :class-label="classLabel"
      >
        <DateTimeTZ :date="trade.close_timestamp" :date-only="true" />
      </ValuePair>
    </div>
    <TradeProfit class="w-5/12" :trade="trade" />
  </div>
</template>
