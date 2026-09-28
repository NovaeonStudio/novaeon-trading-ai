<script setup lang="ts">
import type { ChartSliderPosition, PairHistory, Trade } from '@/types';

const props = withDefaults(
  defineProps<{
    trades?: Trade[];
    availablePairs: string[];
    timeframe: string;
    historicView?: boolean;
    /** Reload data on pair switch if in historic view */
    reloadDataOnSwitch?: boolean;
    strategy?: string;
    sliderPosition?: ChartSliderPosition;
  }>(),
  {
    trades: () => [],
    historicView: false,
    reloadDataOnSwitch: false,
    strategy: '',
    sliderPosition: undefined,
  },
);

const emit = defineEmits<{
  refreshData: [pair: string, columns: string[]];
}>();

const { t } = useI18n();
const settingsStore = useSettingsStore();
const botStore = useBotStore();
const plotStore = usePlotConfigStore();

const dataset = computed((): PairHistory | undefined => {
  const firstpair = botStore.activeBot.plotMultiPairs[0];
  if (props.historicView) {
    return botStore.activeBot.history[`${firstpair}__${props.timeframe}`]?.data;
  }
  return botStore.activeBot.candleData[`${firstpair}__${props.timeframe}`]?.data;
});

const datasetColumns = computed(() =>
  dataset.value ? (dataset.value.all_columns ?? dataset.value.columns) : [],
);

const strategyName = computed(() => props.strategy || dataset.value?.strategy || '');

const showPlotConfigModal = ref(false);
function showConfigurator() {
  showPlotConfigModal.value = !showPlotConfigModal.value;
}

const isSinglePairView = computed(() => botStore.activeBot.plotMultiPairs.length === 1);

watch(
  () => botStore.activeBot.selectedPair,
  () => {
    botStore.activeBot.plotMultiPairs = [botStore.activeBot.selectedPair];
  },
);

onMounted(() => {
  if (botStore.activeBot.selectedPair) {
    botStore.activeBot.plotMultiPairs = [botStore.activeBot.selectedPair];
  } else if (props.availablePairs.length > 0) {
    assignFirstPair();
  }
  plotStore.plotConfigChanged();
});

function refresh() {
  for (const pair of botStore.activeBot.plotMultiPairs) {
    emit('refreshData', pair, plotStore.usedColumns);
  }
}

function refreshIfNecessary(newValue: string[], oldValue: string[] | undefined) {
  for (const pair of newValue) {
    if (oldValue?.includes(pair)) {
      continue;
    }
    emit('refreshData', pair, plotStore.usedColumns);
  }
}

function assignFirstPair() {
  const [firstPair] = props.availablePairs;
  if (firstPair) {
    botStore.activeBot.plotMultiPairs = [firstPair];
  }
}

watch(
  () => props.availablePairs,
  () => {
    if (
      botStore.activeBot.plotMultiPairs.length === 0 ||
      botStore.activeBot.plotMultiPairs.some((p) => !props.availablePairs.includes(p))
    ) {
      assignFirstPair();
      refresh();
    }
  },
);

watch(
  () => botStore.activeBot.plotMultiPairs,
  (newValue, oldValue) => {
    if (newValue.length === 0) return;

    if (!props.historicView || props.reloadDataOnSwitch) {
      refreshIfNecessary(newValue, oldValue);
    }
  },
  {
    immediate: true,
  },
);

watch(
  () => settingsStore.multiPairSelection,
  () => {
    if (
      !settingsStore.multiPairSelection &&
      botStore.activeBot.plotMultiPairs.length > 1 &&
      botStore.activeBot.plotMultiPairs[0]
    ) {
      // Select only the first pair if switching to single pair mode
      botStore.activeBot.plotMultiPairs = [botStore.activeBot.plotMultiPairs[0]];
    }
  },
);

const singlePairSelection = computed({
  get() {
    return botStore.activeBot.plotMultiPairs[0] || '';
  },
  set(value: string) {
    botStore.activeBot.plotMultiPairs = [value];
  },
});
</script>

