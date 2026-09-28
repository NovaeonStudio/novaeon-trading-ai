<script setup lang="ts">
import ECharts from 'vue-echarts';
// import { EChartsOption } from 'echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  CalendarComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  TransformComponent,
} from 'echarts/components';
import { registerTransform } from 'echarts';

import type { BacktestMarketChange } from '@/types';
import type { EChartsOption } from 'echarts';

use([
  LineChart,
  CalendarComponent,
  CanvasRenderer,
  GridComponent,
  DatasetComponent,
  DataZoomComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  TransformComponent,
]);

const props = withDefaults(
  defineProps<{
    marketChangeData: BacktestMarketChange | null;
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);

const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

const marketChangeChart = ref(null);
registerTransform(ftEchartsTransforms.multiple);

const marketChangeOptions: ComputedRef<EChartsOption> = computed(() => {
  if (!props.marketChangeData) {
    return {};
  }
  const colDate = props.marketChangeData.columns.findIndex((el) => el === '__date_ts');
  const colRelMean = props.marketChangeData.columns.findIndex((el) => el === 'rel_mean');
  const t = tokens.value;
  return {
    title: {
      text: tr('charts.marketChange.title'),
      show: props.showTitle,
    },
    dataset: [
      {
        source: props.marketChangeData.data,
      },
      {
        transform: {
          type: 'ft:multiple',
          config: { dimension: colRelMean, factor: 100, mode: 'array' },
        },
      },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
      },
      formatter: (params) => {
        const p = (Array.isArray(params) ? params : [params])[0];
        const row = (p?.data ?? []) as number[];
        const v = Number(row[colRelMean]);
        return (
          novaTooltipTitle(t, timestampms(Number(row[colDate]))) +
          novaTooltipRow(t, t.secondary, tr('charts.marketChange.average'), `${v.toFixed(2)}%`)
        );
      },
    },
    grid: {
      ...echartsGridDefault,
      top: props.showTitle ? 36 : 16,
    },
    xAxis: [
      {
        type: 'time',
        axisLine: { onZero: false },
        axisLabel: { show: true, hideOverlap: true },
        axisPointer: {
          label: { show: false },
        },
        // position: 'top',
        splitLine: { show: false },
        splitNumber: 6,
        min: 'dataMin',
        max: 'dataMax',
      },
    ],
    yAxis: [
      {
        type: 'value',
        axisLabel: { formatter: '{value}%' },
      },
    ],
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100,
      },
      {
        bottom: 8,
        start: 0,
        end: 100,
        ...dataZoomPartial,
      },
    ],
    series: [
      {
        type: 'line',
        name: tr('charts.marketChange.series'),
        showSymbol: false,
        color: t.secondary,
        lineStyle: { width: 2 },
        areaStyle: { color: t.secondary, opacity: 0.1 },
        datasetIndex: 1,
        encode: {
          x: colDate,
          // open, close, low, high
          y: colRelMean,
        },
      },
    ],
  };
});
</script>

<template>
  <ECharts
    v-if="marketChangeData?.data"
    ref="marketChangeChart"
    :option="marketChangeOptions"
    :theme="chartTheme"
    autoresize
  />
</template>

<style lang="css" scoped>
.echarts {
  min-height: 240px;
  height: 100%;
}
</style>
