<script setup lang="ts">
import type { StrategyBacktestResult } from '@/types';

const props = defineProps<{
  backtestResult: StrategyBacktestResult;
}>();
const { t } = useI18n();

const backtestResultStats = computed(() => {
  const tmp = generateBacktestMetricRows(props.backtestResult);
  return formatObjectForTable({ value: tmp }, 'metric');
});

/** Compact, sentence case table look shared by the backtest result tables. */
const tableUi = {
  root: 'overflow-x-auto',
  base: 'min-w-full',
  th: 'px-3 py-2 text-xs font-medium whitespace-nowrap text-muted text-start',
  td: 'px-3 py-2 text-sm whitespace-nowrap text-default',
  tr: 'transition-colors duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] hover:bg-accented/40',
  separator: 'bg-default/50',
};
const kvColumns = (keyField: string, keyHeader: string) => [
  {
    accessorKey: keyField,
    header: keyHeader,
    meta: { class: { td: 'whitespace-normal text-muted' } },
  },
  {
    accessorKey: 'value',
    header: t('backtest.analysis.value'),
    meta: {
      class: {
        th: 'text-end',
        td: 'nova-num text-end font-medium break-words whitespace-normal text-highlighted',
      },
    },
  },
];

const backtestResultSettings = computed(() => {
  // Transpose Result into readable format
  const tmp = generateBacktestSettingRows(props.backtestResult);

  return formatObjectForTable({ value: tmp }, 'setting');
});
</script>

<template>
  <div class="flex w-full min-w-0 flex-col gap-6 text-start">
    <header>
      <h2 class="text-lg font-semibold text-balance text-highlighted">
        {{ t('backtest.analysis.title', { strategy: backtestResult.strategy_name }) }}
      </h2>
      <p class="nova-num mt-1 text-sm text-muted">
        {{ backtestResult.timeframe }} ·
        {{
          t('backtest.trades', { count: backtestResult.total_trades }, backtestResult.total_trades)
        }}
        ·
        <span :class="backtestResult.profit_total >= 0 ? 'text-emerald-400' : 'text-rose-400'">{{
          formatPercent(backtestResult.profit_total, 2)
        }}</span>
      </p>
    </header>

    <div class="grid grid-cols-1 items-start gap-6 xl:grid-cols-2">
      <NovaPanel :title="t('backtest.analysis.strategySettings')">
        <UTable
          :data="backtestResultSettings"
          :columns="kvColumns('setting', t('backtest.analysis.setting'))"
          :ui="tableUi"
        />
      </NovaPanel>
      <NovaPanel :title="t('backtest.analysis.metrics')">
        <UTable
          :data="backtestResultStats"
          :columns="kvColumns('metric', t('backtest.analysis.metric'))"
          :ui="tableUi"
        />
      </NovaPanel>
    </div>
    <BacktestResultTablePer
      :title="t('backtest.analysis.perEntryTag')"
      :results="backtestResult.results_per_enter_tag"
      :stake-currency="backtestResult.stake_currency"
      :key-header="t('backtest.analysis.entryTag')"
      :stake-currency-decimals="backtestResult.stake_currency_decimals"
    />

    <BacktestResultTablePer
      :title="t('backtest.analysis.perExitReason')"
      :results="backtestResult.exit_reason_summary ?? []"
      :stake-currency="backtestResult.stake_currency"
      :key-header="t('backtest.analysis.exitReason')"
      :stake-currency-decimals="backtestResult.stake_currency_decimals"
    />

    <BacktestResultTablePer
      v-if="backtestResult.mix_tag_stats"
      :title="t('backtest.analysis.perEntryAndExitTag')"
      :results="backtestResult.mix_tag_stats ?? []"
      :stake-currency="backtestResult.stake_currency"
      :key-headers="[t('backtest.analysis.entryTag'), t('backtest.analysis.exitTag')]"
      :stake-currency-decimals="backtestResult.stake_currency_decimals"
    />

    <BacktestResultTablePer
      :title="t('backtest.analysis.perPair')"
      :results="backtestResult.results_per_pair"
      :stake-currency="backtestResult.stake_currency"
      :key-header="t('backtest.analysis.pair')"
      :stake-currency-decimals="backtestResult.stake_currency_decimals"
    />
    <NovaPanel
      v-if="backtestResult.periodic_breakdown"
      :title="t('backtest.analysis.periodicBreakdown')"
    >
      <BacktestResultPeriodBreakdown :periodic-breakdown="backtestResult.periodic_breakdown">
      </BacktestResultPeriodBreakdown>
    </NovaPanel>

    <NovaPanel :title="t('backtest.analysis.singleTrades')">
      <TradeList
        :trades="backtestResult.trades"
        :show-filter="true"
        :stake-currency="backtestResult.stake_currency"
      />
    </NovaPanel>
  </div>
</template>
