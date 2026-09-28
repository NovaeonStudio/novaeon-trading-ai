<script setup lang="ts">
import ECharts from 'vue-echarts';

import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { LineChart } from 'echarts/charts';
import {
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  MarkLineComponent,
  TransformComponent,
} from 'echarts/components';

import type { WalletHistoryPerBot } from '@/types';
import type { EChartsOption, MarkLineComponentOption } from 'echarts';

use([
  LineChart,
  CanvasRenderer,
  DatasetComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  VisualMapComponent,
  MarkLineComponent,
  TransformComponent,
]);

const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart theme tokens below, so the translate function is `tr`.
const { t: tr } = useI18n();

const props = withDefaults(
  defineProps<{
    walletData: WalletHistoryPerBot;
    showTitle?: boolean;
  }>(),
  {
    showTitle: true,
  },
);

const legendSelection = ref<Record<string, boolean>>({});

// vue-echarts types all chart event payloads as `unknown`.
function handleLegendSelectChanged(params: unknown) {
  legendSelection.value = (params as { selected: Record<string, boolean> }).selected;
}

const hasWalletData = computed(() =>
  Object.values(props.walletData).some(
    (history) => Array.isArray(history.data) && history.data.length > 0,
  ),
);

const walletHistoryOptions: ComputedRef<EChartsOption> = computed(() => {
  const walletEntries = Object.entries(props.walletData).filter(
    ([, history]) => Array.isArray(history?.data) && history.data.length > 0,
  );

  if (walletEntries.length === 0) {
    return {};
  }

  const dataset: EChartsOption['dataset'] = [];
  const series: EChartsOption['series'] = [];
  const visualMap: EChartsOption['visualMap'] = [];
  const legendData: string[] = [];
  const selectedBotIds = walletEntries
    .map(([botId]) => botId)
    .filter((botId) => legendSelection.value[botId] ?? true);
  const useProfitLossVisualMap = selectedBotIds.length === 1;
  const selectedBotId = selectedBotIds[0];
  const t = tokens.value;
  const captureLineColor = t.textMuted;
  const startingBalance = tr('charts.wallet.startingBalance');

  walletEntries.forEach(([botId, history], botIndex) => {
    const botName = history.botName ?? botId;
    const colDate = history.columns.findIndex((el) => el === '__date_ts');
    const colTotal = history.columns.findIndex((el) => el === 'total_quote');
    const startingField = history.data[0];
    if (!startingField || colDate < 0 || colTotal < 0) {
      return;
    }

    const startingValue = startingField[colTotal] as number;
    const captureStartTs = history.capture_start_ts ?? 0;
    const firstTimestamp = Number(startingField[colDate]);
    const shouldShowCaptureLine =
      captureStartTs > 0 && Number.isFinite(firstTimestamp) && captureStartTs !== firstTimestamp;

    const sourceDatasetIndex = dataset.length;
    const postCaptureDatasetIndex = sourceDatasetIndex + 1;
    const preCaptureDatasetIndex = sourceDatasetIndex + 2;
    const seriesStartIndex = series.length + 1; // +1 to account for the dummy series inserted below
    // Single wallet: the accent; several bots: categorical slots in fixed order.
    const seriesColor =
      walletEntries.length === 1 ? t.accent : t.categorical[botIndex % t.categorical.length];

    dataset.push(
      { source: history.data },
      {
        fromDatasetIndex: sourceDatasetIndex,
        transform: {
          // post capture start
          type: 'filter',
          config: { dimension: colDate, gte: captureStartTs - 1 },
        },
      },
      {
        fromDatasetIndex: sourceDatasetIndex,
        transform: {
          // pre capture start
          type: 'filter',
          config: { dimension: colDate, lte: captureStartTs + 1 },
        },
      },
    );

    const markLineData: MarkLineComponentOption['data'] = [
      {
        name: startingBalance,
        yAxis: startingValue,
        emphasis: { disabled: true },
        lineStyle: { color: t.axis, type: 'dashed', width: 1 },
        label: {
          show: true,
          position: 'insideStartTop',
          formatter:
            walletEntries.length === 1
              ? startingBalance
              : tr('charts.wallet.startingBalanceBot', { bot: botName }),
          ...novaLineLabel(t),
        },
      },
      {
        name: 'Zero',
        label: {
          show: false,
        },
        emphasis: { disabled: true },
        lineStyle: {
          type: 'solid',
          color: t.axis,
        },
        yAxis: 0,
      },
    ];

    if (shouldShowCaptureLine) {
      markLineData.push({
        name: 'Capture start',
        xAxis: captureStartTs,
        emphasis: { disabled: true },
        label: {
          show: true,
          position: 'insideEndTop',
          formatter: tr('charts.wallet.captureStart', { bot: botName }),
          ...novaLineLabel(t),
        },
        lineStyle: {
          type: 'dotted',
          color: captureLineColor,
          width: 1,
        },
      });
    }

    legendData.push(botName);

    if (useProfitLossVisualMap && selectedBotId === botId) {
      visualMap.push({
        show: false,
        seriesIndex: [seriesStartIndex, seriesStartIndex + 1],
        dimension: colTotal,
        pieces: [
          {
            gte: startingValue,
            color: t.profit,
          },
          {
            gt: startingValue - 0.01,
            lt: startingValue + 0.01,
            color: t.profit,
          },
          {
            lt: startingValue - 0.01,
            color: t.loss,
          },
        ],
      });
    }

    series.push(
      { type: 'line', data: [] },
      // Empty, hidden series to stabilize data zoom
      // https://github.com/apache/echarts/issues/21245
      {
        type: 'line',
        name: botName,
        showSymbol: false,
        color: seriesColor,
        datasetIndex: postCaptureDatasetIndex,
        encode: {
          x: colDate,
          y: colTotal,
        },
        lineStyle: {
          type: 'solid',
          width: 2,
        },
        markLine: {
          symbol: 'none',
          animation: false,
          data: markLineData,
        },
      },
      {
        type: 'line',
        name: botName,
        showSymbol: false,
        lineStyle: {
          type: 'dashed',
        },
        color: seriesColor,
        datasetIndex: preCaptureDatasetIndex,
        encode: {
          x: colDate,
          y: colTotal,
        },
      },
    );
  });

  if (series.length === 0) {
    return {};
  }

  const option: EChartsOption = {
    title: {
      text: tr('charts.wallet.title'),
      show: props.showTitle,
    },
    dataset,
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'line',
      },
      formatter: (params) => {
        const seriesParams = Array.isArray(params) ? params : [params];
        if (seriesParams.length === 0) {
          return '';
        }

        const firstPoint = seriesParams[0] as { data: unknown[]; encode?: { x?: number[] } };
        const xIdx = firstPoint.encode?.x?.[0] ?? 0;
        const label = `${timestampms(Number(firstPoint.data[xIdx]))}`;
        const lines = seriesParams.map((seriesPoint) => {
          const typedPoint = seriesPoint as {
            color: string;
            seriesName: string;
            data: unknown[];
            encode?: { y?: number[] };
          };
          const yIdx = typedPoint.encode?.y?.[0] ?? 0;
          const walletHistory = Number(typedPoint.data[yIdx]);
          return novaTooltipRow(
            t,
            typeof typedPoint.color === 'string' ? typedPoint.color : t.accent,
            typedPoint.seriesName,
            formatPrice(walletHistory, 3),
          );
        });

        return novaTooltipTitle(t, label) + lines.join('');
      },
    },
    grid: {
      ...echartsGridDefault,
      top: props.showTitle || walletEntries.length > 1 ? 36 : 16,
    },
    legend: {
      data: legendData,
      right: 0,
      top: 0,
      show: walletEntries.length > 1,
      selectedMode: true,
      selected: legendSelection.value,
    },
    xAxis: [
      {
        type: 'time',
        axisLine: { onZero: false },
        axisLabel: { hideOverlap: true },
        splitNumber: 6,
        axisPointer: {
          label: { show: false },
        },
      },
    ],
    yAxis: [
      {
        type: 'value',
        axisLabel: {
          // The exact data min / max labels crowd the rounded ticks next to them.
          showMinLabel: false,
          showMaxLabel: false,
          formatter: (value) => {
            return formatPrice(value, 2);
          },
        },
        min: 'dataMin',
        max: 'dataMax',
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
    visualMap,
    series,
  };
  return option;
});
</script>

<template>
  <ECharts
    v-if="hasWalletData"
    :option="walletHistoryOptions"
    :theme="chartTheme"
    @legendselectchanged="handleLegendSelectChanged"
    autoresize
  />
  <div v-else class="flex h-full flex-col items-center justify-center gap-3 p-4 text-center">
    <span class="flex size-10 items-center justify-center rounded-full bg-accented">
      <UIcon name="i-mdi-wallet-outline" class="size-5 text-muted" />
    </span>
    <p class="max-w-sm text-sm text-pretty text-muted">
      {{ tr('charts.wallet.empty') }}
    </p>
  </div>
</template>

<style lang="css" scoped>
.echarts {
  min-height: 150px;
  height: 100%;
  width: 100%;
}
</style>
