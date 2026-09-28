<script setup lang="ts">
import { h } from 'vue';
import type { ExitReasonResults, PairResult } from '@/types';

type ResultsType = PairResult | ExitReasonResults;
type ResultsTypeWithKey = ResultsType & { key?: string | string[] };
const props = withDefaults(
  defineProps<{
    title: string;
    results: ResultsType[];
    stakeCurrency: string;
    stakeCurrencyDecimals: number;
    keyHeader?: string;
    keyHeaders?: string[];
  }>(),
  {
    keyHeader: '',
    keyHeaders: () => [],
  },
);

const tableItems = computed<ResultsTypeWithKey[]>(() =>
  props.results.map((v) => {
    if (props.keyHeaders.length > 0) {
      return {
        ...v,
        key:
          typeof v['key'] === 'string' ? Array(props.keyHeaders.length).fill(v['key']) : v['key'],
      };
    }
    return v;
  }),
);

const perTagReason = computed(() => {
  const firstFields: {
    key: string;
    label: string;
    formatter: (value: string, item: ResultsTypeWithKey) => string;
  }[] = [];
  if (props.keyHeaders.length > 0) {
    // Keys could be an array
    for (const [i, header] of props.keyHeaders.entries()) {
      firstFields.push({
        key: `key[${i}]`,
        label: header,
        formatter: (value, item) =>
          Array.isArray(value) ? value[i] : value || item['exit_reason'] || 'OTHER',
      });
    }
  } else {
    firstFields.push({
      key: 'key',
      label: props.keyHeader,
      formatter: (value, item) => (value || item['exit_reason'] || 'OTHER') as string,
    });
  }
  return firstFields;
});

const { t } = useI18n();
const settingsStore = useSettingsStore();

const metrics = computed(() =>
  availableBacktestMetrics.value.filter(
    (metric) =>
      metric.field !== 'key' && settingsStore.backtestAdditionalMetrics.includes(metric.field),
  ),
);

/** Compact, sentence case table look shared by the backtest result tables. */
const tableUi = {
  root: 'overflow-x-auto',
  base: 'min-w-full',
  th: 'px-3 py-2 text-xs font-medium whitespace-nowrap text-muted text-start',
  td: 'px-3 py-2 text-sm whitespace-nowrap text-default',
  tr: 'transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40',
  separator: 'bg-default/50',
};
const numMeta = { class: { th: 'text-end', td: 'nova-num text-end' } };
/** Profit / loss colored number cell. */
function pnlCell(value: number | undefined | null, text: string) {
  const v = value ?? 0;
  return h('span', { class: v > 0 ? 'text-emerald-400' : v < 0 ? 'text-rose-400' : '' }, text);
}

const tableColumns = computed(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cols: any[] = [];

  // Dynamic first columns (key/tags)
  perTagReason.value.forEach((col, i) => {
    cols.push({
      id: `key_${i}`,
      header: col.label,
      cell: ({ row }) => col.formatter(row.original['key'] as string, row.original),
    });
  });

  // Fixed metric columns
  cols.push({ accessorKey: 'trades', header: t('backtest.col.trades'), meta: numMeta });
  cols.push({
    id: 'profit_mean',
    header: t('backtest.col.avgProfitPct'),
    meta: numMeta,
    cell: ({ row }) =>
      pnlCell(row.original.profit_mean, formatPercent(row.original.profit_mean, 2)),
  });
  cols.push({
    id: 'profit_total_abs',
    header: t('backtest.col.totalProfitCurrency', { currency: props.stakeCurrency }),
    meta: numMeta,
    cell: ({ row }) =>
      pnlCell(
        row.original.profit_total_abs,
        formatPrice(row.original.profit_total_abs, props.stakeCurrencyDecimals),
      ),
  });
  cols.push({
    id: 'profit_total',
    header: t('backtest.col.totalProfitPct'),
    meta: numMeta,
    cell: ({ row }) =>
      pnlCell(row.original.profit_total, formatPercent(row.original.profit_total, 2)),
  });
  cols.push({ accessorKey: 'wins', header: t('backtest.col.wins'), meta: numMeta });
  cols.push({ accessorKey: 'draws', header: t('backtest.col.draws'), meta: numMeta });
  cols.push({ accessorKey: 'losses', header: t('backtest.col.losses'), meta: numMeta });

  // Dynamic additional metric columns
  metrics.value.forEach((col) => {
    cols.push({
      accessorKey: col.field,
      header: col.header,
      meta: numMeta,
      cell: ({ row }) =>
        col.is_ratio
          ? formatPercent(row.original[col.field as keyof ResultsTypeWithKey] as number, 2)
          : formatPrice(row.original[col.field as keyof ResultsTypeWithKey] as number, 2),
    });
  });

  return cols;
});
</script>
<template>
  <NovaPanel :title="title">
    <template #actions>
      <div class="flex w-full items-center gap-2 sm:w-auto">
        <label :for="`bt-metrics-${title}`" class="text-sm whitespace-nowrap text-muted">{{
          t('backtest.col.extraColumns')
        }}</label>
        <USelectMenu
          :id="`bt-metrics-${title}`"
          v-model="settingsStore.backtestAdditionalMetrics"
          multiple
          size="sm"
          :items="availableBacktestMetrics"
          label-key="header"
          value-key="field"
          :placeholder="t('common.none')"
          class="w-full min-w-40 sm:w-56"
        />
      </div>
    </template>
    <UTable :data="tableItems" :columns="tableColumns" :ui="tableUi" />
  </NovaPanel>
</template>
