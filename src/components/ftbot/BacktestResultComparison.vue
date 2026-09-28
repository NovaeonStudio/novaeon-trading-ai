<script setup lang="ts">
import { h, resolveComponent } from 'vue';
import type { BacktestResultInMemory } from '@/types';

const props = withDefaults(
  defineProps<{
    backtestResults: Record<string, BacktestResultInMemory>;
  }>(),
  {},
);
const { t } = useI18n();

const backtestResultStats = computed(() => {
  const values = {};
  Object.entries(props.backtestResults).forEach(([key, result]) => {
    const tmp = generateBacktestMetricRows(result.strategy);
    values[key] = tmp;
  });
  return formatObjectForTable(values, 'metric');
});

const backtestResultFields = computed(() => {
  const res = [{ key: 'metric', label: t('backtest.analysis.metric') }];
  Object.entries(props.backtestResults).forEach(([key, value]) => {
    res.push({ key, label: value.metadata.strategyName });
  });
  return res;
});

const BacktestResultSelectEntry = resolveComponent('BacktestResultSelectEntry');

/** Compact, sentence case table look shared by the backtest result tables. */
const tableUi = {
  root: 'overflow-x-auto',
  base: 'min-w-full',
  th: 'px-3 py-2 text-xs font-medium whitespace-nowrap text-muted text-start align-bottom',
  td: 'px-3 py-2 text-sm whitespace-nowrap text-default',
  tr: 'transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40',
  separator: 'bg-default/50',
};

const tableColumns = computed(() => {
  return backtestResultFields.value.map((col) => ({
    accessorKey: col.key,
    meta:
      col.key === 'metric'
        ? { class: { td: 'text-muted' } }
        : { class: { th: 'text-end', td: 'nova-num text-end' } },
    header: () => {
      if (col.key && props.backtestResults[col.key]) {
        return h(BacktestResultSelectEntry, {
          backtestResult: props.backtestResults[col.key],
        });
      }
      return col.label;
    },
  }));
});
</script>

<template>
  <div class="flex w-full min-w-0 flex-col gap-6 text-start">
    <header>
      <h2 class="text-lg font-semibold text-balance text-highlighted">
        {{ t('backtest.tabs.compare') }}
      </h2>
      <p class="mt-1 text-sm text-pretty text-muted">
        {{ t('backtest.compare.subtitle') }}
      </p>
    </header>
    <NovaPanel>
      <UTable :data="backtestResultStats" :columns="tableColumns" :ui="tableUi" />
    </NovaPanel>
  </div>
</template>
