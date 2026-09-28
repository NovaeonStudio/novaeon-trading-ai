<script setup lang="ts">
const { t } = useI18n();
const botStore = useBotStore();
enum PerformanceOptions {
  performance = 'performance',
  entryStats = 'entryStats',
  exitStats = 'exitStats',
  mixTagStats = 'mixTagStats',
}
const selectedOption = ref<PerformanceOptions>(PerformanceOptions.performance);

function formatTextLen(text: string, len: number) {
  if (text.length > len) {
    return text.substring(0, len) + '...';
  }
  return text;
}

const performanceTable = computed<
  {
    key: string;
    label: string;
    formatter?: (v: unknown) => string;
  }[]
>(() => {
  const textLength = 17;
  const initialCol = {
    [PerformanceOptions.performance]: { key: 'pair', label: t('bot.performance.colPair') },
    [PerformanceOptions.entryStats]: {
      key: 'enter_tag',
      label: t('bot.performance.colEnterTag'),
      formatter: (v: unknown) => formatTextLen(v as string, textLength),
    },
    [PerformanceOptions.exitStats]: {
      key: 'exit_reason',
      label: t('bot.performance.colExitReason'),
      formatter: (v: unknown) => formatTextLen(v as string, textLength),
    },
    [PerformanceOptions.mixTagStats]: {
      key: 'mix_tag',
      label: t('bot.performance.colMixTag'),
      formatter: (v: unknown) => formatTextLen(v as string, textLength),
    },
  };
  return [
    initialCol[selectedOption.value],
    { key: 'profit', label: t('bot.performance.colProfitPct') },
    {
      key: 'profit_abs',
      label: t('bot.performance.colProfitAbs', {
        currency: `${botStore.activeBot.botState?.stake_currency}`,
      }),
      formatter: (v: unknown) => formatPrice(v as number, 5),
    },
    { key: 'count', label: t('bot.performance.colCount') },
  ];
});

const performanceData = computed(() => {
  if (selectedOption.value === PerformanceOptions.performance) {
    return botStore.activeBot.performanceStats;
  }
  if (selectedOption.value === PerformanceOptions.entryStats) {
    return botStore.activeBot.entryStats;
  }
  if (selectedOption.value === PerformanceOptions.exitStats) {
    return botStore.activeBot.exitStats;
  }
  if (selectedOption.value === PerformanceOptions.mixTagStats) {
    return botStore.activeBot.mixTagStats;
  }
  return [];
});

const options = computed(() => [
  { value: PerformanceOptions.performance, text: t('bot.performance.optPerformance') },
  { value: PerformanceOptions.entryStats, text: t('bot.performance.optEntries') },
  { value: PerformanceOptions.exitStats, text: t('bot.performance.optExits') },
  { value: PerformanceOptions.mixTagStats, text: t('bot.performance.optMixTag') },
]);

function refreshSummary() {
  if (selectedOption.value === PerformanceOptions.performance) {
    botStore.activeBot.getPerformance();
  }
  if (selectedOption.value === PerformanceOptions.entryStats) {
    botStore.activeBot.getEntryStats();
  }
  if (selectedOption.value === PerformanceOptions.exitStats) {
    botStore.activeBot.getExitStats();
  }
  if (selectedOption.value === PerformanceOptions.mixTagStats) {
    botStore.activeBot.getMixTagStats();
  }
}

onMounted(() => {
  refreshSummary();
});

const tableColumns = computed(() => {
  return performanceTable.value.map((field) => ({
    accessorKey: field.key,
    header: field.label,
    cell: ({ row }: { row: { original: Record<string, unknown> } }) =>
      field.formatter ? field.formatter(row.original[field.key]) : row.original[field.key],
  }));
});

watch(selectedOption, () => {
  refreshSummary();
});
</script>
<template>
  <div>
    <div class="mb-2">
      <h3 class="me-auto text-2xl inline">{{ t('bot.performance.title') }}</h3>
      <UButton class="float-end" color="neutral" icon="mdi:refresh" @click="refreshSummary" />
    </div>
    <USegmentedControl
      v-if="botStore.activeBot.botFeatures.hasAdvancedStats"
      id="order-direction"
      v-model="selectedOption"
      :items="options"
      label-key="text"
      value-key="value"
      size="sm"
    ></USegmentedControl>
    <UTable class="text-center" :data="performanceData" :columns="tableColumns" />
  </div>
</template>