<template>
  <div class="flex h-full">
    <div class="flex h-full w-full min-w-0 flex-1 flex-col items-stretch gap-3">
      <!-- toolbar: what is plotted (left), how it is drawn (right); wraps on small screens -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <span
            v-if="strategyName || timeframe"
            class="truncate text-base font-semibold text-highlighted"
            >{{ [strategyName, timeframe].filter(Boolean).join(' · ') }}</span
          >
          <div class="flex w-full items-center gap-2 sm:w-auto">
            <BaseStringMultiSelectMenu
              v-if="settingsStore.multiPairSelection"
              v-model="botStore.activeBot.plotMultiPairs"
              class="w-full sm:w-72"
              :items="availablePairs"
              :placeholder="t('candle.container.selectPairs')"
              virtualize
              size="md"
            />
            <USelectMenu
              v-else
              v-model="singlePairSelection"
              class="w-full sm:w-72"
              :items="availablePairs"
              size="md"
              virtualize
              :aria-label="t('candle.container.pair')"
              @input="refresh"
            />
            <UButton
              :title="t('candle.container.refresh')"
              :aria-label="t('candle.container.refresh')"
              color="neutral"
              variant="soft"
              size="md"
              :disabled="botStore.activeBot.plotMultiPairs.length === 0"
              icon="mdi:refresh"
              class="shrink-0"
              @click="refresh"
            />
          </div>
          <UCheckbox
            v-model="settingsStore.multiPairSelection"
            :label="t('candle.container.multiPair')"
            class="ms-1"
          />
        </div>
        <div class="flex flex-wrap items-center gap-x-4 gap-y-3 sm:ms-auto">
          <UCheckbox
            v-model="settingsStore.showMarkArea"
            :label="t('candle.container.showAreas')"
          />
          <UCheckbox v-model="settingsStore.useHeikinAshiCandles" label="Heikin Ashi" />
          <div class="flex min-w-0 grow items-center gap-2 sm:grow-0">
            <PlotConfigSelect class="min-w-40 grow" />
            <UButton
              :title="t('candle.container.plotConfigurator')"
              :aria-label="t('candle.container.plotConfigurator')"
              color="neutral"
              variant="soft"
              size="md"
              icon="mdi:cog"
              class="shrink-0"
              @click="showConfigurator"
            />
          </div>
        </div>
      </div>
      <div
        v-if="botStore.activeBot.plotMultiPairs?.length > 0"
        class="min-h-0 flex-1"
        :class="{
          'h-full w-full min-w-0': isSinglePairView,
          'grid grid-cols-1 gap-4 lg:grid-cols-2': !isSinglePairView,
        }"
      >
        <SingleCandleChartContainer
          v-for="pair in botStore.activeBot.plotMultiPairs"
          :key="pair"
          :available-pairs="availablePairs"
          :pair="pair"
          :historic-view="botStore.activeBot.isWebserverMode"
          :timeframe="timeframe"
          :trades="props.trades"
          :slider-position="props.sliderPosition"
          :is-single-pair-view="isSinglePairView"
          @refresh-data="refresh()"
        >
        </SingleCandleChartContainer>
      </div>
      <div v-else class="flex h-full w-full flex-col items-center justify-center gap-3 py-16">
        <span class="flex size-10 items-center justify-center rounded-full bg-accented">
          <UIcon name="i-mdi-chart-box-outline" class="size-5 text-muted" />
        </span>
        <p class="text-sm text-balance text-muted">{{ t('candle.container.pickPair') }}</p>
      </div>
    </div>
    <DraggableModal
      v-model:open="showPlotConfigModal"
      :title="t('candle.container.plotConfigurator')"
      class="max-w-xl"
      :description="t('candle.container.configuratorDescription')"
      :overlay="false"
      :modal="false"
      :dismissible="false"
    >
      <template #body>
        <PlotConfigurator :is-visible="showPlotConfigModal" :columns="datasetColumns" />
      </template>
    </DraggableModal>
  </div>
</template>
