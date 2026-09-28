<script setup lang="ts">
defineProps<{
  history?: boolean;
}>();
const { t } = useI18n();
const botStore = useBotStore();
</script>

<template>
  <div>
    <!-- <TradeList
      class="open-trades"
      :trades="openTrades"
      title="Open trades"
      :active-trades="true"
      empty-text="Currently no open trades."
    /> -->
    <CustomTradeList
      v-if="!history && !botStore.activeBot.detailTradeId"
      :trades="botStore.activeBot.openTrades"
      :title="t('tradeList.mobile.openTitle')"
      :active-trades="true"
      :stake-currency-decimals="botStore.activeBot.stakeCurrencyDecimals"
      :empty-text="t('tradeList.mobile.emptyOpen')"
    />
    <CustomTradeList
      v-if="history && !botStore.activeBot.detailTradeId"
      :trades="botStore.activeBot.closedTrades"
      :title="t('tradeList.mobile.historyTitle')"
      :stake-currency-decimals="botStore.activeBot.stakeCurrencyDecimals"
      :empty-text="t('tradeList.mobile.emptyClosed')"
    />
    <div
      v-if="botStore.activeBot.detailTradeId && botStore.activeBot.tradeDetail"
      class="flex flex-col"
    >
      <UButton
        color="neutral"
        class="self-start my-1 ms-1"
        @click="botStore.activeBot.setDetailTrade(null)"
        :label="t('common.back')"
        icon="mdi:arrow-left"
      />
      <TradeDetail
        :trade="botStore.activeBot.tradeDetail"
        :stake-currency="botStore.activeBot.stakeCurrency"
      />
    </div>
  </div>
</template>
