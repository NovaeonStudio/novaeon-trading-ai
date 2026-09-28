<script setup lang="ts">
import { MarginMode, TradingMode } from '@/types';
import type { ExchangeSelection, Markets, MarketsPayload, PairHistoryPayload } from '@/types';

const { t } = useI18n();
const botStore = useBotStore();
const chartStore = useChartConfigStore();

const finalTimeframe = computed<string>(() => {
  return botStore.activeBot.isWebserverMode
    ? chartStore.selectedTimeframe || botStore.activeBot.strategy?.timeframe || ''
    : botStore.activeBot.timeframe;
});

const availablePairs = computed<string[]>(() => {
  if (botStore.activeBot.isWebserverMode) {
    if (chartStore.useLiveData) {
      return Object.keys(markets.value?.markets || {}).sort() || [];
    }
    if (finalTimeframe.value && finalTimeframe.value !== '') {
      const tf = finalTimeframe.value;
      return botStore.activeBot.pairlistWithTimeframe
        .filter(([_, timeframe]) => {
          // console.log(pair, timeframe, tf);
          return timeframe === tf;
        })
        .map(([pair]) => pair);
    }
    return botStore.activeBot.pairlist;
  }
  return botStore.activeBot.whitelist;
});

onMounted(() => {
  if (botStore.activeBot.isWebserverMode) {
    // Get available pairs for all timeframes
    botStore.activeBot.getAvailablePairs({});
  } else if (!botStore.activeBot.whitelist || botStore.activeBot.whitelist.length === 0) {
    botStore.activeBot.getWhitelist();
  }
});

function refreshOHLCV(pair: string, columns: string[]) {
  console.log('Refreshing OHLCV for pair:', pair, finalTimeframe.value, 'with columns:', columns);
  if (botStore.activeBot.isWebserverMode && finalTimeframe.value) {
    const payload: PairHistoryPayload = {
      pair: pair,
      timeframe: finalTimeframe.value,
      timerange: chartStore.timerange,
      strategy: chartStore.strategy,
      // freqaimodel: freqaiModel.value,
      columns: columns,
      live_mode: chartStore.useLiveData,
    };
    if (exchange.value.customExchange) {
      payload.exchange = exchange.value.selectedExchange.exchange;
      payload.trading_mode = exchange.value.selectedExchange.trade_mode.trading_mode;
      payload.margin_mode = exchange.value.selectedExchange.trade_mode.margin_mode;
    }
    botStore.activeBot.getPairHistory(payload);
  } else {
    botStore.activeBot.getPairCandles({
      pair: pair,
      timeframe: finalTimeframe.value,
      columns: columns,
    });
  }
}
const exchange = ref<{
  customExchange: boolean;
  selectedExchange: ExchangeSelection;
}>({
  customExchange: false,
  selectedExchange: {
    exchange: botStore.activeBot.botState.exchange,
    trade_mode: {
      margin_mode: MarginMode.NONE,
      trading_mode: TradingMode.SPOT,
    },
  },
});

const markets = ref<Markets | null>(null);
watch(
  () => chartStore.useLiveData,
  async () => {
    if (botStore.activeBot.isWebserverMode && chartStore.useLiveData) {
      const payload: MarketsPayload = {};
      if (exchange.value.customExchange) {
        payload.exchange = exchange.value.selectedExchange.exchange;
        payload.trading_mode = exchange.value.selectedExchange.trade_mode.trading_mode;
        payload.margin_mode = exchange.value.selectedExchange.trade_mode.margin_mode;
      }

      markets.value = await botStore.activeBot.getMarkets(payload);
    }
  },
  {
    immediate: true,
  },
);
</script>

<template>
  <div class="flex h-full flex-col gap-4">
    <!-- Chart data settings (webserver mode only) -->
    <section v-if="botStore.activeBot.isWebserverMode" class="nova-panel p-4 sm:p-6">
      <div class="mb-4 flex items-center gap-2">
        <h2 class="text-base font-semibold text-highlighted">{{ t('candle.view.title') }}</h2>
        <InfoBox :hint="t('candle.view.hint')" />
      </div>
      <div class="nova-tile mb-4 p-3 text-start">
        <UCollapsible v-model:open="exchange.customExchange">
          <div class="flex flex-wrap items-center gap-x-5 gap-y-2">
            <UCheckbox v-model="exchange.customExchange" :label="t('candle.view.customExchange')" />
            <span v-show="!exchange.customExchange" class="text-sm text-muted">
              {{ t('candle.view.currentExchange') }}
              <span class="text-default"
                >{{ botStore.activeBot.botState.exchange }}
                {{ botStore.activeBot.botState.trading_mode }}</span
              >
            </span>
          </div>
          <template #content>
            <ExchangeSelect v-model="exchange.selectedExchange" class="mt-3" />
          </template>
        </UCollapsible>
      </div>
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3 md:grid-cols-5">
        <div class="flex flex-col gap-2 text-start sm:col-span-2">
          <span class="nova-label">{{ t('candle.view.strategy') }}</span>
          <StrategySelect v-model="chartStore.strategy"></StrategySelect>
          <UCheckbox
            v-if="botStore.activeBot.botFeatures.chartLiveData"
            v-model="chartStore.useLiveData"
            :label="t('candle.view.useLiveData')"
            :title="t('candle.view.useLiveDataHint')"
          />
        </div>
        <div class="flex flex-col gap-2 text-start">
          <span class="nova-label">{{ t('candle.view.timeframe') }}</span>
          <TimeframeSelect v-model="chartStore.selectedTimeframe" />
        </div>
        <TimeRangeSelect
          v-model="chartStore.timerange"
          :can-use-time="botStore.activeBot.botFeatures.timerangeWithTime"
          class="sm:col-span-3 md:col-span-2"
        ></TimeRangeSelect>
      </div>
    </section>

    <div class="h-full min-h-0">
      <CandleChartContainer
        :available-pairs="availablePairs"
        :historic-view="botStore.activeBot.isWebserverMode"
        :timeframe="finalTimeframe"
        :trades="botStore.activeBot.allTrades"
        :timerange="botStore.activeBot.isWebserverMode ? chartStore.timerange : undefined"
        :strategy="botStore.activeBot.isWebserverMode ? chartStore.strategy : undefined"
        @refresh-data="refreshOHLCV"
      >
      </CandleChartContainer>
    </div>
  </div>
</template>
