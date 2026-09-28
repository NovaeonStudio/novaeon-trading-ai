<script setup lang="ts">
import ECharts from 'vue-echarts';
import type { EChartsOption } from 'echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart } from 'echarts/charts';
import { GridComponent, TitleComponent, TooltipComponent } from 'echarts/components';

import type { ClosedTrade } from '@/types';

use([BarChart, CanvasRenderer, GridComponent, TitleComponent, TooltipComponent]);

const props = withDefaults(
  defineProps<{
    trades: ClosedTrade[];
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);
const settingsStore = useSettingsStore();
const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

const binOptions = [
  { label: '10', value: 10 },
  { label: '15', value: 15 },
  { label: '20', value: 20 },
  { label: '25', value: 25 },
  { label: '50', value: 50 },
];
const data = computed(() => {
  const profits = props.trades
    .filter((trade) => isDefined(trade.profit_ratio))
    .map((trade) => trade.profit_ratio ?? 0);

  return binData(profits, settingsStore.profitDistributionBins);
});

const pctLabel = (ratio: number) => `${(ratio * 100).toFixed(1)}%`;

const chartOptions = computed((): EChartsOption => {
  const t = tokens.value;
  const bins = data.value;
  return {
    title: {
      text: tr('charts.profitDistribution.title'),
      show: props.showTitle,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: t.neutralArea } },
      formatter: (params) => {
        const p = (Array.isArray(params) ? params : [params])[0];
        const i = p?.dataIndex ?? -1;
        const bin = bins[i];
        if (!bin) return '';
        const next = bins[i + 1]?.[0];
        const range =
          next !== undefined
            ? tr('charts.profitDistribution.range', { from: pctLabel(bin[0]!), to: pctLabel(next) })
            : tr('charts.profitDistribution.rangeFrom', { from: pctLabel(bin[0]!) });
        return (
          novaTooltipTitle(t, range) +
          novaTooltipRow(t, t.neutral, tr('charts.shared.trades'), bin[1])
        );
      },
    },
    xAxis: {
      type: 'category',
      data: bins.map((b) => pctLabel(b[0]!)),
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
    },
    grid: novaGrid({ top: 48 }),
    series: [
      {
        type: 'bar',
        name: tr('charts.shared.tradeCount'),
        barCategoryGap: '20%',
        data: bins.map((b, i) => {
          const start = b[0] ?? 0;
          const end = bins[i + 1]?.[0] ?? start;
          const color = start >= 0 ? t.profit : end > 0 ? t.neutral : t.loss;
          return { value: b[1], itemStyle: { color } };
        }),
      },
    ],
  };
});
</script>

<template>
  <div class="relative flex h-full flex-col">
    <div class="absolute top-0 right-0 z-10 flex items-center gap-2">
      <label for="input-bins" class="nova-label">{{ tr('charts.profitDistribution.bins') }}</label>
      <USelect
        id="input-bins"
        v-model="settingsStore.profitDistributionBins"
        size="sm"
        class="min-w-20"
        :items="binOptions"
      />
    </div>
    <div class="min-h-0 grow">
      <ECharts v-if="trades" :option="chartOptions" autoresize :theme="chartTheme" />
    </div>
  </div>
</template>

<style scoped>
.echarts {
  width: 100%;
  height: 100%;
  min-height: 150px;
}
</style>
