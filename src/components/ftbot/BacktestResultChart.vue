<script setup lang="ts">
import type { ChartSliderPosition, StrategyBacktestResult, Trade } from '@/types';

const props = defineProps<{
  timeframe: string;
  strategy: string;
  freqaiModel?: string;
  timerange: string;
  backtestResult: StrategyBacktestResult;
}>();
const botStore = useBotStore();
const isBarVisible = ref({ right: true, left: true });
const sliderPosition = ref<ChartSliderPosition>();

function navigateChartToTrade(trade: Trade) {
  sliderPosition.value = {
    startValue: trade.open_timestamp,
    endValue: trade.close_timestamp,
  };
}

function refreshOHLCV(pair: string, columns: string[]) {
  botStore.activeBot.getPairHistory({
    pair: pair,
    timeframe: props.timeframe,
    timerange: props.timerange,
    strategy: props.strategy,
    freqaimodel: props.freqaiModel,
    columns: columns,
    margin_mode: props.backtestResult.margin_mode,
    trading_mode: props.backtestResult.trading_mode,
  });
}
onMounted(() => {
  if (!botStore.activeBot.selectedPair && props.backtestResult.pairlist.length > 0) {
    const [firstPair] = props.backtestResult.pairlist;
    if (firstPair) {
      botStore.activeBot.selectedPair = firstPair;
    }
  }
});
</script>

<template>
  <div class="flex flex-col gap-4 py-4">
    <div class="flex flex-wrap items-center gap-3">
      <UButton
        :aria-label="
          isBarVisible.left ? $t('backtest.chart.hidePairs') : $t('backtest.chart.showPairs')
        "
        :title="isBarVisible.left ? $t('backtest.chart.hidePairs') : $t('backtest.chart.showPairs')"
        color="neutral"
        variant="soft"
        :icon="isBarVisible.left ? 'mdi:chevron-left' : 'mdi:chevron-right'"
        @click="isBarVisible.left = !isBarVisible.left"
      />
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-medium text-highlighted">
          {{ [strategy, timerange].filter(Boolean).join(' · ') }}
        </p>
        <p class="text-xs text-pretty text-muted">
          {{ $t('backtest.chart.hint') }}
        </p>
      </div>
      <UButton
        :aria-label="
          isBarVisible.right ? $t('backtest.chart.hideTrades') : $t('backtest.chart.showTrades')
        "
        :title="
          isBarVisible.right ? $t('backtest.chart.hideTrades') : $t('backtest.chart.showTrades')
        "
        color="neutral"
        variant="soft"
        :icon="isBarVisible.right ? 'mdi:chevron-right' : 'mdi:chevron-left'"
        @click="isBarVisible.right = !isBarVisible.right"
      />
    </div>
    <div class="flex h-full flex-row items-stretch gap-4 overflow-x-clip text-center">
      <Transition name="fadeleft">
        <PairSummary
          v-if="isBarVisible.left"
          class="overflow-y-auto overflow-x-hidden"
          style="max-height: calc(100vh - 200px)"
          :pairlist="backtestResult.pairlist"
          :trades="backtestResult.trades"
          :starting-balance="backtestResult.starting_balance"
          sort-method="profit"
          :backtest-mode="true"
        />
      </Transition>
      <CandleChartContainer
        :available-pairs="backtestResult.pairlist"
        historic-view
        reload-data-on-switch
        :timeframe="timeframe"
        :timerange="timerange"
        :strategy="strategy"
        :trades="backtestResult.trades"
        class="nova-panel candle-chart-container h-full min-w-0 flex-1 self-stretch overflow-y-auto p-3 sm:p-4"
        :slider-position="sliderPosition"
        :freqai-model="freqaiModel"
        @refresh-data="refreshOHLCV"
      >
      </CandleChartContainer>
      <Transition name="fade">
        <TradeListNav
          v-if="isBarVisible.right"
          class="overflow-y-auto overflow-x-visible min-w-56"
          style="max-height: calc(100vh - 200px)"
          :trades="backtestResult.trades.filter((t) => t.pair === botStore.activeBot.selectedPair)"
          @trade-select="navigateChartToTrade"
        />
      </Transition>
    </div>
    <DraggableContainer :header="$t('backtest.analysis.singleTrades')" class="w-full">
      <TradeList class="trade-history w-full" :trades="backtestResult.trades" :show-filter="true" />
    </DraggableContainer>
  </div>
</template>

<style lang="css" scoped>
.candle-chart-container {
  /* TODO: Rough estimate - still to fix correctly
   Applies to all "calc" usages in this file. */
  height: calc(100vh - 250px) !important;
}

.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 300ms cubic-bezier(0.32, 0.72, 0, 1),
    transform 300ms cubic-bezier(0.32, 0.72, 0, 1);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateX(30px);
}
.fadeleft-enter-active,
.fadeleft-leave-active {
  transition:
    opacity 300ms cubic-bezier(0.32, 0.72, 0, 1),
    transform 300ms cubic-bezier(0.32, 0.72, 0, 1);
}

.fadeleft-enter-from,
.fadeleft-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}
</style>
