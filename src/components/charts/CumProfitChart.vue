<script setup lang="ts">
import type { EChartsOption } from 'echarts';
import ECharts from 'vue-echarts';

import { BarChart, LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';

import type {
  ClosedTrade,
  CumProfitChartData,
  CumProfitData,
  CumProfitDataPerDate,
  Trade,
} from '@/types';
import type { ComputedRefWithControl } from '@vueuse/core';

use([
  BarChart,
  LineChart,

  CanvasRenderer,

  DatasetComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
]);

const props = withDefaults(
  defineProps<{
    trades: ClosedTrade[];
    openTrades?: Trade[];
    showTitle?: boolean;
    profitColumn?: string;
  }>(),
  {
    openTrades: () => [],
    showTitle: true,
    profitColumn: 'profit_abs',
  },
);
const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr, locale } = useI18n();

const openProfit = computed<number>(() => {
  return props.openTrades.reduce(
    (a, v) => a + (v['total_profit_abs'] ?? v[props.profitColumn] ?? 0),
    0,
  );
});

const cumulativeData = computed<CumProfitChartData[]>(() => {
  // const res: CumProfitData[] = [];
  const resD: CumProfitDataPerDate = {};
  const closedTrades = props.trades
    .slice()
    .sort((a, b) => (a.close_timestamp > b.close_timestamp ? 1 : -1));
  let profit = 0.0;
  let first = true;

  for (let i = 0, len = closedTrades.length; i < len; i += 1) {
    const trade = closedTrades[i];
    if (!trade) continue;
    if (first) {
      // Start with chart with a 0 entry
      first = false;
      if (!resD[trade.open_timestamp]) {
        // New timestamp
        resD[trade.open_timestamp] = { profit, [trade.botId]: profit };
      } else {
        // Add to existing profit
        resD[trade.open_timestamp]![trade.botId] = profit;
      }
    }

    if (trade.close_timestamp && trade[props.profitColumn]) {
      profit += trade[props.profitColumn];
      const resDEntry = resD[trade.close_timestamp];
      if (!resDEntry) {
        // New timestamp
        resD[trade.close_timestamp] = { profit, [trade.botId]: profit };
      } else {
        // Add to existing profit
        resDEntry.profit += trade[props.profitColumn];
        if (resDEntry[trade.botId]) {
          resDEntry[trade.botId] += trade[props.profitColumn];
        } else {
          resDEntry[trade.botId] = profit;
        }
      }
      // res.push({ date: trade.close_timestamp, profit, [trade.botId]: profit });
    }
  }

  const valueArray: CumProfitChartData[] = Object.entries(resD).map(
    ([k, v]: [string, CumProfitData]) => {
      const obj = { date: parseInt(k, 10), profit: v.profit };
      // TODO: The below could allow "lines" per bot"
      // this.botList.forEach((botId) => {
      // obj[botId] = v[botId];
      // });
      return obj;
    },
  );

  if (props.openTrades.length > 0) {
    let lastProfit = 0;
    let lastDate: number;
    const lastPoint = valueArray[valueArray.length - 1];
    if (lastPoint) {
      lastProfit = lastPoint.profit ?? 0;
      lastDate = lastPoint.date ?? 0;
    } else {
      const firstOpenTrade = props.openTrades[0];
      lastDate = firstOpenTrade ? firstOpenTrade.open_timestamp : 0;
    }
    const resultWithOpen = (lastProfit ?? 0) + openProfit.value;
    valueArray.push({ date: lastDate, currentProfit: lastProfit });
    // Add one day to date to ensure it's showing properly
    const tomorrow = Date.now() + 24 * 60 * 60 * 1000;
    valueArray.push({ date: tomorrow, currentProfit: resultWithOpen });
  }
  return valueArray;
});

function generateChart(initial = false) {
  const t = tokens.value;
  const projectedColor = openProfit.value > 0 ? t.profit : t.loss;
  const chartOptionsLoc: EChartsOption = {
    dataset: {
      dimensions: ['date', 'profit', 'currentProfit'],
      source: cumulativeData.value,
    },

    series: [
      {
        // Keep current-profit before profit, so the starting symbol is behind
        type: 'line',
        name: tr('charts.cumProfit.projected'),
        animation: initial,
        color: projectedColor,
        lineStyle: { color: projectedColor, type: 'dotted', width: 2 },
        itemStyle: { color: projectedColor, borderColor: t.surface, borderWidth: 2 },
        showSymbol: true,
        symbolSize: 8,
        encode: {
          x: 'date',
          y: 'currentProfit',
        },
      },
      {
        type: 'line',
        name: tr('charts.cumProfit.profit'),
        animation: initial,
        step: 'end',
        color: t.accent,
        lineStyle: { color: t.accent, width: 2 },
        areaStyle: { color: t.accentArea },
        encode: {
          x: 'date',
          y: 'profit',
        },
      },
    ],
  };
  return chartOptionsLoc;
}

const cumProfitChartOptions: ComputedRefWithControl<EChartsOption> = computedWithControl(
  () => props.trades,
  () => {
    const t = tokens.value;
    const hasOpen = props.openTrades.length > 0;
    const chartOptionsLoc: EChartsOption = {
      title: {
        text: tr('charts.cumProfit.title'),
        show: props.showTitle,
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params) => {
          const list = Array.isArray(params) ? params : [params];
          const row = (list[0]?.data ?? {}) as {
            date?: number;
            profit?: number;
            currentProfit?: number;
          };
          const date = row.date ? timestampToDateString(row.date) : '';
          const line =
            row.currentProfit !== undefined && row.currentProfit !== null
              ? novaTooltipRow(
                  t,
                  openProfit.value > 0 ? t.profit : t.loss,
                  tr('charts.cumProfit.projectedRow'),
                  formatPrice(row.currentProfit, 3),
                )
              : novaTooltipRow(
                  t,
                  t.accent,
                  tr('charts.shared.profit'),
                  formatPrice(row.profit ?? 0, 3),
                );
          return novaTooltipTitle(t, date) + line;
        },
        axisPointer: {
          type: 'line',
        },
      },
      legend: {
        data: hasOpen ? [tr('charts.cumProfit.profit'), tr('charts.cumProfit.projected')] : [],
        show: hasOpen,
        right: 0,
        top: 0,
        selectedMode: false,
      },
      useUTC: false,
      xAxis: {
        type: 'time',
        axisLabel: { hideOverlap: true },
      },
      yAxis: [
        {
          type: 'value',
          axisLabel: { formatter: (v: number) => formatPrice(v, 2) },
        },
      ],
      grid: {
        ...echartsGridDefault,
        top: props.showTitle || hasOpen ? 36 : 12,
      },
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
    };

    const chartOptionsLoc1 = generateChart(false);
    // Merge the series and dataset, but not the rest
    chartOptionsLoc.series = chartOptionsLoc1.series;
    chartOptionsLoc.dataset = chartOptionsLoc1.dataset;
    return chartOptionsLoc;
  },
);

onMounted(() => {
  // initializeChart();
});

watchThrottled(
  () => props.openTrades,
  () => {
    cumProfitChartOptions.trigger();
  },
  { throttle: 60 * 1000 },
);
watch([tokens, locale], () => {
  cumProfitChartOptions.trigger();
});
</script>

<template>
  <ECharts v-if="trades" :option="cumProfitChartOptions" :theme="chartTheme" autoresize />
</template>

<style scoped>
.echarts {
  width: 100%;
  height: 100%;
  min-height: 150px;
}
</style>
