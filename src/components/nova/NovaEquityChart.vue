<script setup lang="ts">
import { intlLocale } from '@/i18n';
import type { EChartsOption } from 'echarts';
import ECharts from 'vue-echarts';
import { LineChart } from 'echarts/charts';
import {
  AxisPointerComponent,
  GridComponent,
  MarkPointComponent,
  TooltipComponent,
} from 'echarts/components';
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import type { EquityPoint } from '@/utils/novaMetrics';

use([
  LineChart,
  CanvasRenderer,
  GridComponent,
  TooltipComponent,
  AxisPointerComponent,
  MarkPointComponent,
]);

const props = defineProps<{ points: EquityPoint[]; currency: string; liveEquity?: number }>();
const { privacy } = useNovaPrivacy();
const { chartTheme, tokens } = useNovaChartTheme();
// `t` is the chart token set below, so the translator is aliased.
const { t: tr } = useI18n();

const thousands = (v: number, decimals = 0) =>
  v.toLocaleString(intlLocale(), {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

const option = computed((): EChartsOption => {
  const hidden = privacy.value; // re-render axis labels and tooltip when privacy mode toggles
  const t = tokens.value;
  const pts = [...props.points];
  if (props.liveEquity !== undefined && pts.length) {
    const peak = Math.max(...pts.map((p) => p.equity), props.liveEquity);
    pts.push({ ts: Date.now(), equity: props.liveEquity, drawdown: props.liveEquity / peak - 1 });
  }
  const eq = pts.map((p) => [p.ts, Number(p.equity.toFixed(2))]);
  const dd = pts.map((p) => [p.ts, Number((p.drawdown * 100).toFixed(2))]);
  const last = eq[eq.length - 1];
  return {
    animationDuration: 600,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params];
        const first = list[0] as { axisValue?: number } | undefined;
        const when = first?.axisValue ? timestampms(Number(first.axisValue)) : '';
        const rows = list.map((p) => {
          const v = (p.value as number[])[1] ?? 0;
          const isEq = p.seriesIndex === 0;
          const shown = hidden
            ? '•••'
            : isEq
              ? `${thousands(v, 2)} ${props.currency}`
              : `${v.toFixed(2)}%`;
          return novaTooltipRow(
            t,
            isEq ? t.accent : t.loss,
            isEq ? tr('widgets.equityChart.equity') : tr('widgets.equityChart.drawdown'),
            shown,
          );
        });
        return novaTooltipTitle(t, when) + rows.join('');
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    // Fixed side margins (no auto label containment) so both panes share the same time extent.
    grid: [
      { left: 60, right: 16, top: 12, height: '58%', outerBoundsMode: 'none' },
      { left: 60, right: 16, top: '74%', bottom: 28, outerBoundsMode: 'none' },
    ],
    xAxis: [
      {
        type: 'time',
        gridIndex: 0,
        axisLabel: { show: false },
        axisLine: { show: false },
      },
      {
        type: 'time',
        gridIndex: 1,
        axisLabel: { fontSize: 11, hideOverlap: true },
      },
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        splitNumber: 4,
        axisLabel: { formatter: (v: number) => (hidden ? '' : thousands(v)) },
      },
      {
        type: 'value',
        gridIndex: 1,
        max: 0,
        splitNumber: 2,
        axisLabel: { formatter: (v: number) => `${v.toFixed(1)}%` },
      },
    ],
    series: [
      {
        name: tr('widgets.equityChart.seriesEquity', { currency: props.currency }),
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: eq,
        showSymbol: false,
        color: t.accent,
        lineStyle: { width: 2, color: t.accent },
        areaStyle: { color: t.accentArea, origin: 'start' },
        emphasis: { disabled: true },
        markPoint: last
          ? {
              silent: true,
              animation: false,
              symbol: 'circle',
              symbolSize: 10,
              itemStyle: { color: t.accent, borderColor: t.surface, borderWidth: 2 },
              label: { show: false },
              data: [{ name: 'Now', coord: last }],
            }
          : undefined,
      },
      {
        name: tr('widgets.equityChart.seriesDrawdown'),
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: dd,
        showSymbol: false,
        step: 'end',
        color: t.loss,
        lineStyle: { width: 2, color: t.loss },
        areaStyle: { color: t.lossArea },
        emphasis: { disabled: true },
      },
    ],
  };
});
</script>

<template>
  <div class="h-full min-h-64">
    <div v-if="points.length < 2" class="flex h-full flex-col items-center justify-center gap-3">
      <span class="flex size-10 items-center justify-center rounded-full bg-accented">
        <UIcon name="i-mdi-chart-line" class="size-5 text-muted" />
      </span>
      <p class="text-sm text-pretty text-muted">
        {{ $t('widgets.equityChart.empty') }}
      </p>
    </div>
    <ECharts v-else :option="option" :theme="chartTheme" autoresize class="h-full w-full" />
  </div>
</template>
