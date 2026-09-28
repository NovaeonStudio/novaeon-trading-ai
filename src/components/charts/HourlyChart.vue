<script setup lang="ts">
// TODO: is this component used?!?
import ECharts from 'vue-echarts';

import type { Trade } from '@/types';
import type { EChartsOption } from 'echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';

use([BarChart, CanvasRenderer, GridComponent, LegendComponent, TitleComponent, TooltipComponent]);

const props = withDefaults(
  defineProps<{
    trades: Trade[];
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);
const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

const hourlyData = computed(() => {
  const res = new Array(24);
  for (let i = 0; i < 24; i += 1) {
    res[i] = { hour: i, hourDesc: `${i}h`, profit: 0.0, count: 0.0 };
  }

  for (let i = 0, len = props.trades.length; i < len; i += 1) {
    const trade = props.trades[i];
    if (trade && trade.close_timestamp) {
      const hour = timestampHour(trade.close_timestamp);

      res[hour].profit += trade.profit_ratio;
      res[hour].count += 1;
    }
  }
  return res;
});
/** Profit per hour (top pane) and trade count (bottom pane) in stacked grids, one y-scale each. */
const hourlyChartOptions = computed((): EChartsOption => {
  const t = tokens.value;
  const rows = hourlyData.value as { hourDesc: string; profit: number; count: number }[];
  const hours = rows.map((r) => r.hourDesc);
  const nameProfit = tr('charts.shared.profitPct');
  const nameTradeCount = tr('charts.shared.tradeCount');
  return {
    title: {
      text: tr('charts.hourly.title'),
      show: props.showTitle,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: t.neutralArea } },
      formatter: (params) => {
        const i = (Array.isArray(params) ? params : [params])[0]?.dataIndex ?? -1;
        const r = rows[i];
        if (!r) return '';
        return (
          novaTooltipTitle(t, r.hourDesc) +
          novaTooltipRow(
            t,
            novaPnlColor(t, r.profit),
            tr('charts.shared.profit'),
            formatPercent(r.profit, 2),
          ) +
          novaTooltipRow(t, t.neutral, tr('charts.shared.trades'), r.count)
        );
      },
    },
    legend: {
      data: [nameProfit, nameTradeCount],
      right: 0,
      top: 0,
      selectedMode: false,
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 56, right: 16, top: 36, bottom: '34%', outerBoundsMode: 'none' },
      { left: 56, right: 16, top: '72%', bottom: 28, outerBoundsMode: 'none' },
    ],
    xAxis: [
      { type: 'category', gridIndex: 0, data: hours, axisLabel: { show: false } },
      { type: 'category', gridIndex: 1, data: hours, axisLabel: { hideOverlap: true } },
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        splitNumber: 4,
        axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
      },
      { type: 'value', gridIndex: 1, splitNumber: 2, minInterval: 1 },
    ],
    series: [
      {
        type: 'bar',
        name: nameProfit,
        color: t.profit,
        animation: false,
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: rows.map((r) => ({
          value: r.profit,
          itemStyle: { color: novaPnlColor(t, r.profit), borderRadius: novaBarRadius(r.profit) },
        })),
      },
      {
        type: 'bar',
        name: nameTradeCount,
        color: t.neutral,
        animation: false,
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: rows.map((r) => r.count),
      },
    ],
  };
});
</script>

<template>
  <ECharts v-if="trades.length > 0" :option="hourlyChartOptions" autoresize :theme="chartTheme" />
</template>

<style scoped>
.echarts {
  width: 100%;
  height: 100%;
  min-height: 240px;
}
</style>
