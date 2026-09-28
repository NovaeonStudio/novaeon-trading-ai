<script setup lang="ts">
import ECharts from 'vue-echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  TransformComponent,
} from 'echarts/components';

import { registerTransform } from 'echarts';

import type { TimeSummaryCols, TimeSummaryRecord, TimeSummaryReturnValue } from '@/types';
import type { EChartsOption } from 'echarts';

use([
  BarChart,
  CanvasRenderer,
  GridComponent,
  DatasetComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  TransformComponent,
]);

const props = withDefaults(
  defineProps<{
    dailyStats: TimeSummaryReturnValue;
    showTitle?: boolean;
    profitCol: TimeSummaryCols;
  }>(),
  {
    showTitle: true,
  },
);

const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

// Series / legend labels (translated, rebuilt on a language switch)
const CHART_PROFIT = computed(() =>
  props.profitCol === 'abs_profit'
    ? tr('charts.timePeriod.absProfit')
    : tr('charts.timePeriod.relProfit'),
);
const CHART_TRADE_COUNT = computed(() => tr('charts.shared.tradeCount'));

const dailyChart = ref(null);

registerTransform(ftEchartsTransforms.multiple);

/**
 * Profit per period (top pane, bars colored by sign) and trade count (bottom pane) share the time
 * axis in two stacked grids instead of two y-scales on one plot.
 */
const dailyChartOptions: ComputedRef<EChartsOption> = computed(() => {
  const t = tokens.value;
  const isRel = props.profitCol === 'rel_profit';
  const rows = props.dailyStats.data;
  const profitOf = (r: TimeSummaryRecord) => (isRel ? r.rel_profit * 100 : r.abs_profit);
  return {
    title: {
      text: tr('charts.timePeriod.title'),
      show: props.showTitle,
    },
    legend: {
      data: [CHART_PROFIT.value, CHART_TRADE_COUNT.value],
      top: 0,
      right: 0,
      selectedMode: false,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: t.neutralArea } },
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params];
        const i = list[0]?.dataIndex ?? -1;
        const r = rows[i];
        if (!r) return '';
        const absProfit = typeof r.abs_profit === 'number' ? formatNumber(r.abs_profit, 3) : '-';
        const relProfit =
          typeof r.rel_profit === 'number' ? `${formatNumber(r.rel_profit * 100, 2)}%` : '-';
        return (
          novaTooltipTitle(t, r.date) +
          novaTooltipRow(
            t,
            novaPnlColor(t, r.abs_profit),
            tr('charts.shared.profit'),
            `${absProfit} (${relProfit})`,
          ) +
          novaTooltipRow(t, t.neutral, tr('charts.shared.trades'), r.trade_count ?? '-')
        );
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 56, right: 16, top: 36, bottom: '34%', outerBoundsMode: 'none' },
      { left: 56, right: 16, top: '72%', bottom: 28, outerBoundsMode: 'none' },
    ],
    xAxis: [
      {
        type: 'category',
        gridIndex: 0,
        data: rows.map((r) => r.date),
        axisLabel: { show: false },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: rows.map((r) => r.date),
        axisLabel: { hideOverlap: true },
      },
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        splitNumber: 4,
        axisLabel: { formatter: (value: number) => (isRel ? `${value}%` : `${value}`) },
      },
      {
        type: 'value',
        gridIndex: 1,
        splitNumber: 2,
        minInterval: 1,
      },
    ],
    series: [
      {
        type: 'bar',
        name: CHART_PROFIT.value,
        color: t.profit,
        xAxisIndex: 0,
        yAxisIndex: 0,
        barCategoryGap: '25%',
        data: rows.map((r) => {
          const v = profitOf(r);
          return {
            value: v,
            itemStyle: { color: novaPnlColor(t, v), borderRadius: novaBarRadius(v) },
          };
        }),
      },
      {
        type: 'bar',
        name: CHART_TRADE_COUNT.value,
        color: t.neutral,
        xAxisIndex: 1,
        yAxisIndex: 1,
        barCategoryGap: '25%',
        data: rows.map((r) => r.trade_count),
      },
    ],
  };
});
</script>

<template>
  <ECharts
    v-if="dailyStats.data"
    ref="dailyChart"
    :option="dailyChartOptions"
    :theme="chartTheme"
    :style="{ height: '100%' }"
    autoresize
  />
</template>

<style lang="css" scoped>
.echarts {
  min-height: 240px;
  height: 100%;
}
</style>
