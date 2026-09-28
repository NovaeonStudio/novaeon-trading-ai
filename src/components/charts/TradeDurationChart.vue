<script setup lang="ts">
import ECharts from 'vue-echarts';
import type { ClosedTrade } from '@/types';
import type { EChartsOption } from 'echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BoxplotChart, ScatterChart } from 'echarts/charts';
import {
  DatasetComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  TransformComponent,
  VisualMapComponent,
} from 'echarts/components';

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

use([
  DatasetComponent,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  TransformComponent,
  BoxplotChart,
  CanvasRenderer,
  VisualMapComponent,
  ScatterChart,
]);

const allTrades = computed(() => {
  return props.trades.map((trade) => {
    // Convert timestamp difference to minutes (timestamps are in milliseconds)
    return (trade.close_timestamp - trade.open_timestamp) / (60 * 1000);
  });
});

const winningTrades = computed(() => {
  return props.trades
    .filter((trade) => (trade.profit_ratio ?? 0) > 0)
    .map((trade) => {
      return (trade.close_timestamp - trade.open_timestamp) / (60 * 1000);
    });
});

const losingTrades = computed(() => {
  return props.trades
    .filter((trade) => (trade.profit_ratio ?? 0) <= 0)
    .map((trade) => {
      return (trade.close_timestamp - trade.open_timestamp) / (60 * 1000);
    });
});

const chartOptions = computed((): EChartsOption => {
  const t = tokens.value;
  const groupColors = [t.textMuted, t.profit, t.loss];
  // Read here (not only in the ECharts callbacks) so the options follow a language switch.
  const groupNames = [
    tr('charts.tradeDuration.all'),
    tr('charts.tradeDuration.winning'),
    tr('charts.tradeDuration.losing'),
  ];
  return {
    title: {
      text: tr('charts.tradeDuration.title'),
      show: props.showTitle,
    },
    grid: novaGrid({ top: props.showTitle ? 40 : 16 }),
    dataset: [
      {
        id: 'allTrades',
        source: [allTrades.value, winningTrades.value, losingTrades.value],
      },
      {
        id: 'allTradesBoxplot',
        fromDatasetId: 'allTrades',
        transform: {
          type: 'boxplot',

          config: {
            itemNameFormatter: (params) => {
              if (params.value === 0) {
                return groupNames[0];
              } else if (params.value === 1) {
                return groupNames[1];
              } else if (params.value === 2) {
                return groupNames[2];
              }
            },
          },
        },
      },
      {
        id: 'outlier',
        fromDatasetIndex: 1,
        fromTransformResult: 1,
      },
    ],
    xAxis: {
      type: 'category',
      show: true,
      // data: ['All Trades', 'Winning Trades', 'Losing Trades'],
    },
    yAxis: [
      {
        type: 'value',
        axisLabel: {
          formatter: formatDuration,
        },
      },
    ],
    tooltip: {
      formatter: (params) => {
        if (params.seriesType === 'boxplot') {
          const statistics = params.data as number[];
          const c = groupColors[params.dataIndex] ?? t.textMuted;
          const row = (label: string, v: number | undefined) =>
            novaTooltipRow(t, c, label, formatDuration(v ?? 0));
          return (
            novaTooltipTitle(t, params.name) +
            row(tr('charts.tradeDuration.median'), statistics[3]) +
            row(tr('charts.tradeDuration.middleFrom'), statistics[2]) +
            row(tr('charts.tradeDuration.middleTo'), statistics[4]) +
            row(tr('charts.tradeDuration.shortest'), statistics[1]) +
            row(tr('charts.tradeDuration.longest'), statistics[5])
          );
        }
        if (params.seriesType === 'scatter') {
          const v = (params.data as number[])[1];
          return (
            novaTooltipTitle(t, tr('charts.tradeDuration.outlier')) +
            novaTooltipRow(t, t.textMuted, tr('charts.tradeDuration.held'), formatDuration(v ?? 0))
          );
        }
        return '';
      },
    },
    visualMap: [
      {
        type: 'piecewise',
        show: false,
        dimension: 0,
        pieces: [
          {
            min: 0,
            max: 0,
            label: groupNames[0],
            color: t.textMuted,
          },
          {
            min: 1,
            max: 1,
            label: groupNames[1],
            color: t.profit,
          },
          {
            min: 2,
            max: 2,
            label: groupNames[2],
            color: t.loss,
          },
        ],
      },
    ],
    series: [
      {
        name: tr('charts.tradeDuration.title'),
        type: 'boxplot',
        datasetId: 'allTradesBoxplot',
        colorBy: 'data',
        boxWidth: [12, 40],
        itemStyle: { color: t.neutralArea, borderWidth: 1.5 },
        // itemStyle: {
        //   color: '#b8c5f2',
        // },
      },
      {
        name: 'outlier',
        type: 'scatter',
        datasetId: 'outlier',
        symbolSize: 8,
        itemStyle: { color: t.textDim, borderColor: t.surface, borderWidth: 2 },
      },
    ],
  };
});

// Helper function to format duration in human-readable format
function formatDuration(minutes: number): string {
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const mins = Math.floor(minutes % 60);
    return `${hours}h ${mins}m`;
  }
  return `${Math.floor(minutes)}m`;
}
</script>

<template>
  <!-- {{ chartData }} -->
  <ECharts v-if="trades.length > 0" :option="chartOptions" autoresize :theme="chartTheme" />
</template>

<style scoped>
.echarts {
  width: 100%;
  height: 100%;
  min-height: 150px;
}
</style>
