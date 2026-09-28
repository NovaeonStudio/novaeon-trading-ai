<script setup lang="ts">
import type { Trade, BotFeatures } from '@/types';

withDefaults(
  defineProps<{
    botFeatures: BotFeatures;
    trade: Trade;
    enableForceEntry?: boolean;
  }>(),
  {
    enableForceEntry: false,
  },
);
const { t } = useI18n();
defineEmits<{
  forceExit: [trade: Trade, type?: 'limit' | 'market'];
  forceExitPartial: [trade: Trade];
  cancelOpenOrder: [trade: Trade];
  reloadTrade: [trade: Trade];
  deleteTrade: [trade: Trade];
  forceEntry: [trade: Trade];
}>();
</script>

<template>
  <div class="flex flex-col gap-1">
    <UButton
      v-if="!botFeatures.forceExitParams"
      class="justify-start!"
      color="neutral"
      :title="t('tradeList.actions.forceExit')"
      :label="t('tradeList.actions.forceExit')"
      icon="mdi:close-box"
      @click="$emit('forceExit', trade)"
    />
    <UButton
      v-if="botFeatures.forceExitParams"
      class="justify-start!"
      color="neutral"
      :title="t('tradeList.actions.forceExitLimit')"
      :label="t('tradeList.actions.forceExitLimit')"
      icon="mdi:close-box"
      @click="$emit('forceExit', trade, 'limit')"
    />
    <UButton
      v-if="botFeatures.forceExitParams"
      class="justify-start!"
      color="neutral"
      :title="t('tradeList.actions.forceExitMarket')"
      :label="t('tradeList.actions.forceExitMarket')"
      icon="mdi:close-box"
      @click="$emit('forceExit', trade, 'market')"
    />
    <UButton
      v-if="botFeatures.forceEntryTag"
      class="justify-start!"
      color="neutral"
      :title="t('tradeList.actions.forceExitPartial')"
      :label="t('tradeList.actions.forceExitPartial')"
      icon="mdi:close-box-multiple"
      @click="$emit('forceExitPartial', trade)"
    />
    <UButton
      v-if="botFeatures.cancelOpenOrders && (trade.open_order_id || trade.has_open_orders)"
      class="justify-start!"
      color="neutral"
      :title="t('tradeList.actions.cancelOpenOrders')"
      :label="t('tradeList.actions.cancelOpenOrders')"
      icon="mdi:cancel"
      @click="$emit('cancelOpenOrder', trade)"
    />
    <UButton
      v-if="enableForceEntry"
      class="justify-start!"
      color="neutral"
      :title="t('tradeList.actions.increasePosition')"
      :label="t('tradeList.actions.increasePosition')"
      icon="mdi:plus-box-multiple-outline"
      @click="$emit('forceEntry', trade)"
    />
    <UButton
      v-if="botFeatures.reloadTrade"
      class="justify-start!"
      color="neutral"
      :title="t('common.reload')"
      :label="t('common.reload')"
      icon="mdi:reload-alert"
      @click="$emit('reloadTrade', trade)"
    />
    <UButton
      class="justify-start!"
      color="neutral"
      :title="t('tradeList.actions.deleteTrade')"
      :label="t('tradeList.actions.deleteTrade')"
      icon="mdi:delete"
      @click="$emit('deleteTrade', trade)"
    />
  </div>
</template>
