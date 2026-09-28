<script setup lang="ts">
import type { PeriodicBreakdown } from '@/types';
import type { TableColumn } from '@nuxt/ui';

const props = defineProps<{
  periodicBreakdown: PeriodicBreakdown;
}>();
const { t } = useI18n();

const periodicBreakdownSelections = computed(() => {
  const res = [
    { value: 'day', label: t('backtest.period.days') },
    { value: 'week', label: t('backtest.period.weeks') },
    { value: 'month', label: t('backtest.period.months') },
  ];
  if (props.periodicBreakdown.year) {
    res.push({ value: 'year', label: t('backtest.period.years') });
  }
  if (props.periodicBreakdown.weekday) {
    res.push({ value: 'weekday', label: t('backtest.period.weekday') });
  }

  return res;
});

const periodicBreakdownPeriod = ref<string>('month');

type PeriodRow = {
  date: string;
  trades?: number;
  profit_abs?: number;
  profit_factor?: number;
  wins?: number;
  draws?: number;
  losses?: number;
  loses?: number;
};

const numMeta = { class: { th: 'text-end', td: 'nova-num text-end' } };
const columns = computed<TableColumn<PeriodRow>[]>(() => [
  { accessorKey: 'date', header: t('backtest.col.date'), meta: { class: { td: 'nova-num' } } },
  { accessorKey: 'trades', header: t('backtest.col.trades'), meta: numMeta },
  { accessorKey: 'profit_abs', header: t('backtest.col.totalProfit'), meta: numMeta },
  { accessorKey: 'profit_factor', header: t('backtest.col.profitFactor'), meta: numMeta },
  { accessorKey: 'wins', header: t('backtest.col.wins'), meta: numMeta },
  { accessorKey: 'draws', header: t('backtest.col.draws'), meta: numMeta },
  { accessorKey: 'losses', header: t('backtest.col.losses'), meta: numMeta },
  { id: 'win_rate', header: t('backtest.col.winRate'), meta: numMeta },
]);

/** Compact, sentence case table look shared by the backtest result tables. */
const tableUi = {
  root: 'overflow-x-auto',
  base: 'min-w-full',
  th: 'px-3 py-2 text-xs font-medium whitespace-nowrap text-muted text-start',
  td: 'px-3 py-2 text-sm whitespace-nowrap text-default',
  tr: 'transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40',
  separator: 'bg-default/50',
};
</script>

<template>
  <div class="flex flex-col gap-4">
    <USegmentedControl
      v-model="periodicBreakdownPeriod"
      :items="periodicBreakdownSelections"
      value-key="value"
      size="md"
      class="self-start"
      :aria-label="t('backtest.period.label')"
    ></USegmentedControl>
    <UTable :data="periodicBreakdown[periodicBreakdownPeriod]" :columns="columns" :ui="tableUi">
      <template #trades-cell="{ row }">
        {{ row.original.trades ?? 'N/A' }}
      </template>
      <template #profit_abs-cell="{ row }">
        <span
          :class="
            (row.original.profit_abs ?? 0) > 0
              ? 'text-emerald-400'
              : (row.original.profit_abs ?? 0) < 0
                ? 'text-rose-400'
                : ''
          "
          >{{ formatNumber(row.original.profit_abs, 2) }}</span
        >
      </template>
      <template #profit_factor-cell="{ row }">
        {{ formatPrice(row.original.profit_factor ?? null, 2) }}
      </template>
      <template #losses-cell="{ row }">
        {{ row.original.loses ?? row.original.losses ?? 'N/A' }}
      </template>
      <template #win_rate-cell="{ row }">
        {{
          formatPercent(
            row.original.wins! /
              (row.original.wins! +
                row.original.draws! +
                (row.original.loses ?? row.original.losses ?? 0)),
            2,
          )
        }}
      </template>
    </UTable>
  </div>
</template>
