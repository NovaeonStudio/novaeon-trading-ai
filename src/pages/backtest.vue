<script setup lang="ts">
enum BtRunModes {
  run = 'run',
  results = 'results',
  visualize = 'visualize',
  visualizesummary = 'visualize-summary',
  compareresults = 'compare-results',
  historicresults = 'historicResults',
}

const { t } = useI18n();
const botStore = useBotStore();
const btStore = useBtStore();

const hasBacktestResult = computed(() =>
  botStore.activeBot.backtestHistory
    ? Object.keys(botStore.activeBot.backtestHistory).length !== 0
    : false,
);
const hasMultiBacktestResult = computed(() =>
  botStore.activeBot.backtestHistory
    ? Object.keys(botStore.activeBot.backtestHistory).length > 1
    : false,
);

const timeframe = computed((): string => {
  return botStore.activeBot.selectedBacktestResult?.timeframe ?? '';
});

const showLeftBar = ref(false);

const btFormMode = ref<BtRunModes>(BtRunModes.run);
const pollInterval = ref<number | null>(null);

function selectBacktestResult() {
  if (!botStore.activeBot.selectedBacktestResult) {
    return;
  }
  // Set parameters for this result
  btStore.strategy = botStore.activeBot.selectedBacktestResult.strategy_name;
  botStore.activeBot.getStrategy(btStore.strategy);
  btStore.selectedTimeframe = botStore.activeBot.selectedBacktestResult.timeframe;
  btStore.selectedDetailTimeframe =
    botStore.activeBot.selectedBacktestResult.timeframe_detail || '';
  // TODO: maybe this should not use timerange, but the actual backtest start/end results instead?
  btStore.timerange = botStore.activeBot.selectedBacktestResult.timerange;
  btStore.enableProtections = botStore.activeBot.selectedBacktestResult.enable_protections;
  btStore.freqAI.enabled = !!botStore.activeBot.selectedBacktestResult.freqaimodel;
  btStore.freqAI.model = botStore.activeBot.selectedBacktestResult.freqaimodel || '';
  btStore.freqAI.identifier = botStore.activeBot.selectedBacktestResult.freqai_identifier || '';
}

watch(
  () => botStore.activeBot.selectedBacktestResultKey,
  () => {
    selectBacktestResult();
  },
);

onMounted(() => botStore.activeBot.getState());
watch(
  () => botStore.activeBot.backtestRunning,
  () => {
    if (botStore.activeBot.backtestRunning === true) {
      pollInterval.value = window.setInterval(botStore.activeBot.pollBacktest, 1000);
    } else if (pollInterval.value) {
      clearInterval(pollInterval.value);
      pollInterval.value = null;
    }
  },
);

const backtestTabs = computed(() => {
  const tabs: { slot: string; value: string; label: string; icon: string; disabled?: boolean }[] =
    [];
  if (botStore.activeBot.botFeatures.backtestHistory) {
    tabs.push({
      slot: 'historic-results',
      value: BtRunModes.historicresults,
      label: t('backtest.tabs.loadResults'),
      icon: 'i-mdi-cloud-download',
      disabled: !botStore.activeBot.canRunBacktest,
    });
  }
  tabs.push({
    slot: 'run',
    value: BtRunModes.run,
    label: t('backtest.tabs.run'),
    icon: 'i-mdi-run-fast',
    disabled: !botStore.activeBot.canRunBacktest,
  });
  tabs.push({
    slot: 'results',
    value: BtRunModes.results,
    label: t('backtest.tabs.analyze'),
    icon: 'i-mdi-table-eye',
    disabled: !hasBacktestResult.value,
  });
  if (hasMultiBacktestResult.value) {
    tabs.push({
      slot: 'compare-results',
      value: BtRunModes.compareresults,
      label: t('backtest.tabs.compare'),
      icon: 'i-mdi-compare-horizontal',
      disabled: !hasMultiBacktestResult.value,
    });
  }
  tabs.push({
    slot: 'visualize-summary',
    value: BtRunModes.visualizesummary,
    label: t('backtest.tabs.visualizeSummary'),
    icon: 'i-mdi-chart-bell-curve-cumulative',
    disabled: !hasBacktestResult.value,
  });
  tabs.push({
    slot: 'visualize',
    value: BtRunModes.visualize,
    label: t('backtest.tabs.visualizeResult'),
    icon: 'i-mdi-chart-timeline-variant-shimmer',
    disabled: !hasBacktestResult.value,
  });
  return tabs;
});
</script>

