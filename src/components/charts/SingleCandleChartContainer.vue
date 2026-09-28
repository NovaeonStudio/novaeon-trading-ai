<script setup lang="ts">
import type { ChartSliderPosition, PairHistory, Trade } from '@/types';
import { LoadingStatus } from '@/types';
import { I18nT } from 'vue-i18n';

const props = withDefaults(
  defineProps<{
    trades?: Trade[];
    availablePairs: string[];
    timeframe: string;
    historicView?: boolean;
    pair?: string;
    sliderPosition?: ChartSliderPosition;
    isSinglePairView?: boolean;
  }>(),
  {
    trades: () => [],
    historicView: false,
    pair: '',
    sliderPosition: undefined,
    isSinglePairView: true,
  },
);

const emit = defineEmits<{
  refreshData: [pair: string, columns: string[]];
}>();

const { t } = useI18n();
const settingsStore = useSettingsStore();
const { mode: chartMode } = useNovaChartTheme();
const candleColors = useNovaCandleColors();
const botStore = useBotStore();
const plotStore = usePlotConfigStore();

const dataset = computed((): PairHistory | undefined => {
  if (props.historicView) {
    return botStore.activeBot.history[`${props.pair}__${props.timeframe}`]?.data;
  }
  return botStore.activeBot.candleData[`${props.pair}__${props.timeframe}`]?.data;
});

const datasetColumns = computed(() =>
  dataset.value ? (dataset.value.all_columns ?? dataset.value.columns) : [],
);
const datasetLoadedColumns = computed(() =>
  dataset.value ? (dataset.value.columns ?? dataset.value.all_columns) : [],
);

const hasDataset = computed(() => dataset.value && dataset.value.data.length > 0);
const isLoadingDataset = computed((): boolean => {
  if (props.historicView) {
    return botStore.activeBot.historyStatus === LoadingStatus.loading;
  }

  return botStore.activeBot.candleDataStatus === LoadingStatus.loading;
});
const noDatasetText = computed((): string => {
  const status = props.historicView
    ? botStore.activeBot.historyStatus
    : botStore.activeBot.candleDataStatus;

  switch (status) {
    case LoadingStatus.not_loaded:
      return t('candle.single.notLoaded');
    case LoadingStatus.loading:
      return t('candle.single.loadingCandles');
    case LoadingStatus.success:
      return t('candle.single.noData');
    case LoadingStatus.error:
      return t('candle.single.loadError');
    default:
      return t('candle.single.noDataYet');
  }
});

function refresh() {
  emit('refreshData', props.pair, plotStore.usedColumns);
}

function refreshIfNecessary() {
  if (!hasDataset.value) {
    refresh();
  }
}

function assignFirstPair() {
  const [firstPair] = props.availablePairs;
  if (firstPair) {
    //props.pair = firstPair;
  }
}

watch(
  () => props.availablePairs,
  () => {
    if (!props.availablePairs.find((p) => p === props.pair)) {
      assignFirstPair();
      refresh();
    }
  },
);

watch(
  () => plotStore.plotConfig,
  () => {
    // Trigger reload if the used columns are not loaded yet but would be available.
    const hasAllColumns = plotStore.usedColumns.some(
      (c) => datasetColumns.value.includes(c) && !datasetLoadedColumns.value.includes(c),
    );

    if (settingsStore.useReducedPairCalls && hasAllColumns) {
      refresh();
    }
  },
);

watch(
  () => props.timeframe,
  () => {
    refreshIfNecessary();
  },
);
</script>

<template>
  <div
    class="flex w-full min-w-0 flex-col items-stretch"
    :class="{
      'h-full': isSinglePairView,
      'nova-panel h-150 p-3 sm:p-4': !isSinglePairView,
    }"
  >
    <div class="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-2 pb-2">
      <div class="flex min-w-0 items-center gap-2">
        <span class="truncate text-sm font-semibold text-highlighted">{{
          pair || t('candle.container.pair')
        }}</span>
        <UIcon
          v-if="isLoadingDataset"
          name="i-mdi-loading"
          class="size-4 animate-spin text-muted"
          :aria-label="t('candle.single.loading')"
        />
      </div>
      <div
        v-if="dataset"
        class="nova-num flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted"
      >
        <I18nT
          keypath="candle.single.longEntries"
          tag="span"
          scope="global"
          :title="t('candle.single.longEntrySignals')"
        >
          <template #count>
            <span class="font-medium text-highlighted">{{
              dataset.enter_long_signals || dataset.buy_signals
            }}</span>
          </template>
        </I18nT>
        <I18nT
          keypath="candle.single.longExits"
          tag="span"
          scope="global"
          :title="t('candle.single.longExitSignals')"
        >
          <template #count>
            <span class="font-medium text-highlighted">{{
              dataset.exit_long_signals || dataset.sell_signals
            }}</span>
          </template>
        </I18nT>
        <I18nT
          v-if="dataset.enter_short_signals"
          keypath="candle.single.shortEntries"
          tag="span"
          scope="global"
        >
          <template #count>
            <span class="font-medium text-highlighted">{{ dataset.enter_short_signals }}</span>
          </template>
        </I18nT>
        <I18nT
          v-if="dataset.exit_short_signals"
          keypath="candle.single.shortExits"
          tag="span"
          scope="global"
        >
          <template #count>
            <span class="font-medium text-highlighted">{{ dataset.exit_short_signals }}</span>
          </template>
        </I18nT>
      </div>
    </div>
    <div class="flex h-full min-h-0">
      <div class="w-full min-w-0 flex-1">
        <CandleChart
          v-if="hasDataset && dataset"
          :dataset="dataset"
          :trades="trades"
          :plot-config="plotStore.plotConfig"
          :heikin-ashi="settingsStore.useHeikinAshiCandles"
          :show-mark-area="settingsStore.showMarkArea"
          :use-u-t-c="settingsStore.timezone === 'UTC'"
          :theme="chartMode"
          :slider-position="sliderPosition"
          :color-up="candleColors.up"
          :color-down="candleColors.down"
          :start-candle-count="settingsStore.chartDefaultCandleCount"
          :label-side="settingsStore.chartLabelSide"
        />
        <div v-else-if="isLoadingDataset" class="relative h-full min-h-64">
          <USkeleton class="h-full w-full rounded-xl" />
          <p
            v-if="botStore.activeBot.historyTakesLonger"
            class="absolute inset-x-0 bottom-4 text-center text-xs text-muted"
          >
            {{ t('candle.single.slow') }}
          </p>
        </div>
        <div
          v-else
          class="flex h-full min-h-64 flex-col items-center justify-center gap-3 text-center"
        >
          <span class="flex size-10 items-center justify-center rounded-full bg-accented">
            <UIcon name="i-mdi-chart-box-outline" class="size-5 text-muted" />
          </span>
          <p class="max-w-xs text-sm text-pretty text-muted">{{ noDatasetText }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
