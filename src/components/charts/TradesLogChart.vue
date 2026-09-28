<script setup lang="ts">
import ECharts from 'vue-echarts';
import type { EChartsOption } from 'echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';

import type { ClosedTrade } from '@/types';

use([BarChart, CanvasRenderer, DataZoomComponent, GridComponent, TitleComponent, TooltipComponent]);

const props = withDefaults(
  defineProps<{
    trades: ClosedTrade[];
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);
const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

interface LogRow {
  profit: number;
  pair: string;
  botName?: string;
  closed: string;
  side: string;
}

const chartData = computed<LogRow[]>(() =>
  props.trades
    .slice(0)
    .sort((a, b) => (a.close_timestamp > b.close_timestamp ? 1 : -1))
    .map((trade) => ({
      profit: Number(((trade.profit_ratio ?? 0) * 100).toFixed(2)),
      pair: trade.pair,
      botName: trade.botName,
      closed: timestampms(trade.close_timestamp),
      side: trade.is_short === undefined || !trade.is_short ? 'Long' : 'Short',
    })),
);

const chartOptions = computed((): EChartsOption => {
  const t = tokens.value;
  // Show a maximum of 50 trades by default - allowing to zoom out further.
  const datazoomStart = chartData.value.length > 0 ? (1 - 50 / chartData.value.length) * 100 : 100;
  return {
    title: {
      text: tr('charts.tradesLog.title'),
      show: props.showTitle,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: t.neutralArea } },
      formatter: (params) => {
        const p = (Array.isArray(params) ? params : [params])[0];
        const row = chartData.value[p?.dataIndex ?? -1];
        if (!row) return '';
        const who = [row.pair, row.side, row.botName].filter(Boolean).join(' · ');
        return (
          novaTooltipTitle(t, row.closed) +
          novaTooltipRow(t, novaPnlColor(t, row.profit), who, `${row.profit.toFixed(2)}%`)
        );
      },
    },
    xAxis: {
      type: 'category',
      show: false,
      data: chartData.value.map((_, i) => i),
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%' },
    },
    grid: { ...echartsGridDefault, top: props.showTitle ? 36 : 12 },
    dataZoom: [
      {
        type: 'inside',
        start: datazoomStart,
        end: 100,
      },
      {
        bottom: 8,
        start: datazoomStart,
        end: 100,
        ...dataZoomPartial,
      },
    ],
    series: [
      {
        type: 'bar',
        name: tr('charts.shared.profitPct'),
        barCategoryGap: '25%',
        animation: false,
        data: chartData.value.map((r) => ({
          value: r.profit,
          itemStyle: { color: novaPnlColor(t, r.profit), borderRadius: novaBarRadius(r.profit) },
        })),
      },
    ],
  };
});
</script>

<template>
  <ECharts v-if="trades.length > 0" :option="chartOptions" autoresize :theme="chartTheme" />
</template>

<style scoped>
.echarts {
  width: 100%;
  height: 100%;
  min-height: 150px;
}
</style>