<template>
  <div class="flex h-full min-h-0 flex-row text-left">
    <!-- Loaded results drawer -->
    <aside
      v-if="btFormMode !== 'visualize'"
      class="hidden shrink-0 flex-col border-e border-default/70 transition-[width] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] md:flex"
      :class="showLeftBar ? 'w-80' : 'w-14'"
      :aria-label="t('backtest.loaded.title')"
    >
      <div class="sticky top-0 flex max-h-full flex-col gap-3 overflow-y-auto p-2">
        <UTooltip :text="showLeftBar ? t('backtest.loaded.hide') : t('backtest.loaded.show')">
          <UButton
            class="self-start"
            color="neutral"
            variant="ghost"
            :icon="showLeftBar ? 'i-mdi-chevron-double-left' : 'i-mdi-format-list-bulleted'"
            :aria-label="showLeftBar ? t('backtest.loaded.hide') : t('backtest.loaded.show')"
            :aria-expanded="showLeftBar"
            @click="showLeftBar = !showLeftBar"
          />
        </UTooltip>
        <Transition name="fade">
          <BacktestResultSelect
            v-if="showLeftBar"
            :backtest-history="botStore.activeBot.backtestHistory"
            :selected-backtest-result-key="botStore.activeBot.selectedBacktestResultKey"
            :can-use-modify="botStore.activeBot.botFeatures.backtestSetNotes"
            @selection-change="botStore.activeBot.setBacktestResultKey"
            @remove-result="botStore.activeBot.removeBacktestResultFromMemory"
            @update-result="botStore.activeBot.saveBacktestResultMetadata"
          />
        </Transition>
      </div>
    </aside>

    <div
      class="mx-auto flex w-full max-w-[1680px] min-w-0 flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8"
    >
      <header class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <h1 class="text-2xl font-semibold text-balance text-highlighted">
            {{ t('backtest.page.title') }}
          </h1>
          <p class="mt-1 text-sm text-pretty text-muted">
            {{ t('backtest.page.subtitle') }}
          </p>
        </div>
        <UButton
          v-if="btFormMode !== 'visualize'"
          class="md:hidden"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-mdi-format-list-bulleted"
          :label="showLeftBar ? t('backtest.loaded.hide') : t('backtest.loaded.title')"
          :aria-expanded="showLeftBar"
          @click="showLeftBar = !showLeftBar"
        />
        <span
          v-if="botStore.activeBot.backtestRunning"
          class="nova-num flex items-center gap-2 rounded-full bg-brand-400/15 px-3 py-1 text-sm font-medium text-brand-400"
          role="status"
        >
          <UIcon name="i-mdi-progress-clock" class="size-4" />
          {{
            t('backtest.page.running', {
              step: botStore.activeBot.backtestStep,
              progress: formatPercent(botStore.activeBot.backtestProgress, 2),
            })
          }}
        </span>
      </header>

      <BacktestResultSelect
        v-if="showLeftBar && btFormMode !== 'visualize'"
        class="md:hidden"
        :backtest-history="botStore.activeBot.backtestHistory"
        :selected-backtest-result-key="botStore.activeBot.selectedBacktestResultKey"
        :can-use-modify="botStore.activeBot.botFeatures.backtestSetNotes"
        @selection-change="botStore.activeBot.setBacktestResultKey"
        @remove-result="botStore.activeBot.removeBacktestResultFromMemory"
        @update-result="botStore.activeBot.saveBacktestResultMetadata"
      />

      <UAlert
        v-if="!botStore.activeBot.canRunBacktest"
        color="warning"
        variant="subtle"
        icon="i-mdi-information-outline"
        :title="t('backtest.page.webserverTitle')"
        :description="t('backtest.page.webserverDescription')"
      />

      <UTabs
        v-model="btFormMode"
        :items="backtestTabs"
        variant="pill"
        class="w-full min-w-0 gap-6"
        :ui="{
          root: 'items-stretch gap-6',
          list: 'w-full max-w-full self-start justify-start overflow-x-auto rounded-full border border-default/70 bg-transparent p-0.5 sm:w-max',
          indicator: 'rounded-full bg-brand-400/15 shadow-none',
          trigger:
            'shrink-0 grow-0 rounded-full px-4 py-2 text-sm font-medium text-muted hover:text-default data-[state=active]:text-highlighted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60',
          leadingIcon: 'size-4 group-data-[state=active]:text-brand-400',
          content: 'min-w-0',
        }"
      >
        <template #historic-results>
          <BacktestHistoryLoad />
        </template>
        <template #run>
          <BacktestRun />
        </template>
        <template #results>
          <BacktestResultAnalysis
            v-if="hasBacktestResult && botStore.activeBot.selectedBacktestResult"
            :backtest-result="botStore.activeBot.selectedBacktestResult"
          />
        </template>
        <template #compare-results>
          <BacktestResultComparison
            v-if="hasMultiBacktestResult"
            :backtest-results="botStore.activeBot.backtestHistory"
          />
        </template>
        <template #visualize-summary>
          <BacktestGraphs
            v-if="hasBacktestResult && botStore.activeBot.selectedBacktestResult"
            :trades="botStore.activeBot.selectedBacktestResult.trades"
            class="flex-fill"
          />
        </template>
        <template #visualize>
          <BacktestResultChart
            v-if="botStore.activeBot.selectedBacktestResult"
            :timeframe="timeframe"
            :strategy="btStore.strategy"
            :timerange="btStore.timerange"
            :backtest-result="botStore.activeBot.selectedBacktestResult"
            :freqai-model="btStore.freqAI.enabled ? btStore.freqAI.model : undefined"
          />
        </template>
      </UTabs>
    </div>
  </div>
</template>

<style lang="css" scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 300ms cubic-bezier(0.32, 0.72, 0, 1);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
