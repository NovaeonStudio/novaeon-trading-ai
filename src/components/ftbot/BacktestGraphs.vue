<script setup lang="ts">
import type { ClosedTrade } from '@/types';
import TradeDurationChart from '../charts/TradeDurationChart.vue';

defineProps<{
  trades: ClosedTrade[];
}>();

const { t } = useI18n();
const botStore = useBotStore();

const { state: marketChangeData } = useAsyncState(
  () => botStore.activeBot.getBacktestMarketChange(),
  null,
);

const { state: walletData } = useAsyncState(
  () => botStore.activeBot.getBacktestWalletChange(),
  null,
);
</script>
<template>
  <!-- Each chart sits in a card with a fixed plot height: ECharts needs a definite height to draw. -->
  <div class="grid grid-cols-1 gap-4 py-4 xl:grid-cols-2">
    <NovaPanel
      :title="t('backtest.graphs.tradesLog')"
      :subtitle="t('backtest.graphs.tradesLogHint')"
    >
      <div class="h-72 sm:h-80">
        <TradesLogChart :trades="trades" :show-title="false" />
      </div>
    </NovaPanel>
    <NovaPanel
      :title="t('backtest.graphs.cumProfit')"
      :subtitle="t('backtest.graphs.cumProfitHint')"
    >
      <div class="h-72 sm:h-80">
        <CumProfitChart :trades="trades" :show-title="false" />
      </div>
    </NovaPanel>
    <NovaPanel
      :title="t('backtest.graphs.profitDistribution')"
      :subtitle="t('backtest.graphs.profitDistributionHint')"
    >
      <div class="h-72 sm:h-80">
        <ProfitDistributionChart :trades="trades" :show-title="false" />
      </div>
    </NovaPanel>
    <NovaPanel
      :title="t('backtest.graphs.tradeDurations')"
      :subtitle="t('backtest.graphs.tradeDurationsHint')"
    >
      <div class="h-72 sm:h-80">
        <TradeDurationChart :trades="trades" :show-title="false" />
      </div>
    </NovaPanel>
    <NovaPanel
      v-if="walletData"
      :title="t('backtest.graphs.wallet')"
      :subtitle="t('backtest.graphs.walletHint')"
    >
      <div class="h-72 sm:h-80">
        <WalletHistoryChart :wallet-data="walletData" :show-title="false" />
      </div>
    </NovaPanel>
    <NovaPanel
      v-if="marketChangeData?.data?.length"
      :title="t('backtest.graphs.marketChange')"
      :subtitle="t('backtest.graphs.marketChangeHint')"
    >
      <div class="h-72 sm:h-80">
        <MarketChangeChart :market-change-data="marketChangeData" :show-title="false" />
      </div>
    </NovaPanel>
  </div>
</template>
