<script setup lang="ts">
import type { Trade } from '@/types';
defineProps<{ tradeId: Trade['trade_id'] }>();
const { t } = useI18n();
defineEmits<{
  close: [value: boolean];
}>();
</script>

<template>
  <UModal :title="t('tradeList.customData.title', { id: String(tradeId) })" description="">
    <template #body>
      <TradeCustomData :trade-id="tradeId" />
    </template>
  </UModal>
</template>
